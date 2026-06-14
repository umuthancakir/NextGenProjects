"""
SQLite-backed scan history with diff capability.

Each scan stores:
  - scan_id (auto int), name, timestamp, target spec, scan profile
  - host results as a JSON blob per host

Diff: compare open ports/services/risk-levels between two scans of the same
host — highlights newly opened ports, closed ports, and changed services.
"""

import json
import os
import sqlite3
import datetime
from dataclasses import asdict, dataclass
from typing import List, Optional

from .models import HostResult, HostRisk, PortResult, RiskLevel

_DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scan_history.db')


@dataclass
class ScanRecord:
    scan_id:    int
    name:       str
    timestamp:  str
    target:     str
    profile:    str
    host_count: int
    open_ports: int


@dataclass
class PortDiff:
    port:       int
    state:      str   # 'new', 'closed', 'changed', 'unchanged'
    service_a:  str   = ''
    service_b:  str   = ''
    risk_a:     str   = ''
    risk_b:     str   = ''


@dataclass
class HostDiff:
    host:          str
    port_diffs:    List[PortDiff]
    new_ports:     List[int]
    closed_ports:  List[int]
    changed_ports: List[int]


@dataclass
class DiffResult:
    scan_id_a:   int
    scan_id_b:   int
    name_a:      str
    name_b:      str
    timestamp_a: str
    timestamp_b: str
    host_diffs:  List[HostDiff]
    summary:     str


class ScanHistory:
    def __init__(self, db_path: str = _DEFAULT_DB):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS scans (
                    scan_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       TEXT NOT NULL,
                    timestamp  TEXT NOT NULL,
                    target     TEXT NOT NULL,
                    profile    TEXT NOT NULL DEFAULT 'custom',
                    host_count INTEGER DEFAULT 0,
                    open_ports INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS hosts (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id   INTEGER NOT NULL REFERENCES scans(scan_id),
                    host      TEXT NOT NULL,
                    ip        TEXT,
                    data_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_hosts_scan ON hosts(scan_id);
                CREATE INDEX IF NOT EXISTS idx_hosts_host ON hosts(host);
            """)

    # ── Saving ───────────────────────────────────────────────────────────────

    def save(
        self,
        host_results:  List[HostResult],
        target:        str,
        profile:       str  = 'custom',
        name:          Optional[str] = None,
    ) -> int:
        """Persist a scan and return the new scan_id."""
        ts         = datetime.datetime.now().isoformat()
        name       = name or f"scan_{ts[:19].replace(':', '-')}"
        open_total = sum(len(hr.ports) for hr in host_results)

        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO scans(name,timestamp,target,profile,host_count,open_ports) "
                "VALUES(?,?,?,?,?,?)",
                (name, ts, target, profile, len(host_results), open_total),
            )
            scan_id = cur.lastrowid

            for hr in host_results:
                conn.execute(
                    "INSERT INTO hosts(scan_id,host,ip,data_json) VALUES(?,?,?,?)",
                    (scan_id, hr.host, hr.ip, _host_to_json(hr)),
                )
        return scan_id

    # ── Listing ───────────────────────────────────────────────────────────────

    def list(self, limit: int = 50) -> List[ScanRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM scans ORDER BY scan_id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [ScanRecord(**dict(r)) for r in rows]

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def get(self, scan_id: int) -> Optional[tuple[ScanRecord, List[HostResult]]]:
        """Return (ScanRecord, [HostResult]) or None if not found."""
        with self._conn() as conn:
            scan_row = conn.execute(
                "SELECT * FROM scans WHERE scan_id=?", (scan_id,)
            ).fetchone()
            if not scan_row:
                return None
            host_rows = conn.execute(
                "SELECT * FROM hosts WHERE scan_id=?", (scan_id,)
            ).fetchall()

        record  = ScanRecord(**dict(scan_row))
        results = [_json_to_host(r['data_json']) for r in host_rows]
        return record, results

    def delete(self, scan_id: int) -> bool:
        with self._conn() as conn:
            conn.execute("DELETE FROM hosts WHERE scan_id=?", (scan_id,))
            conn.execute("DELETE FROM scans WHERE scan_id=?", (scan_id,))
        return True

    # ── Diff ──────────────────────────────────────────────────────────────────

    def diff(self, scan_id_a: int, scan_id_b: int) -> Optional[DiffResult]:
        """
        Compare two scans and return a DiffResult describing what changed.
        """
        result_a = self.get(scan_id_a)
        result_b = self.get(scan_id_b)
        if not result_a or not result_b:
            return None

        rec_a, hosts_a = result_a
        rec_b, hosts_b = result_b

        # Build lookup: host → {port → PortResult}
        def _index(host_results):
            idx = {}
            for hr in host_results:
                idx[hr.host] = {pr.port: pr for pr in hr.ports}
            return idx

        idx_a = _index(hosts_a)
        idx_b = _index(hosts_b)

        all_hosts = sorted(set(idx_a.keys()) | set(idx_b.keys()))
        host_diffs: List[HostDiff] = []

        for host in all_hosts:
            ports_a = idx_a.get(host, {})
            ports_b = idx_b.get(host, {})
            all_ports = sorted(set(ports_a.keys()) | set(ports_b.keys()))

            port_diffs = []
            new_ports     = []
            closed_ports  = []
            changed_ports = []

            for port in all_ports:
                if port in ports_b and port not in ports_a:
                    new_ports.append(port)
                    port_diffs.append(PortDiff(
                        port=port, state='new',
                        service_b=ports_b[port].service or str(port),
                    ))
                elif port in ports_a and port not in ports_b:
                    closed_ports.append(port)
                    port_diffs.append(PortDiff(
                        port=port, state='closed',
                        service_a=ports_a[port].service or str(port),
                    ))
                else:
                    pa, pb = ports_a[port], ports_b[port]
                    changed = pa.service != pb.service or pa.version != pb.version
                    state   = 'changed' if changed else 'unchanged'
                    if changed:
                        changed_ports.append(port)
                    port_diffs.append(PortDiff(
                        port=port, state=state,
                        service_a=pa.service, service_b=pb.service,
                    ))

            host_diffs.append(HostDiff(
                host=host,
                port_diffs=port_diffs,
                new_ports=new_ports,
                closed_ports=closed_ports,
                changed_ports=changed_ports,
            ))

        total_new    = sum(len(hd.new_ports)     for hd in host_diffs)
        total_closed = sum(len(hd.closed_ports)  for hd in host_diffs)
        total_changed= sum(len(hd.changed_ports) for hd in host_diffs)

        summary = (
            f"{total_new} new port(s), {total_closed} closed port(s), "
            f"{total_changed} changed service(s) across {len(host_diffs)} host(s)"
        )

        return DiffResult(
            scan_id_a=scan_id_a, scan_id_b=scan_id_b,
            name_a=rec_a.name,   name_b=rec_b.name,
            timestamp_a=rec_a.timestamp, timestamp_b=rec_b.timestamp,
            host_diffs=host_diffs, summary=summary,
        )


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _host_to_json(hr: HostResult) -> str:
    return json.dumps({
        'host':          hr.host,
        'ip':            hr.ip,
        'scan_duration': hr.scan_duration,
        'timestamp':     hr.timestamp,
        'ports': [
            {'port': p.port, 'state': p.state, 'service': p.service,
             'banner': p.banner[:256], 'version': p.version, 'latency_ms': p.latency_ms}
            for p in hr.ports
        ],
    })


def _json_to_host(raw: str) -> HostResult:
    d = json.loads(raw)
    ports = [
        PortResult(
            port=p['port'], state=p['state'], service=p.get('service',''),
            banner=p.get('banner',''), version=p.get('version',''),
            latency_ms=p.get('latency_ms',0.0),
        )
        for p in d.get('ports', [])
    ]
    return HostResult(
        host=d['host'], ip=d.get('ip',''),
        ports=ports,
        scan_duration=d.get('scan_duration',0.0),
        timestamp=d.get('timestamp',''),
    )
