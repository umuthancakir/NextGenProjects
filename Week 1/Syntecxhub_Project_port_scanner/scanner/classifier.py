"""
Risk classification engine.

Combines local vulnerability DB info, NVD CVE data, and port/service
context into a final RiskLevel for each port, plus an aggregate
host-level risk score.
"""

from typing import List, Optional

from .models import CVE, HostResult, HostRisk, PortResult, PortRisk, RiskLevel
from . import vuln_db as vdb
from . import nvd as nvd_client


# Ports that should NEVER be internet-facing — always CRITICAL if open
_NEVER_INTERNET = {23, 111, 135, 139, 445, 2049, 2375, 4444, 6379,
                   9200, 11211, 27017, 27018, 28017}

# Ports where an open finding alone is HIGH risk regardless of banner
_INHERENTLY_HIGH = {21, 23, 139, 389, 445, 514, 873, 1433, 1723, 2049,
                    3306, 3389, 5432, 5900, 5984, 6379, 9200, 11211,
                    27017, 27018}


def _cvss_to_risk(score: Optional[float]) -> RiskLevel:
    if score is None:
        return RiskLevel.UNKNOWN
    if score >= 9.0:
        return RiskLevel.CRITICAL
    if score >= 7.0:
        return RiskLevel.HIGH
    if score >= 4.0:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _cves_max_risk(cves: List[CVE]) -> RiskLevel:
    if not cves:
        return RiskLevel.UNKNOWN
    return max((_cvss_to_risk(c.cvss_score) for c in cves), default=RiskLevel.UNKNOWN)


def classify_port(
    port_result: PortResult,
    api_key:     Optional[str] = None,
    use_nvd:     bool          = True,
) -> PortRisk:
    """
    Classify a single open port result and return a PortRisk.
    """
    info = vdb.query(
        port=port_result.port,
        service=port_result.service,
        banner=port_result.banner,
    )

    db_risk: RiskLevel = info['risk_level']

    # Automatic CRITICAL override for well-known dangerous open ports
    if port_result.port in _NEVER_INTERNET:
        db_risk = RiskLevel.CRITICAL

    # Fetch CVEs from NVD if requested
    cves: List[CVE] = []
    if use_nvd and info['cve_keywords']:
        cves = nvd_client.lookup_for_port(
            port    = port_result.port,
            service = port_result.service,
            version = port_result.version,
            cve_keywords = info['cve_keywords'],
            api_key = api_key,
            limit   = 5,
        )

    nvd_risk = _cves_max_risk(cves)
    final_risk = db_risk if db_risk.score >= nvd_risk.score else nvd_risk

    # If still UNKNOWN, fall back to MEDIUM (open port = at least some risk)
    if final_risk == RiskLevel.UNKNOWN:
        final_risk = RiskLevel.LOW

    return PortRisk(
        port_result     = port_result,
        risk_level      = final_risk,
        service_name    = info['service'] or port_result.service or f"Port {port_result.port}",
        description     = info['description'],
        risks           = info['risks'],
        recommendations = info['recommendations'],
        cves            = cves,
        internet_exposure = info['internet_exposure'],
    )


def classify_host(
    host_result: HostResult,
    api_key:     Optional[str] = None,
    use_nvd:     bool          = True,
) -> HostRisk:
    """
    Classify all open ports on a host and compute an aggregate risk score.
    """
    port_risks = [
        classify_port(pr, api_key=api_key, use_nvd=use_nvd)
        for pr in host_result.ports
    ]

    # Aggregate score: sum of per-port risk scores, capped at 100
    if port_risks:
        raw_score = sum(pr.risk_level.score * 4 for pr in port_risks)
        risk_score = min(raw_score, 100)
        overall   = max((pr.risk_level for pr in port_risks), default=RiskLevel.UNKNOWN)
    else:
        risk_score = 0
        overall    = RiskLevel.INFO

    critical_count = sum(1 for pr in port_risks if pr.risk_level == RiskLevel.CRITICAL)
    high_count     = sum(1 for pr in port_risks if pr.risk_level == RiskLevel.HIGH)
    open_count     = len(port_risks)

    if overall == RiskLevel.CRITICAL:
        summary = (
            f"{open_count} open ports — {critical_count} CRITICAL "
            f"(requires immediate attention)"
        )
    elif overall == RiskLevel.HIGH:
        summary = (
            f"{open_count} open ports — {high_count} HIGH risk "
            f"(review and harden soon)"
        )
    elif open_count == 0:
        summary = "No open ports found."
    else:
        summary = f"{open_count} open ports — risk level {overall.label.upper()}"

    return HostRisk(
        host_result  = host_result,
        port_risks   = port_risks,
        overall_risk = overall,
        risk_score   = risk_score,
        summary      = summary,
    )


def classify_all(
    host_results: List[HostResult],
    api_key:      Optional[str] = None,
    use_nvd:      bool          = True,
    progress_cb   = None,
) -> List[HostRisk]:
    """Classify a list of HostResults. Calls progress_cb(host) after each host."""
    results = []
    for hr in host_results:
        classified = classify_host(hr, api_key=api_key, use_nvd=use_nvd)
        results.append(classified)
        if progress_cb:
            progress_cb(hr.host)
    return results
