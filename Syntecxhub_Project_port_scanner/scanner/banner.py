"""
Banner grabbing and service fingerprinting.

For each open port, we send a protocol-appropriate probe and parse the
response to extract the service name and version string. Pure asyncio —
no external libraries required.
"""

import asyncio
import re
import ssl
from typing import Optional, Tuple

# ── Protocol-specific probes ──────────────────────────────────────────────────
# Maps port → list of (probe_bytes, label) to try in order.
# Empty probe means "just read the banner" (services that speak first).

_SPEAK_FIRST_PORTS = {21, 22, 23, 25, 110, 143, 220, 465, 514, 587, 993, 995}

PROBES: dict[int, list[bytes]] = {
    # Services that send a banner immediately (we just read)
    21:    [b''],
    22:    [b''],
    23:    [b''],
    25:    [b''],
    110:   [b''],
    143:   [b''],
    220:   [b''],
    465:   [b''],
    514:   [b''],
    587:   [b''],
    993:   [b''],
    995:   [b''],
    # HTTP/HTTPS — send a minimal HEAD request
    80:    [b'HEAD / HTTP/1.0\r\nHost: localhost\r\n\r\n'],
    8000:  [b'HEAD / HTTP/1.0\r\nHost: localhost\r\n\r\n'],
    8008:  [b'HEAD / HTTP/1.0\r\nHost: localhost\r\n\r\n'],
    8080:  [b'HEAD / HTTP/1.0\r\nHost: localhost\r\n\r\n'],
    8081:  [b'HEAD / HTTP/1.0\r\nHost: localhost\r\n\r\n'],
    8443:  [b'HEAD / HTTP/1.0\r\nHost: localhost\r\n\r\n'],
    443:   [b'HEAD / HTTP/1.0\r\nHost: localhost\r\n\r\n'],
    3000:  [b'HEAD / HTTP/1.0\r\nHost: localhost\r\n\r\n'],
    9090:  [b'HEAD / HTTP/1.0\r\nHost: localhost\r\n\r\n'],
    9200:  [b'GET / HTTP/1.0\r\nHost: localhost\r\n\r\n'],  # Elasticsearch REST
    10000: [b'GET / HTTP/1.0\r\nHost: localhost\r\n\r\n'],  # Webmin
    # Redis inline command
    6379:  [b'*1\r\n$4\r\nINFO\r\n', b'INFO\r\n'],
    6380:  [b'*1\r\n$4\r\nINFO\r\n'],
    # Memcached
    11211: [b'version\r\n'],
    # MySQL — server speaks first with handshake packet
    3306:  [b''],
    # MongoDB — speaks first with OP_REPLY on connection (varies by version)
    27017: [b''],
    27018: [b''],
    # PostgreSQL needs auth handshake; just note it's open
    5432:  [],
    # VNC — server sends protocol version
    5900:  [b''],
    5800:  [b''],
    # Docker API (plain HTTP)
    2375:  [b'GET /info HTTP/1.0\r\nHost: localhost\r\n\r\n'],
    2376:  [b'GET /info HTTP/1.0\r\nHost: localhost\r\n\r\n'],
    # CouchDB REST
    5984:  [b'GET / HTTP/1.0\r\nHost: localhost\r\n\r\n'],
    # Telnet
    4444:  [b''],  # Metasploit listener
}

# ── Version extraction regexes ────────────────────────────────────────────────
VERSION_PATTERNS: list[tuple[str, str, str]] = [
    # (service_name, regex, version_group)
    ('OpenSSH',        r'SSH-\d+\.\d+-OpenSSH[_\s]+([\d.p]+)',   '\\1'),
    ('Dropbear',       r'SSH-\d+\.\d+-dropbear[_\s]+([\d.]+)',   '\\1'),
    ('Apache',         r'Apache/([\d.]+)',                         '\\1'),
    ('nginx',          r'nginx/([\d.]+)',                          '\\1'),
    ('IIS',            r'Microsoft-IIS/([\d.]+)',                  '\\1'),
    ('Tomcat',         r'Apache[-/ ]Tomcat/([\d.]+)',              '\\1'),
    ('vsftpd',         r'vsftpd ([\d.]+)',                         '\\1'),
    ('ProFTPD',        r'ProFTPD ([\d.]+)',                        '\\1'),
    ('Exim',           r'Exim ([\d.]+)',                           '\\1'),
    ('Postfix',        r'Postfix',                                 ''),
    ('Dovecot',        r'Dovecot',                                 ''),
    ('MySQL',          r'([\d.]+)-(MariaDB|MySQL)',                '\\1 \\2'),
    ('MariaDB',        r'([\d.]+-MariaDB)',                        '\\1'),
    ('Redis',          r'redis_version:([\d.]+)',                  '\\1'),
    ('Memcached',      r'VERSION ([\d.]+)',                        '\\1'),
    ('Elasticsearch',  r'"number"\s*:\s*"([\d.]+)"',              '\\1'),
    ('CouchDB',        r'"version"\s*:\s*"([\d.]+)"',             '\\1'),
    ('Webmin',         r'Webmin',                                  ''),
    ('VNC RFB',        r'RFB ([\d.]+\.\d+)',                      '\\1'),
    ('Docker',         r'"ServerVersion"\s*:\s*"([\d.]+)"',       '\\1'),
    ('OpenSSL',        r'OpenSSL/([\d.a-z]+)',                     '\\1'),
    ('PHP',            r'PHP/([\d.]+)',                            '\\1'),
]

# Port → service name fallback (when no banner is parseable)
PORT_SERVICE_MAP: dict[int, str] = {
    21:    'FTP',       22:    'SSH',       23:    'Telnet',
    25:    'SMTP',      53:    'DNS',       80:    'HTTP',
    110:   'POP3',      111:   'RPC',       135:   'MSRPC',
    139:   'NetBIOS',   143:   'IMAP',      179:   'BGP',
    389:   'LDAP',      443:   'HTTPS',     445:   'SMB',
    465:   'SMTPS',     514:   'Syslog',    587:   'SMTP',
    631:   'IPP',       873:   'Rsync',     993:   'IMAPS',
    995:   'POP3S',     1433:  'MSSQL',     1723:  'PPTP',
    1900:  'UPnP',      2049:  'NFS',       2375:  'Docker API',
    2376:  'Docker TLS',3000:  'Web',       3306:  'MySQL',
    3389:  'RDP',       4444:  'Metasploit',5432:  'PostgreSQL',
    5900:  'VNC',       5984:  'CouchDB',   6379:  'Redis',
    6380:  'Redis',     8000:  'HTTP',      8080:  'HTTP',
    8443:  'HTTPS',     9200:  'Elasticsearch',10000:'Webmin',
    11211: 'Memcached', 27017: 'MongoDB',   27018: 'MongoDB',
    28017: 'MongoDB UI',
}

SSL_PORTS = {443, 465, 636, 993, 995, 8443, 2376}


def _extract_version(banner: str) -> Tuple[str, str]:
    """Return (service_name, version_string) from a raw banner string."""
    for name, pattern, repl in VERSION_PATTERNS:
        m = re.search(pattern, banner, re.IGNORECASE)
        if m:
            version = m.expand(repl).strip() if repl else ''
            return name, version
    return '', ''


async def grab_banner(
    host: str,
    port: int,
    timeout: float = 3.0,
) -> Tuple[str, str, str]:
    """
    Attempt to grab a service banner from host:port.

    Returns (raw_banner, service_name, version_string).
    Returns ('', '', '') if the port doesn't speak or times out.
    """
    probes = PROBES.get(port, [b'HEAD / HTTP/1.0\r\nHost: localhost\r\n\r\n'])
    if not probes:
        return ('', PORT_SERVICE_MAP.get(port, ''), '')

    use_ssl = port in SSL_PORTS

    for probe in probes:
        try:
            ctx = ssl.create_default_context() if use_ssl else None
            if ctx:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port, ssl=ctx),
                timeout=timeout,
            )

            if probe:
                writer.write(probe)
                await asyncio.wait_for(writer.drain(), timeout=timeout)

            raw = await asyncio.wait_for(reader.read(2048), timeout=timeout)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

            banner = raw.decode('utf-8', errors='replace').strip()
            if banner:
                svc, ver = _extract_version(banner)
                if not svc:
                    svc = PORT_SERVICE_MAP.get(port, '')
                return banner[:512], svc, ver

        except ssl.SSLError:
            # If SSL fails on a non-SSL port, it's probably plain text — skip
            if use_ssl:
                break
        except Exception:
            continue

    return ('', PORT_SERVICE_MAP.get(port, ''), '')


async def enrich_ports(
    host: str,
    port_results: list,
    timeout: float = 3.0,
) -> None:
    """
    Mutate a list of PortResult objects in-place by adding banner/service/version.
    Runs all banner grabs concurrently.
    """
    async def _enrich(pr) -> None:
        banner, service, version = await grab_banner(host, pr.port, timeout)
        pr.banner  = banner
        pr.service = service or PORT_SERVICE_MAP.get(pr.port, '')
        pr.version = version

    await asyncio.gather(*[_enrich(pr) for pr in port_results])
