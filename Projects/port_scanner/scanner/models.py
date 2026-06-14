"""Shared data model dataclasses used across all scanner modules."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class RiskLevel(Enum):
    CRITICAL = ("critical", 5)
    HIGH     = ("high",     4)
    MEDIUM   = ("medium",   3)
    LOW      = ("low",      2)
    INFO     = ("info",     1)
    UNKNOWN  = ("unknown",  0)

    def __init__(self, label: str, score: int):
        self.label = label
        self.score = score

    @classmethod
    def from_string(cls, s: str) -> "RiskLevel":
        s = s.lower()
        for member in cls:
            if member.label == s:
                return member
        return cls.UNKNOWN

    def __lt__(self, other):
        return self.score < other.score

    def rich_style(self) -> str:
        styles = {
            "critical": "bold red",
            "high":     "red",
            "medium":   "yellow",
            "low":      "green",
            "info":     "dim",
            "unknown":  "dim",
        }
        return styles.get(self.label, "dim")


@dataclass
class PortResult:
    port:       int
    state:      str              # open / closed / filtered
    service:    str  = ''
    banner:     str  = ''
    version:    str  = ''
    latency_ms: float = 0.0


@dataclass
class HostResult:
    host:          str
    ip:            str             = ''
    ports:         List[PortResult] = field(default_factory=list)
    scan_duration: float            = 0.0
    timestamp:     str              = ''


@dataclass
class CVE:
    id:          str
    description: str
    cvss_score:  Optional[float] = None
    severity:    str             = ''
    url:         str             = ''


@dataclass
class PortRisk:
    port_result:     PortResult
    risk_level:      RiskLevel
    service_name:    str              = ''
    description:     str              = ''
    risks:           List[str]        = field(default_factory=list)
    recommendations: List[str]        = field(default_factory=list)
    cves:            List[CVE]        = field(default_factory=list)
    internet_exposure: str            = ''


@dataclass
class HostRisk:
    host_result:  HostResult
    port_risks:   List[PortRisk]     = field(default_factory=list)
    overall_risk: RiskLevel          = RiskLevel.UNKNOWN
    risk_score:   int                = 0
    summary:      str                = ''
