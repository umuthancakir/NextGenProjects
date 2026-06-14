#!/usr/bin/env python3
"""
VulnScanner — Interactive Defensive Port Vulnerability Assessment Tool
======================================================================
Run with no arguments to launch the interactive menu:
  python main.py

Or use CLI mode for scripting:
  python main.py scan 192.168.1.1 --profile full

IMPORTANT: Only scan systems you own or have explicit written permission to scan.
"""

import asyncio
import datetime
import os
import sys

from rich.console import Console
from rich.prompt  import Confirm, IntPrompt, Prompt
from rich         import box
from rich.panel   import Panel
from rich.table   import Table
from rich.text    import Text
from rich.rule    import Rule

from scanner.core    import ScanEngine, parse_ports, resolve_targets
from scanner.banner  import enrich_ports
from scanner         import classifier, profiles as profile_module, reporter
from scanner.history import ScanHistory
from tui             import dashboard as dash

console = Console()

# ══════════════════════════════════════════════════════════════════════════════
# SHARED SCAN RUNNER  (used by both interactive menu and CLI mode)
# ══════════════════════════════════════════════════════════════════════════════

def run_scan(
    target:      str,
    port_spec:   str   = 'top100',
    profile_name:str   = 'quick',
    timeout:     float = None,
    concurrency: int   = None,
    banner_grab: bool  = True,
    use_nvd:     bool  = False,
    api_key:     str   = None,
    scan_name:   str   = None,
    output_dir:  str   = 'reports',
    formats:     list  = None,
):
    """Core scan logic shared by interactive and CLI modes."""
    profile = profile_module.get(profile_name) or profile_module.get('quick')

    port_spec   = port_spec   or profile.ports
    timeout     = timeout     or profile.timeout
    concurrency = concurrency or profile.concurrency
    api_key     = api_key     or os.environ.get('NVD_API_KEY')

    targets = resolve_targets(target)
    ports   = parse_ports(port_spec)

    if not targets:
        dash.print_error("No valid targets found.")
        return None

    dash.print_scan_start(target, ports, profile_name)
    if len(targets) > 1:
        dash.print_info(f"Expanded to {len(targets)} hosts")
    if use_nvd and not api_key:
        dash.print_info("NVD: no API key — rate-limited to 5 req/30s (set NVD_API_KEY env var)")

    # Scanning
    engine = ScanEngine(
        timeout=timeout, concurrency=concurrency,
        randomize=profile.randomize, delay=profile.delay,
    )
    total_probes = len(targets) * len(ports)
    scan_display = dash.ScanDisplay(total_probes, target)
    engine.set_progress_callback(scan_display.progress_callback)

    host_results = scan_display.run_with_scan(engine.scan(targets, ports))
    total_open   = sum(len(hr.ports) for hr in host_results)
    dash.print_success(
        f"Scan complete — {total_open} open port(s) across {len(host_results)} host(s)"
    )

    # Banner grabbing
    if banner_grab and total_open > 0:
        dash.print_info("Grabbing service banners…")
        loop = asyncio.new_event_loop()
        try:
            for hr in host_results:
                if hr.ports:
                    loop.run_until_complete(enrich_ports(hr.ip or hr.host, hr.ports, timeout=3.0))
        finally:
            loop.close()
        dash.print_success("Banner grabbing complete")

    # Classification + NVD
    if use_nvd and total_open > 0:
        dash.print_info("Querying NVD for CVEs (may take a moment)…")
    host_risks = classifier.classify_all(host_results, api_key=api_key, use_nvd=use_nvd)

    # Persist to history
    history  = ScanHistory()
    ts       = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    name     = scan_name or f"{target.replace('/', '_')}_{ts}"
    scan_id  = history.save(host_results, target=target, profile=profile_name, name=name)
    dash.print_success(f"Saved to history — scan ID: [bold cyan]{scan_id}[/]")

    # Reports
    if formats:
        os.makedirs(output_dir, exist_ok=True)
        base = os.path.join(output_dir, f"scan_{scan_id}_{ts}")
        paths = {}
        if 'json'     in formats: paths['JSON']     = reporter.generate_json(host_risks, f"{base}.json")
        if 'csv'      in formats: paths['CSV']      = reporter.generate_csv(host_risks,  f"{base}.csv")
        if 'markdown' in formats: paths['Markdown'] = reporter.generate_markdown(
            host_risks, f"{base}.md", target=target)
        for fmt, path in paths.items():
            dash.print_success(f"{fmt} report → [cyan]{path}[/]")

    return host_risks


# ══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE MENU HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _clear():
    console.clear()

def _pause():
    Prompt.ask("\n[dim]  Press Enter to return to the menu[/]", default="")

def _banner():
    console.print()
    console.print(Panel(
        "[bold cyan]▸ VulnScanner[/]  [dim]— Defensive Vulnerability Assessment Tool[/]\n"
        "[dim]  Only scan systems you own or have explicit written permission to scan.[/]",
        border_style="cyan", padding=(0, 2),
    ))
    console.print()

def _menu_table(options: list[tuple]) -> None:
    """Print a numbered option list.  options = [(key, icon, label, desc), ...]"""
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2), expand=False)
    t.add_column("key",   style="bold cyan",  width=4)
    t.add_column("icon",  width=3)
    t.add_column("label", style="bold white", min_width=20)
    t.add_column("desc",  style="dim")
    for key, icon, label, desc in options:
        t.add_row(f"[{key}]", icon, label, desc)
    console.print(t)

def _pick(prompt: str, valid: set, default: str = '') -> str:
    while True:
        ans = Prompt.ask(f"  [cyan]{prompt}[/]", default=default).strip()
        if ans in valid:
            return ans
        console.print(f"  [red]Invalid choice — enter one of: {', '.join(sorted(valid))}[/]")


# ══════════════════════════════════════════════════════════════════════════════
# SCAN WIZARD  (interactive guided scan)
# ══════════════════════════════════════════════════════════════════════════════

def _wizard_scan():
    _clear(); _banner()
    console.print(Rule("[bold]New Scan[/]", style="cyan"))
    console.print()

    # Target
    target = Prompt.ask("  [bold]Target[/] [dim](IP, hostname, CIDR 192.168.1.0/24, or comma-separated)[/]")
    if not target.strip():
        dash.print_error("No target entered."); _pause(); return

    console.print()

    # Profile selection
    console.print("  [bold]Select a scan profile:[/]")
    console.print()
    prof_options = []
    for i, (name, p) in enumerate(profile_module.PROFILES.items(), 1):
        prof_options.append((str(i), '⚡' if 'quick' in name else '🔍', name.upper(), p.description))
    _menu_table(prof_options)
    console.print()

    valid_profile_nums = {str(i) for i in range(1, len(profile_module.PROFILES) + 1)}
    pnum = _pick(f"Profile [1-{len(profile_module.PROFILES)}]", valid_profile_nums, default='1')
    profile_name = list(profile_module.PROFILES.keys())[int(pnum) - 1]
    profile      = profile_module.PROFILES[profile_name]
    console.print(f"  [green]✓[/] Profile: [bold cyan]{profile_name}[/] — {profile.description}")
    console.print()

    # Advanced options
    use_advanced = Confirm.ask("  [dim]Customize ports / NVD / timeout?[/]", default=False)
    port_spec   = profile.ports
    timeout     = profile.timeout
    concurrency = profile.concurrency
    use_nvd     = profile.use_nvd
    banner_grab = True

    if use_advanced:
        console.print()
        console.print(f"  [dim]Current ports: {profile.ports}[/]")
        custom_ports = Prompt.ask(
            "  Ports [dim](Enter to keep profile default)[/]", default=''
        ).strip()
        if custom_ports:
            port_spec = custom_ports

        custom_timeout = Prompt.ask(
            "  Timeout seconds [dim](Enter to keep default)[/]", default=''
        ).strip()
        if custom_timeout:
            try:
                timeout = float(custom_timeout)
            except ValueError:
                pass

        use_nvd     = Confirm.ask("  Enable NVD CVE lookups?", default=use_nvd)
        banner_grab = Confirm.ask("  Grab service banners?",   default=True)

    # Report format
    console.print()
    console.print("  [bold]Export report?[/]")
    _menu_table([
        ('1', '📄', 'JSON + Markdown', 'Machine-readable + human-readable report'),
        ('2', '📊', 'All formats',     'JSON, CSV, and Markdown'),
        ('3', '🚫', 'No report',       'Skip export (results still saved to history)'),
    ])
    fmt_choice = _pick("Format [1-3]", {'1', '2', '3'}, default='3')
    formats    = {
        '1': ['json', 'markdown'],
        '2': ['json', 'csv', 'markdown'],
        '3': [],
    }[fmt_choice]

    # Scan name
    scan_name = Prompt.ask(
        "\n  [dim]Scan name (optional, Enter to auto-generate)[/]", default=''
    ).strip() or None

    console.print()
    console.print(Rule("[dim]Running scan[/]", style="dim"))

    host_risks = run_scan(
        target       = target,
        port_spec    = port_spec,
        profile_name = profile_name,
        timeout      = timeout,
        concurrency  = concurrency,
        banner_grab  = banner_grab,
        use_nvd      = use_nvd,
        scan_name    = scan_name,
        formats      = formats,
    )

    if host_risks and sys.stdin.isatty():
        console.print()
        if Confirm.ask("  [cyan]Browse results now?[/]", default=True):
            dash.show_host_list(host_risks)

    _pause()


# ══════════════════════════════════════════════════════════════════════════════
# HISTORY MENU
# ══════════════════════════════════════════════════════════════════════════════

def _menu_history():
    history = ScanHistory()

    while True:
        _clear(); _banner()
        console.print(Rule("[bold]Scan History[/]", style="cyan"))
        console.print()

        records = history.list(limit=30)
        if not records:
            console.print("  [dim]No scans recorded yet. Run a scan first.[/]")
            _pause(); return

        # Build history table
        t = Table(
            box=box.ROUNDED, border_style="cyan", header_style="bold cyan",
            show_lines=True, expand=True,
        )
        t.add_column("ID",         width=5,  justify="right", style="bold cyan")
        t.add_column("Name",       min_width=22, style="white")
        t.add_column("Target",     min_width=15, style="dim")
        t.add_column("Profile",    width=10)
        t.add_column("Hosts",      width=7,  justify="right")
        t.add_column("Open Ports", width=11, justify="right")
        t.add_column("Timestamp",  width=19, style="dim")

        for rec in records:
            t.add_row(
                str(rec.scan_id), rec.name, rec.target, rec.profile,
                str(rec.host_count), str(rec.open_ports),
                rec.timestamp[:19].replace('T', ' '),
            )
        console.print(t)
        console.print()

        _menu_table([
            ('v', '🔍', 'View scan results', 'Browse findings for a past scan'),
            ('e', '📄', 'Export report',     'Generate JSON/CSV/Markdown for a past scan'),
            ('d', '🗑️ ', 'Delete a scan',    'Remove a scan from history'),
            ('b', '↩ ', 'Back',             'Return to the main menu'),
        ])
        console.print()

        action = _pick("Action [v/e/d/b]", {'v', 'e', 'd', 'b'}, default='b')

        if action == 'b':
            return

        elif action == 'v':
            sid = Prompt.ask("  Scan ID to view").strip()
            try:
                result = history.get(int(sid))
                if result is None:
                    dash.print_error(f"Scan ID {sid} not found."); _pause(); continue
                _, host_results = result
                host_risks = classifier.classify_all(host_results, use_nvd=False)
                dash.show_host_list(host_risks)
            except (ValueError, TypeError):
                dash.print_error("Invalid ID."); _pause()

        elif action == 'e':
            sid = Prompt.ask("  Scan ID to export").strip()
            try:
                result = history.get(int(sid))
                if result is None:
                    dash.print_error(f"Scan ID {sid} not found."); _pause(); continue
                rec, host_results = result
                host_risks = classifier.classify_all(host_results, use_nvd=False)

                console.print()
                _menu_table([
                    ('1', '📝', 'JSON + Markdown', ''),
                    ('2', '📊', 'All formats',     'JSON, CSV, Markdown'),
                    ('3', '📋', 'JSON only',       ''),
                    ('4', '📈', 'CSV only',        ''),
                    ('5', '📄', 'Markdown only',   ''),
                ])
                fc = _pick("Format [1-5]", {'1','2','3','4','5'}, '1')
                fmt_map = {
                    '1': ['json','markdown'], '2': ['json','csv','markdown'],
                    '3': ['json'], '4': ['csv'], '5': ['markdown'],
                }
                fmts = fmt_map[fc]
                paths = reporter.generate_all(host_risks, 'reports', f"scan_{sid}", target=rec.target)
                for fmt, path in paths.items():
                    if any(f in fmt for f in fmts):
                        dash.print_success(f"{fmt} → [cyan]{path}[/]")
                _pause()
            except (ValueError, TypeError):
                dash.print_error("Invalid ID."); _pause()

        elif action == 'd':
            sid = Prompt.ask("  Scan ID to delete").strip()
            try:
                if Confirm.ask(f"  [red]Delete scan {sid}? This cannot be undone.[/]", default=False):
                    history.delete(int(sid))
                    dash.print_success(f"Scan {sid} deleted.")
                    _pause()
            except (ValueError, TypeError):
                dash.print_error("Invalid ID."); _pause()


# ══════════════════════════════════════════════════════════════════════════════
# DIFF WIZARD
# ══════════════════════════════════════════════════════════════════════════════

def _wizard_diff():
    history = ScanHistory()
    records = history.list(limit=20)

    _clear(); _banner()
    console.print(Rule("[bold]Compare Two Scans[/]", style="cyan"))
    console.print()

    if len(records) < 2:
        console.print("  [dim]Need at least 2 scans in history to compare.[/]")
        _pause(); return

    # Show compact history
    t = Table(box=box.SIMPLE_HEAD, header_style="bold cyan", expand=True)
    t.add_column("ID",         width=5,  justify="right", style="bold cyan")
    t.add_column("Name",       min_width=22, style="white")
    t.add_column("Target",     style="dim")
    t.add_column("Open Ports", width=11, justify="right")
    t.add_column("Timestamp",  width=19, style="dim")
    for rec in records:
        t.add_row(
            str(rec.scan_id), rec.name, rec.target,
            str(rec.open_ports), rec.timestamp[:19].replace('T', ' '),
        )
    console.print(t)
    console.print()

    try:
        id_a = int(Prompt.ask("  [bold]First scan ID[/]  (older / baseline)"))
        id_b = int(Prompt.ask("  [bold]Second scan ID[/] (newer / comparison)"))
    except ValueError:
        dash.print_error("Invalid ID."); _pause(); return

    diff = history.diff(id_a, id_b)
    if diff is None:
        dash.print_error(f"Could not find scans {id_a} or {id_b}."); _pause(); return

    dash.show_diff(diff)
    _pause()


# ══════════════════════════════════════════════════════════════════════════════
# PROFILES VIEWER
# ══════════════════════════════════════════════════════════════════════════════

def _menu_profiles():
    _clear(); _banner()
    dash.show_profiles(profile_module.PROFILES)


# ══════════════════════════════════════════════════════════════════════════════
# QUICK SCAN  (minimal prompts — just enter target)
# ══════════════════════════════════════════════════════════════════════════════

def _wizard_quick():
    _clear(); _banner()
    console.print(Rule("[bold]Quick Scan[/] [dim](top 100 ports, fast)[/]", style="cyan"))
    console.print()
    target = Prompt.ask("  [bold]Target[/] [dim](IP, hostname, or CIDR)[/]")
    if not target.strip():
        dash.print_error("No target entered."); _pause(); return

    console.print()
    host_risks = run_scan(
        target=target, profile_name='quick',
        banner_grab=True, use_nvd=False,
    )
    if host_risks and sys.stdin.isatty():
        console.print()
        if Confirm.ask("  [cyan]Browse results now?[/]", default=True):
            dash.show_host_list(host_risks)
    _pause()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN INTERACTIVE MENU LOOP
# ══════════════════════════════════════════════════════════════════════════════

MENU_OPTIONS = [
    ('1', '⚡', 'Quick Scan',      'Scan top 100 ports — just enter a target'),
    ('2', '🔍', 'Full Scan Wizard','Choose profile, ports, NVD, reports, and more'),
    ('3', '📋', 'Scan History',    'Browse, view, export, or delete past scans'),
    ('4', '🔀', 'Compare Scans',   'Diff two historical scans — see what changed'),
    ('5', '📊', 'Scan Profiles',   'View all available scan profiles and their settings'),
    ('0', '🚪', 'Exit',            ''),
]

def interactive_menu():
    while True:
        _clear()
        console.print()
        console.print(Panel(
            "[bold cyan]▸ VulnScanner[/]  [dim]Defensive Vulnerability Assessment Tool[/]\n\n"
            "[dim]  ⚠  Only scan systems you own or have explicit written permission to scan.[/]",
            border_style="cyan", padding=(1, 3),
        ))
        console.print()
        console.print("  [bold]What would you like to do?[/]")
        console.print()

        _menu_table(MENU_OPTIONS)
        console.print()

        choice = _pick("Select [0-5]", {'0','1','2','3','4','5'})

        if   choice == '1': _wizard_quick()
        elif choice == '2': _wizard_scan()
        elif choice == '3': _menu_history()
        elif choice == '4': _wizard_diff()
        elif choice == '5': _menu_profiles()
        elif choice == '0':
            _clear()
            console.print("\n  [dim]Goodbye.[/]\n")
            break


# ══════════════════════════════════════════════════════════════════════════════
# CLI MODE  (for scripting / CI — invoked when arguments are passed)
# ══════════════════════════════════════════════════════════════════════════════

def cli_mode():
    import argparse

    p = argparse.ArgumentParser(
        prog='vulnscanner',
        description='VulnScanner — run without arguments for the interactive menu.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py scan 192.168.1.1
  python main.py scan 10.0.0.0/24 --profile full --format all
  python main.py scan example.com --ports 80,443,8080 --no-nvd --no-tui
  python main.py history
  python main.py diff 1 2
  python main.py profiles
""",
    )
    sub = p.add_subparsers(dest='command', required=True)

    s = sub.add_parser('scan')
    s.add_argument('target')
    s.add_argument('-p', '--ports',       default='')
    s.add_argument('--profile',           default='quick')
    s.add_argument('-t', '--timeout',     type=float, default=None)
    s.add_argument('-c', '--concurrency', type=int,   default=None)
    s.add_argument('--no-banner',         action='store_true')
    s.add_argument('--no-nvd',            action='store_true')
    s.add_argument('--nvd-key',           default='')
    s.add_argument('-o', '--output',      default='reports')
    s.add_argument('-f', '--format',      default='')
    s.add_argument('--name',              default='')
    s.add_argument('--no-tui',            action='store_true')

    sub.add_parser('history').set_defaults()
    sub.add_parser('profiles').set_defaults()

    d = sub.add_parser('diff')
    d.add_argument('scan_a', type=int)
    d.add_argument('scan_b', type=int)

    args = p.parse_args()

    console.print()
    console.print(dash._header())

    if args.command == 'scan':
        fmts = args.format.lower().split(',') if args.format else []
        if 'all' in fmts:
            fmts = ['json', 'csv', 'markdown']
        host_risks = run_scan(
            target       = args.target,
            port_spec    = args.ports or None,
            profile_name = args.profile,
            timeout      = args.timeout,
            concurrency  = args.concurrency,
            banner_grab  = not args.no_banner,
            use_nvd      = not args.no_nvd,
            api_key      = args.nvd_key or None,
            scan_name    = args.name or None,
            output_dir   = args.output,
            formats      = fmts,
        )
        if host_risks and not args.no_tui and sys.stdin.isatty():
            dash.show_host_list(host_risks)

    elif args.command == 'history':
        history = ScanHistory()
        dash.show_history(history.list())

    elif args.command == 'diff':
        history = ScanHistory()
        diff = history.diff(args.scan_a, args.scan_b)
        if diff is None:
            dash.print_error(f"Scans {args.scan_a} or {args.scan_b} not found.")
        else:
            dash.show_diff(diff)

    elif args.command == 'profiles':
        dash.show_profiles(profile_module.PROFILES)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    try:
        if len(sys.argv) > 1:
            cli_mode()       # arguments provided → CLI mode
        else:
            interactive_menu()   # no arguments → interactive menu
    except KeyboardInterrupt:
        console.print('\n\n  [dim]Interrupted.[/]\n')
        sys.exit(0)
    except Exception as e:
        dash.print_error(str(e))
        if os.environ.get('DEBUG'):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
