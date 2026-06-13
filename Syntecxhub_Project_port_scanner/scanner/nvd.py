"""
National Vulnerability Database (NVD) API v2.0 client.

Queries https://services.nvd.nist.gov/rest/json/cves/2.0 for CVEs
matching a keyword (e.g. "OpenSSH 7.4").

Rate limits (as of 2024):
  - Without API key: 5 requests / 30 seconds
  - With API key:   50 requests / 30 seconds

Results are cached in-memory for the duration of the scan to avoid
hitting the rate limit when the same service appears on multiple hosts.
"""

import time
import urllib.request
import urllib.parse
import urllib.error
import json
from typing import List, Optional

from .models import CVE

NVD_BASE = 'https://services.nvd.nist.gov/rest/json/cves/2.0'

_cache: dict[str, List[CVE]] = {}
_last_request_time: float    = 0.0
_request_count_window: int   = 0
_window_start: float         = 0.0

# Conservative rate limiting: 4 req/30s without key
_RATE_LIMIT_NO_KEY  = 4
_RATE_LIMIT_WITH_KEY = 45
_WINDOW_SECONDS     = 30


def _rate_limit(api_key: Optional[str]) -> None:
    """Sleep if necessary to stay within NVD rate limits."""
    global _request_count_window, _window_start

    limit = _RATE_LIMIT_WITH_KEY if api_key else _RATE_LIMIT_NO_KEY
    now   = time.monotonic()

    if now - _window_start > _WINDOW_SECONDS:
        _window_start         = now
        _request_count_window = 0

    if _request_count_window >= limit:
        sleep_for = _WINDOW_SECONDS - (now - _window_start) + 0.5
        if sleep_for > 0:
            time.sleep(sleep_for)
        _window_start         = time.monotonic()
        _request_count_window = 0

    _request_count_window += 1


def _parse_cvss(cve_item: dict) -> tuple[Optional[float], str]:
    """Extract the highest available CVSS score and severity from a CVE item."""
    metrics = cve_item.get('metrics', {})
    for key in ('cvssMetricV31', 'cvssMetricV30', 'cvssMetricV2'):
        entries = metrics.get(key, [])
        if entries:
            data = entries[0].get('cvssData', {})
            score    = data.get('baseScore')
            severity = data.get('baseSeverity', entries[0].get('baseSeverity', ''))
            return score, severity.lower()
    return None, ''


def lookup(
    keyword: str,
    api_key: Optional[str] = None,
    limit:   int           = 5,
) -> List[CVE]:
    """
    Return up to `limit` CVEs matching `keyword` from NVD.

    Returns an empty list on any network error so the scanner degrades
    gracefully if NVD is unreachable.
    """
    cache_key = f"{keyword}:{limit}"
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        _rate_limit(api_key)

        params = {
            'keywordSearch':  keyword,
            'resultsPerPage': min(limit, 20),
        }
        url = f"{NVD_BASE}?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(url)
        req.add_header('Accept', 'application/json')
        if api_key:
            req.add_header('apiKey', api_key)

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

    except Exception:
        _cache[cache_key] = []
        return []

    cves: List[CVE] = []
    for item in data.get('vulnerabilities', []):
        cve_data = item.get('cve', {})
        cve_id   = cve_data.get('id', '')

        descriptions = cve_data.get('descriptions', [])
        desc = next(
            (d['value'] for d in descriptions if d.get('lang') == 'en'),
            'No description available.',
        )

        score, severity = _parse_cvss(cve_data)

        cves.append(CVE(
            id          = cve_id,
            description = desc[:300] + ('…' if len(desc) > 300 else ''),
            cvss_score  = score,
            severity    = severity,
            url         = f"https://nvd.nist.gov/vuln/detail/{cve_id}",
        ))

    cves.sort(key=lambda c: c.cvss_score or 0, reverse=True)
    _cache[cache_key] = cves[:limit]
    return _cache[cache_key]


def lookup_for_port(
    port:    int,
    service: str,
    version: str,
    cve_keywords: list,
    api_key: Optional[str] = None,
    limit:   int = 5,
) -> List[CVE]:
    """
    Convenience wrapper: builds the best keyword string for a port/service/version
    and queries NVD. Uses the most specific keyword available.
    """
    if not cve_keywords:
        return []

    # Try specific version first (most targeted)
    if version and cve_keywords:
        q = f"{cve_keywords[0]} {version}"
        results = lookup(q, api_key=api_key, limit=limit)
        if results:
            return results

    # Fall back to service name
    for kw in cve_keywords[:2]:
        results = lookup(kw, api_key=api_key, limit=limit)
        if results:
            return results

    return []
