"""
Async port scanning engine.

Uses asyncio.open_connection() for non-blocking TCP connect scans with a
Semaphore to cap concurrency. Supports single host, comma-separated list,
and CIDR notation (e.g. 192.168.1.0/24).
"""

import asyncio
import ipaddress
import random
import socket
import time
import datetime
from typing import Callable, List, Optional

from .models import HostResult, PortResult

# ── Port presets (Nmap-compatible top-N lists) ────────────────────────────────

TOP_100_PORTS = [
    7, 9, 13, 21, 22, 23, 25, 26, 37, 53, 79, 80, 81, 88, 106, 110, 111, 113,
    119, 135, 139, 143, 144, 179, 199, 389, 427, 443, 444, 445, 465, 513, 514,
    515, 543, 544, 548, 554, 587, 631, 646, 873, 990, 993, 995, 1025, 1026,
    1027, 1028, 1029, 1110, 1433, 1720, 1723, 1755, 1900, 2000, 2001, 2049,
    2121, 2717, 3000, 3128, 3306, 3389, 3986, 4899, 5000, 5009, 5051, 5060,
    5101, 5190, 5357, 5432, 5631, 5666, 5800, 5900, 6000, 6001, 6646, 7070,
    8000, 8008, 8009, 8080, 8081, 8443, 8888, 9100, 9999, 10000, 32768,
    49152, 49153, 49154, 49155, 49156, 49157,
]

TOP_1000_PORTS = sorted(set(TOP_100_PORTS + list(range(1, 1025))))

# Extra security-relevant ports appended to top-100 for the 'security' preset
SECURITY_PORTS = sorted(set(TOP_100_PORTS + [
    2375, 2376, 4444, 4848, 5984, 6379, 6380, 7474, 8161, 9000, 9090, 9200,
    9300, 11211, 27017, 27018, 28017, 50070,
]))


def parse_ports(spec: str) -> List[int]:
    """
    Parse a port specification string into a sorted list of port numbers.
    Supported formats:
      'top100', 'top1000', 'all', 'security',
      '80', '80,443,8080', '1-1000', '22,80,1000-2000'
    """
    spec = spec.strip()
    presets = {
        'top100':    TOP_100_PORTS,
        'top-100':   TOP_100_PORTS,
        'top1000':   TOP_1000_PORTS,
        'top-1000':  TOP_1000_PORTS,
        'all':       list(range(1, 65536)),
        'security':  SECURITY_PORTS,
    }
    if spec.lower() in presets:
        return presets[spec.lower()]

    ports: set[int] = set()
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            ports.update(range(int(a.strip()), int(b.strip()) + 1))
        else:
            ports.add(int(part))
    return sorted(ports)


def resolve_targets(target: str) -> List[str]:
    """
    Expand a target specification into a flat list of hostnames/IPs.
    Supports:
      - Single hostname or IP: 'example.com', '10.0.0.1'
      - CIDR notation: '192.168.1.0/24'
      - Comma-separated list: '10.0.0.1,10.0.0.2'
    """
    results: List[str] = []
    for t in target.split(','):
        t = t.strip()
        if not t:
            continue
        try:
            network = ipaddress.ip_network(t, strict=False)
            if network.num_addresses == 1:
                results.append(str(network.network_address))
            else:
                results.extend(str(ip) for ip in network.hosts())
        except ValueError:
            results.append(t)
    return results


class ScanEngine:
    """
    Concurrent TCP connect-scan engine.

    Parameters
    ----------
    timeout     : seconds to wait for each TCP connection
    concurrency : max simultaneous connection attempts (Semaphore limit)
    randomize   : shuffle port order before scanning (stealth mode)
    delay       : per-port delay in seconds (stealth mode)
    """

    def __init__(
        self,
        timeout:     float = 1.0,
        concurrency: int   = 500,
        randomize:   bool  = False,
        delay:       float = 0.0,
    ):
        self.timeout     = timeout
        self.concurrency = concurrency
        self.randomize   = randomize
        self.delay       = delay
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._progress_cb: Optional[Callable] = None

    def set_progress_callback(self, cb: Callable) -> None:
        """Register a callback(host, port, result) called for every probed port."""
        self._progress_cb = cb

    async def _scan_port(self, host: str, port: int) -> PortResult:
        """Attempt a TCP connect to host:port and return a PortResult."""
        assert self._semaphore is not None
        start = asyncio.get_event_loop().time()
        async with self._semaphore:
            if self.delay > 0:
                await asyncio.sleep(self.delay)
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=self.timeout,
                )
                latency = (asyncio.get_event_loop().time() - start) * 1000
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                result = PortResult(port=port, state='open', latency_ms=round(latency, 2))
            except ConnectionRefusedError:
                result = PortResult(port=port, state='closed')
            except (asyncio.TimeoutError, OSError, ConnectionResetError):
                result = PortResult(port=port, state='filtered')

        if self._progress_cb:
            self._progress_cb(host, port, result)
        return result

    async def scan_host(self, host: str, ports: List[int]) -> HostResult:
        """Scan all specified ports on a single host. Returns only open ports."""
        try:
            ip = socket.gethostbyname(host)
        except socket.gaierror:
            ip = host

        port_list = list(ports)
        if self.randomize:
            random.shuffle(port_list)

        t0 = time.monotonic()
        tasks = [self._scan_port(ip, p) for p in port_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        duration = time.monotonic() - t0

        open_ports = [
            r for r in results
            if isinstance(r, PortResult) and r.state == 'open'
        ]
        open_ports.sort(key=lambda p: p.port)

        return HostResult(
            host=host,
            ip=ip,
            ports=open_ports,
            scan_duration=round(duration, 2),
            timestamp=datetime.datetime.now().isoformat(),
        )

    async def scan(self, targets: List[str], ports: List[int]) -> List[HostResult]:
        """Scan multiple hosts concurrently. Returns a list of HostResult."""
        self._semaphore = asyncio.Semaphore(self.concurrency)
        tasks = [self.scan_host(t, ports) for t in targets]
        return await asyncio.gather(*tasks)

    def run(self, targets: List[str], ports: List[int]) -> List[HostResult]:
        """Synchronous wrapper around scan() — creates a fresh event loop."""
        return asyncio.run(self.scan(targets, ports))
