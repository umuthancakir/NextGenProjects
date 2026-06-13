"""
Rich-based terminal dashboard.

Scanning phase:  Live display with Progress bars + scrolling table of open ports.
Results phase:   Navigable menu system — host list → host detail → port detail.
History phase:   Table of past scans, diff viewer.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Callable, List, Optional

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn, MofNCompleteColumn, Progress,
    SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn,
)
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from scanner.models import CVE, HostRisk, PortRisk, RiskLevel
from scanner.history import DiffResult, ScanRecord

console = Console()

# ── Colour helpers ────────────────────────────────────────────────────────────

_RISK_STYLE = {
    RiskLevel.CRITICAL: 'bold red',
    RiskLevel.HIGH:     'red',
    RiskLevel.MEDIUM:   'yellow',
    RiskLevel.LOW:      'green',
    RiskLevel.INFO:     'dim',
    RiskLevel.UNKNOWN:  'dim',
}
_RISK_EMOJI = {
    RiskLevel.CRITICAL: '[bold red]●[/]',
    RiskLevel.HIGH:     '[red]●[/]',
    RiskLevel.MEDIUM:   '[yellow]●[/]',
    RiskLevel.LOW:      '[green]●[/]',
    RiskLevel.INFO:     '[dim]○[/]',
    RiskLevel.UNKNOWN:  '[dim]○[/]',
}


def _risk_badge(rl: RiskLevel) -> str:
    return f"[{_RISK_STYLE[rl]}]{rl.label.upper()}[/]"


def _header() -> Panel:
    t = Text()
    t.append('▸ ', style='bold cyan')
    t.append('VulnScanner', style='bold white')
    t.append('  — Defensive Vulnerability Assessment Tool', style='dim')
    return Panel(Align.center(t), border_style='cyan', padding=(0, 2))


# ══════════════════════════════════════════════════════════════════════════════
# LIVE SCANNING DISPLAY
# ══════════════════════════════════════════════════════════════════════════════

class ScanDisplay:
    """
    Shown during scanning — live progress bar + open-port discovery table.
    Thread-safe: progress_callback() can be called from asyncio tasks.
    """

    def __init__(self, total_ports: int, target: str):
        self._total   = total_ports
        self._scanned = 0
        self._open: list[tuple] = []   # (host, port, service, latency)
        self._lock    = threading.Lock()
        self._start   = time.monotonic()

        self._progress = Progress(
            SpinnerColumn(spinner_name='dots'),
            TextColumn('[cyan]{task.description}'),
            BarColumn(bar_width=40, style='cyan', complete_style='bold cyan'),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            expand=False,
        )
        self._task = self._progress.add_task(
            f'Scanning [bold]{target}[/]…', total=total_ports
        )

    def progress_callback(self, host: str, port: int, result) -> None:
        with self._lock:
            self._scanned += 1
            self._progress.update(self._task, advance=1)
            if result.state == 'open':
                self._open.append((host, port, result.service or '—', result.latency_ms))

    def _build_table(self) -> Table:
        t = Table(
            box=box.MINIMAL_DOUBLE_HEAD,
            border_style='cyan',
            header_style='bold cyan',
            show_lines=False,
            expand=True,
        )
        t.add_column('Host',       style='white',     min_width=15)
        t.add_column('Port',       style='bold cyan',  width=7,  justify='right')
        t.add_column('Service',    style='green',      min_width=12)
        t.add_column('Latency',    style='dim',        width=9,  justify='right')

        with self._lock:
            for host, port, svc, lat in self._open[-20:]:   # show last 20 discoveries
                t.add_row(host, str(port), svc, f'{lat:.1f} ms')

        if not self._open:
            t.add_row('[dim]Scanning…[/]', '', '', '')
        return t

    def _build_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(self._progress,       name='progress', size=3),
            Layout(self._build_table(),  name='table'),
        )
        return layout

    def run_with_scan(self, scan_coro) -> list:
        """Run the asyncio scan coroutine while displaying the live dashboard."""
        results = []

        async def _runner():
            r = await scan_coro
            results.extend(r)

        with Live(self._build_layout(), console=console, refresh_per_second=10) as live:
            loop = asyncio.new_event_loop()

            def _update():
                while not loop.is_closed():
                    live.update(self._build_layout())
                    time.sleep(0.05)

            t = threading.Thread(target=_update, daemon=True)
            t.start()

            try:
                loop.run_until_complete(_runner())
            finally:
                loop.close()

        return results


# ══════════════════════════════════════════════════════════════════════════════
# RESULTS BROWSER
# ══════════════════════════════════════════════════════════════════════════════

def show_host_list(host_risks: List[HostRisk]) -> None:
    """Interactive host list → drill into a host."""
    while True:
        console.clear()
        console.print(_header())
        console.print()

        t = Table(
            title='[bold]Scan Results[/]',
            box=box.ROUNDED,
            border_style='cyan',
            header_style='bold cyan',
            show_lines=True,
            expand=True,
        )
        t.add_column('#',        width=4,  justify='right', style='dim')
        t.add_column('Host',               style='white')
        t.add_column('IP',                 style='dim')
        t.add_column('Open Ports', width=12, justify='right')
        t.add_column('Risk',       width=12)
        t.add_column('Summary',            style='dim', no_wrap=False)

        for i, hr in enumerate(host_risks, 1):
            badge = _risk_badge(hr.overall_risk)
            t.add_row(
                str(i),
                hr.host_result.host,
                hr.host_result.ip,
                str(len(hr.port_risks)),
                badge,
                hr.summary,
            )

        console.print(t)
        console.print()

        total_open = sum(len(hr.port_risks) for hr in host_risks)
        console.print(
            f'[dim]  {len(host_risks)} host(s) · {total_open} open port(s) total[/]'
        )
        console.print()

        choice = Prompt.ask(
            '[cyan]Enter host number to drill down, or [bold]q[/cyan][bold][/bold] to quit[/]',
            default='q',
        )
        if choice.lower() == 'q':
            break
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(host_risks):
                show_host_detail(host_risks[idx])
        except ValueError:
            pass


def show_host_detail(hr: HostRisk) -> None:
    """Per-host view with port breakdown table."""
    while True:
        console.clear()
        console.print(_header())
        console.print()

        # Host summary panel
        summary_lines = [
            f'[bold white]{hr.host_result.host}[/]  [dim]({hr.host_result.ip})[/]',
            f'Overall risk:   {_risk_badge(hr.overall_risk)}    '
            f'Score: [bold]{hr.risk_score}[/]/100',
            f'Open ports:     [cyan]{len(hr.port_risks)}[/]    '
            f'Scan time: [dim]{hr.host_result.scan_duration}s[/]',
            f'[dim]{hr.summary}[/]',
        ]
        console.print(Panel(
            '\n'.join(summary_lines),
            title='[bold]Host Summary[/]',
            border_style='cyan', padding=(0, 2),
        ))
        console.print()

        if not hr.port_risks:
            console.print('[dim]  No open ports found.[/]')
            Prompt.ask('[cyan]Press Enter to go back[/]', default='')
            return

        t = Table(
            box=box.ROUNDED, border_style='cyan', header_style='bold cyan',
            show_lines=True, expand=True,
        )
        t.add_column('#',        width=4,  justify='right', style='dim')
        t.add_column('Port',     width=7,  justify='right', style='bold cyan')
        t.add_column('Service',  min_width=12, style='green')
        t.add_column('Version',  min_width=12, style='dim')
        t.add_column('Risk',     width=12)
        t.add_column('Exposure', width=12, style='dim')
        t.add_column('CVEs',     width=6,  justify='right')
        t.add_column('Latency',  width=9,  justify='right', style='dim')

        for i, pr in enumerate(hr.port_risks, 1):
            badge = _risk_badge(pr.risk_level)
            t.add_row(
                str(i),
                str(pr.port_result.port),
                pr.service_name or '—',
                pr.port_result.version or '—',
                badge,
                pr.internet_exposure or '—',
                str(len(pr.cves)) if pr.cves else '[dim]—[/]',
                f'{pr.port_result.latency_ms:.1f} ms',
            )

        console.print(t)
        console.print()

        choice = Prompt.ask(
            '[cyan]Enter port number to see details, or [bold]b[/bold] to go back[/]',
            default='b',
        )
        if choice.lower() in ('b', 'q', ''):
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(hr.port_risks):
                show_port_detail(hr.port_risks[idx])
        except ValueError:
            pass


def show_port_detail(pr: PortRisk) -> None:
    """Full detail view for a single port."""
    console.clear()
    console.print(_header())
    console.print()

    port = pr.port_result.port
    svc  = pr.service_name or f'Port {port}'

    console.print(Rule(
        f'[bold]{svc}[/] — Port {port}  {_risk_badge(pr.risk_level)}',
        style='cyan',
    ))
    console.print()

    # Banner snippet
    if pr.port_result.banner:
        console.print(Panel(
            Text(pr.port_result.banner[:300], style='dim'),
            title='[dim]Banner[/]', border_style='dim', padding=(0, 1),
        ))
        console.print()

    # Description
    if pr.description:
        console.print(Panel(
            pr.description,
            title='[bold]What is this?[/]', border_style='yellow', padding=(0, 2),
        ))
        console.print()

    # Risks
    if pr.risks:
        risks_text = '\n'.join(f'  [red]▸[/] {r}' for r in pr.risks)
        console.print(Panel(risks_text, title='[bold red]Risks[/]',
                            border_style='red', padding=(0, 1)))
        console.print()

    # Recommendations
    if pr.recommendations:
        rec_text = '\n'.join(f'  [green]✓[/] {r}' for r in pr.recommendations)
        console.print(Panel(rec_text, title='[bold green]Recommendations[/]',
                            border_style='green', padding=(0, 1)))
        console.print()

    # CVEs
    if pr.cves:
        t = Table(
            box=box.SIMPLE_HEAD, border_style='dim', header_style='bold yellow',
            expand=True, title='[bold yellow]CVEs from NVD[/]',
        )
        t.add_column('CVE ID',      width=18)
        t.add_column('CVSS',        width=6,  justify='right')
        t.add_column('Severity',    width=10)
        t.add_column('Description', no_wrap=False)
        t.add_column('URL',         style='dim cyan', no_wrap=True)

        for cve in pr.cves:
            score_str = f'{cve.cvss_score:.1f}' if cve.cvss_score else '—'
            sev_style = {
                'critical': 'bold red', 'high': 'red',
                'medium': 'yellow', 'low': 'green',
            }.get(cve.severity.lower(), 'dim')
            t.add_row(
                f'[bold]{cve.id}[/]',
                score_str,
                f'[{sev_style}]{cve.severity.upper()}[/]',
                cve.description[:120] + ('…' if len(cve.description) > 120 else ''),
                cve.url,
            )
        console.print(t)
        console.print()

    Prompt.ask('[cyan]Press Enter to go back[/]', default='')


# ══════════════════════════════════════════════════════════════════════════════
# HISTORY BROWSER
# ══════════════════════════════════════════════════════════════════════════════

def show_history(records: List[ScanRecord]) -> None:
    console.clear()
    console.print(_header())
    console.print()

    if not records:
        console.print('[dim]  No scan history found. Run a scan first.[/]')
        Prompt.ask('[cyan]Press Enter to continue[/]', default='')
        return

    t = Table(
        title='[bold]Scan History[/]',
        box=box.ROUNDED, border_style='cyan', header_style='bold cyan',
        show_lines=True, expand=True,
    )
    t.add_column('ID',        width=5,  justify='right', style='bold cyan')
    t.add_column('Name',      min_width=20, style='white')
    t.add_column('Target',    min_width=15, style='dim')
    t.add_column('Profile',   width=10)
    t.add_column('Hosts',     width=7,  justify='right')
    t.add_column('Open Ports',width=11, justify='right')
    t.add_column('Timestamp', width=20, style='dim')

    for rec in records:
        t.add_row(
            str(rec.scan_id),
            rec.name,
            rec.target,
            rec.profile,
            str(rec.host_count),
            str(rec.open_ports),
            rec.timestamp[:19].replace('T', ' '),
        )

    console.print(t)
    console.print()


def show_diff(diff: DiffResult) -> None:
    """Display a scan diff result."""
    console.clear()
    console.print(_header())
    console.print()

    console.print(Panel(
        f'[bold]Scan A:[/] #{diff.scan_id_a} — {diff.name_a} ({diff.timestamp_a[:19].replace("T"," ")})\n'
        f'[bold]Scan B:[/] #{diff.scan_id_b} — {diff.name_b} ({diff.timestamp_b[:19].replace("T"," ")})\n\n'
        f'[dim]{diff.summary}[/]',
        title='[bold]Scan Diff[/]', border_style='cyan', padding=(0, 2),
    ))
    console.print()

    for hd in diff.host_diffs:
        changed = hd.new_ports or hd.closed_ports or hd.changed_ports
        if not changed:
            continue

        console.print(Rule(f'[bold]{hd.host}[/]', style='dim'))

        t = Table(box=box.SIMPLE_HEAD, expand=True, header_style='bold')
        t.add_column('Port',    width=7,  justify='right')
        t.add_column('Change',  width=10)
        t.add_column('Service A', min_width=12, style='dim')
        t.add_column('Service B', min_width=12)

        for pd in hd.port_diffs:
            if pd.state == 'unchanged':
                continue
            style = {'new': 'green', 'closed': 'red', 'changed': 'yellow'}.get(pd.state, '')
            t.add_row(
                str(pd.port),
                f'[{style}]{pd.state.upper()}[/]',
                pd.service_a or '—',
                pd.service_b or '—',
            )
        console.print(t)
        console.print()

    Prompt.ask('[cyan]Press Enter to continue[/]', default='')


# ══════════════════════════════════════════════════════════════════════════════
# PROFILES TABLE
# ══════════════════════════════════════════════════════════════════════════════

def show_profiles(profiles: dict) -> None:
    console.clear()
    console.print(_header())
    console.print()

    t = Table(
        title='[bold]Scan Profiles[/]',
        box=box.ROUNDED, border_style='cyan', header_style='bold cyan',
        show_lines=True, expand=True,
    )
    t.add_column('Name',        width=10, style='bold cyan')
    t.add_column('Ports',       width=12)
    t.add_column('Timeout',     width=9,  justify='right')
    t.add_column('Concurrency', width=13, justify='right')
    t.add_column('Stealth',     width=9,  justify='center')
    t.add_column('NVD',         width=5,  justify='center')
    t.add_column('Description', no_wrap=False)

    for p in profiles.values():
        t.add_row(
            p.name,
            p.ports if len(p.ports) < 30 else p.ports[:27] + '…',
            f'{p.timeout}s',
            str(p.concurrency),
            '[green]✓[/]' if p.randomize else '[dim]—[/]',
            '[green]✓[/]' if p.use_nvd   else '[dim]—[/]',
            p.description,
        )

    console.print(t)
    console.print()
    console.print(
        '[dim]  Stealth mode: randomized port order + inter-probe delay — '
        'reduces IDS/IPS detection probability[/]'
    )
    console.print()
    Prompt.ask('[cyan]Press Enter to continue[/]', default='')


# ══════════════════════════════════════════════════════════════════════════════
# QUICK HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def print_scan_start(target: str, ports: list, profile_name: str) -> None:
    console.print()
    console.print(Panel(
        f'[bold white]Target:[/]  [cyan]{target}[/]\n'
        f'[bold white]Ports:[/]   [cyan]{len(ports)} ports[/] '
        f'([dim]{ports[0]}–{ports[-1]}[/])\n'
        f'[bold white]Profile:[/] [cyan]{profile_name}[/]',
        title='[bold]Starting Scan[/]', border_style='cyan', padding=(0, 2),
    ))
    console.print()


def print_error(msg: str) -> None:
    console.print(f'[bold red]  Error:[/] {msg}')


def print_success(msg: str) -> None:
    console.print(f'[bold green]  ✓[/] {msg}')


def print_info(msg: str) -> None:
    console.print(f'[dim]  {msg}[/]')
