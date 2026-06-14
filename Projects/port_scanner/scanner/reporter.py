"""
Report generation — exports scan results as JSON, CSV, or Markdown.

Each report includes:
  - Summary: hosts scanned, open ports, breakdown by severity
  - Per-host detail: port table, service info, CVEs, recommendations
"""

import csv
import json
import os
import datetime
from typing import List

from .models import HostRisk, PortRisk, RiskLevel


def _timestamp() -> str:
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')


def _risk_counts(host_risks: List[HostRisk]) -> dict:
    counts = {rl.label: 0 for rl in RiskLevel}
    for hr in host_risks:
        for pr in hr.port_risks:
            counts[pr.risk_level.label] += 1
    return counts


# ── JSON ──────────────────────────────────────────────────────────────────────

def generate_json(host_risks: List[HostRisk], output_path: str) -> str:
    def _port_risk(pr: PortRisk) -> dict:
        return {
            'port':            pr.port_result.port,
            'service':         pr.service_name,
            'version':         pr.port_result.version,
            'banner_snippet':  pr.port_result.banner[:120],
            'state':           pr.port_result.state,
            'latency_ms':      pr.port_result.latency_ms,
            'risk_level':      pr.risk_level.label,
            'description':     pr.description,
            'risks':           pr.risks,
            'recommendations': pr.recommendations,
            'internet_exposure': pr.internet_exposure,
            'cves': [
                {'id': c.id, 'description': c.description,
                 'cvss_score': c.cvss_score, 'severity': c.severity, 'url': c.url}
                for c in pr.cves
            ],
        }

    def _host_risk(hr: HostRisk) -> dict:
        return {
            'host':         hr.host_result.host,
            'ip':           hr.host_result.ip,
            'overall_risk': hr.overall_risk.label,
            'risk_score':   hr.risk_score,
            'summary':      hr.summary,
            'scan_duration_s': hr.host_result.scan_duration,
            'timestamp':    hr.host_result.timestamp,
            'open_ports':   [_port_risk(pr) for pr in hr.port_risks],
        }

    counts = _risk_counts(host_risks)
    report = {
        'generated_at':    datetime.datetime.now().isoformat(),
        'hosts_scanned':   len(host_risks),
        'total_open_ports': sum(len(hr.port_risks) for hr in host_risks),
        'severity_breakdown': counts,
        'hosts': [_host_risk(hr) for hr in host_risks],
    }

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    return output_path


# ── CSV ───────────────────────────────────────────────────────────────────────

def generate_csv(host_risks: List[HostRisk], output_path: str) -> str:
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    fields = [
        'host', 'ip', 'port', 'service', 'version', 'state',
        'risk_level', 'latency_ms', 'internet_exposure',
        'description', 'top_cve', 'cvss_score',
    ]
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for hr in host_risks:
            for pr in hr.port_risks:
                top_cve  = pr.cves[0].id if pr.cves else ''
                top_cvss = pr.cves[0].cvss_score if pr.cves else ''
                writer.writerow({
                    'host':             hr.host_result.host,
                    'ip':               hr.host_result.ip,
                    'port':             pr.port_result.port,
                    'service':          pr.service_name,
                    'version':          pr.port_result.version,
                    'state':            pr.port_result.state,
                    'risk_level':       pr.risk_level.label,
                    'latency_ms':       pr.port_result.latency_ms,
                    'internet_exposure': pr.internet_exposure,
                    'description':      pr.description[:100],
                    'top_cve':          top_cve,
                    'cvss_score':       top_cvss,
                })
    return output_path


# ── Markdown ──────────────────────────────────────────────────────────────────

_RISK_EMOJI = {
    'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢', 'info': '⚪',
}


def generate_markdown(host_risks: List[HostRisk], output_path: str, target: str = '') -> str:
    lines = []
    now   = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    counts = _risk_counts(host_risks)

    lines += [
        '# Security Scan Report',
        '',
        f'**Generated:** {now}  ',
        f'**Target:** `{target or "multiple hosts"}`  ',
        f'**Hosts Scanned:** {len(host_risks)}  ',
        f'**Total Open Ports:** {sum(len(hr.port_risks) for hr in host_risks)}',
        '',
        '## Severity Summary',
        '',
        '| Severity | Count |',
        '|----------|-------|',
    ]
    for rl in [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW, RiskLevel.INFO]:
        emoji = _RISK_EMOJI.get(rl.label, '')
        lines.append(f'| {emoji} {rl.label.upper()} | {counts.get(rl.label, 0)} |')

    lines += ['', '---', '', '## Host Findings', '']

    for hr in host_risks:
        emoji = _RISK_EMOJI.get(hr.overall_risk.label, '⚪')
        lines += [
            f'### {emoji} {hr.host_result.host} ({hr.host_result.ip})',
            '',
            f'**Overall Risk:** {hr.overall_risk.label.upper()}  ',
            f'**Risk Score:** {hr.risk_score}/100  ',
            f'**Summary:** {hr.summary}  ',
            f'**Scan Duration:** {hr.host_result.scan_duration}s',
            '',
        ]

        if not hr.port_risks:
            lines.append('_No open ports found._')
            lines.append('')
            continue

        lines += [
            '| Port | Service | Version | Risk | Exposure |',
            '|------|---------|---------|------|----------|',
        ]
        for pr in hr.port_risks:
            e = _RISK_EMOJI.get(pr.risk_level.label, '')
            lines.append(
                f'| {pr.port_result.port} | {pr.service_name} | {pr.port_result.version or "—"} '
                f'| {e} {pr.risk_level.label.upper()} | {pr.internet_exposure} |'
            )

        lines.append('')

        for pr in hr.port_risks:
            if pr.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH) or pr.cves:
                e = _RISK_EMOJI.get(pr.risk_level.label, '')
                lines += [
                    f'#### {e} Port {pr.port_result.port} — {pr.service_name}',
                    '',
                ]
                if pr.description:
                    lines += [pr.description, '']
                if pr.risks:
                    lines.append('**Risks:**')
                    for r in pr.risks:
                        lines.append(f'- {r}')
                    lines.append('')
                if pr.recommendations:
                    lines.append('**Recommendations:**')
                    for r in pr.recommendations:
                        lines.append(f'- {r}')
                    lines.append('')
                if pr.cves:
                    lines.append('**CVEs (from NVD):**')
                    for cve in pr.cves[:5]:
                        score_str = f'CVSS {cve.cvss_score}' if cve.cvss_score else ''
                        lines.append(f'- [{cve.id}]({cve.url}) {score_str} — {cve.description[:120]}')
                    lines.append('')

        lines += ['---', '']

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    return output_path


def generate_all(
    host_risks: List[HostRisk],
    output_dir: str,
    name:       str,
    target:     str = '',
) -> dict[str, str]:
    """Generate JSON + CSV + Markdown reports. Returns {format: path}."""
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.join(output_dir, name)
    return {
        'json':     generate_json(host_risks,     f"{base}.json"),
        'csv':      generate_csv(host_risks,      f"{base}.csv"),
        'markdown': generate_markdown(host_risks, f"{base}.md", target=target),
    }
