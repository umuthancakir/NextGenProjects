"""
Local vulnerability knowledge base.

Loads data/vuln_db.json and provides fast lookups by port number,
service name, or banner string.
"""

import json
import os
import re
from typing import Optional

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'vuln_db.json')

_db: Optional[dict] = None


def _load() -> dict:
    global _db
    if _db is None:
        with open(_DB_PATH, 'r') as f:
            _db = json.load(f)
    return _db


def get_port_info(port: int) -> Optional[dict]:
    """Return the full info dict for a port number, or None."""
    db = _load()
    return db['ports'].get(str(port))


def get_service_fingerprint(service_name: str) -> Optional[dict]:
    """Return fingerprint info for a detected service name."""
    db = _load()
    for key, info in db['service_fingerprints'].items():
        if key.lower() in service_name.lower() or service_name.lower() in key.lower():
            return info
    return None


def query(port: int, service: str = '', banner: str = '') -> dict:
    """
    Merge port-level DB info with service fingerprint info.

    Returns a combined dict with keys:
      service, risk_level, description, risks, recommendations,
      cve_keywords, internet_exposure
    """
    port_info = get_port_info(port) or {}
    svc_info  = get_service_fingerprint(service) if service else {}

    # Service name: detected banner > DB > empty
    svc_name = (
        service
        or port_info.get('service', '')
    )

    # Risk level: take the highest between port info and service fingerprint
    from .models import RiskLevel
    r_port = RiskLevel.from_string(port_info.get('risk_level', 'unknown'))
    r_svc  = RiskLevel.from_string(svc_info.get('risk_level',  'unknown'))
    risk   = r_port if r_port.score >= r_svc.score else r_svc

    # Merge CVE keywords (deduplicated)
    cve_kws = list({
        *port_info.get('cve_keywords', []),
        *svc_info.get('cve_keywords', []),
    })

    # If service is in the service_fingerprints, extend keywords with version info
    version_pattern = svc_info.get('version_pattern', '') if svc_info else ''
    if banner and version_pattern:
        m = re.search(version_pattern, banner, re.IGNORECASE)
        if m:
            # e.g. "OpenSSH 7.4" — useful NVD keyword
            ver = m.group(1) if m.lastindex else ''
            if ver and cve_kws:
                cve_kws.insert(0, f"{svc_name} {ver}")

    return {
        'service':           svc_name,
        'risk_level':        risk,
        'description':       port_info.get('description', ''),
        'risks':             port_info.get('risks', []),
        'recommendations':   port_info.get('recommendations', []),
        'cve_keywords':      cve_kws,
        'internet_exposure': port_info.get('internet_exposure', 'unknown'),
    }
