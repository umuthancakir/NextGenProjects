"""
Cybersecurity Expert System — Inference Engine
Implements MYCIN-style certainty factors, forward & backward chaining,
keyword-based NL extraction, conflict resolution, and feedback learning.
"""

from __future__ import annotations
import re, json, math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

THRESHOLD  = 0.20   # minimum CF to consider a fact "known"
LEARN_FILE = Path(__file__).parent / "data" / "learning.json"

# ══════════════════════════════════════════════════════════════════════════════
# Data classes
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Rule:
    id:           str
    antecedents:  list[str]          # fact IDs that must hold
    conclusion:   str                # fact ID derived
    cf:           float              # certainty factor  [−1, 1]
    priority:     int   = 5          # 1–10; higher fires first in conflicts
    label:        str   = ""         # human-readable description
    domain:       str   = "general"

    @property
    def specificity(self) -> int:
        return len(self.antecedents)


@dataclass
class FiredRule:
    rule:            Rule
    antecedent_cfs:  dict[str, float]
    conclusion_cf:   float


@dataclass
class ConflictEvent:
    conclusion:   str
    rule_a:       Rule
    rule_b:       Rule
    winner:       Rule
    reason:       str


# ══════════════════════════════════════════════════════════════════════════════
# Certainty-factor algebra  (MYCIN-style)
# ══════════════════════════════════════════════════════════════════════════════

def cf_combine(cf1: float, cf2: float) -> float:
    """Combine two CF values that support the same hypothesis."""
    if cf1 >= 0 and cf2 >= 0:
        return cf1 + cf2 * (1.0 - cf1)
    if cf1 < 0 and cf2 < 0:
        return cf1 + cf2 * (1.0 + cf1)
    return (cf1 + cf2) / (1.0 - min(abs(cf1), abs(cf2)) + 1e-9)


def cf_rule(rule: Rule, wm: dict[str, float]) -> float:
    """Compute the CF a rule adds to its conclusion given working memory."""
    min_ant = min(wm.get(a, 0.0) for a in rule.antecedents)
    return rule.cf * min_ant


# ══════════════════════════════════════════════════════════════════════════════
# Knowledge base — cybersecurity domain
# ══════════════════════════════════════════════════════════════════════════════

FACT_LABELS: dict[str, str] = {
    # ── Observable facts ────────────────────────────────────────────────────
    "network_anomaly":       "Unusual network traffic",
    "failed_auth":           "Multiple failed logins",
    "privilege_escalation":  "Privilege escalation detected",
    "data_exfiltration":     "Large outbound data transfer",
    "ransomware_indicators": "Ransomware indicators (encrypt/ransom note)",
    "phishing_email":        "Phishing/spoofed email detected",
    "system_slowdown":       "Unexplained system slowdown",
    "high_cpu_usage":        "CPU spike without known cause",
    "unusual_processes":     "Unknown processes running",
    "file_modification":     "Critical system files changed",
    "log_tampering":         "Security logs modified / deleted",
    "lateral_movement":      "Internal lateral movement",
    "c2_communication":      "C2 server contact",
    "port_scanning":         "Port-scanning activity",
    "dns_anomaly":           "Anomalous DNS queries",
    "insider_access":        "Authorised user acting suspiciously",
    "vulnerability_scan":    "Vulnerability / exploit scan",
    "email_spoofing":        "Email sender forgery",
    # ── Intermediate derived facts ───────────────────────────────────────────
    "active_intrusion":      "Active intrusion in progress",
    "credential_attack":     "Credential-based attack",
    "data_theft_attempt":    "Data theft attempt",
    # ── Final diagnoses ──────────────────────────────────────────────────────
    "malware_infection":     "Malware Infection",
    "ransomware_attack":     "Ransomware Attack",
    "apt_attack":            "Advanced Persistent Threat (APT)",
    "brute_force_attack":    "Brute-Force / Credential Stuffing",
    "insider_threat":        "Insider Threat",
    "ddos_attack":           "DDoS Attack",
    "phishing_campaign":     "Phishing Campaign",
    "cryptojacking":         "Cryptojacking",
    "data_breach":           "Data Breach",
    "supply_chain_attack":   "Supply-Chain Attack",
}

FACT_CATEGORIES: dict[str, str] = {
    **{k: "observable" for k in [
        "network_anomaly","failed_auth","privilege_escalation","data_exfiltration",
        "ransomware_indicators","phishing_email","system_slowdown","high_cpu_usage",
        "unusual_processes","file_modification","log_tampering","lateral_movement",
        "c2_communication","port_scanning","dns_anomaly","insider_access",
        "vulnerability_scan","email_spoofing",
    ]},
    **{k: "intermediate" for k in ["active_intrusion","credential_attack","data_theft_attempt"]},
    **{k: "diagnosis" for k in [
        "malware_infection","ransomware_attack","apt_attack","brute_force_attack",
        "insider_threat","ddos_attack","phishing_campaign","cryptojacking",
        "data_breach","supply_chain_attack",
    ]},
}

DIAGNOSIS_FACTS = {f for f, c in FACT_CATEGORIES.items() if c == "diagnosis"}

RULES: list[Rule] = [
    # ── Intermediate derivations ─────────────────────────────────────────────
    Rule("R01", ["network_anomaly","c2_communication"],         "active_intrusion",   0.88, 7, "Network anomaly + C2 contact → active intrusion"),
    Rule("R02", ["failed_auth","vulnerability_scan"],           "credential_attack",  0.82, 7, "Failed logins + vuln scan → credential attack"),
    Rule("R03", ["data_exfiltration","lateral_movement"],       "data_theft_attempt", 0.85, 7, "Exfiltration + lateral movement → data theft attempt"),

    # ── Malware ──────────────────────────────────────────────────────────────
    Rule("R04", ["active_intrusion","unusual_processes"],       "malware_infection",  0.85, 8, "Active intrusion + unknown processes → malware"),
    Rule("R05", ["unusual_processes","file_modification","c2_communication"], "malware_infection", 0.90, 9, "Unknown procs + file mod + C2 → malware (high specificity)"),
    Rule("R06", ["system_slowdown","unusual_processes"],        "malware_infection",  0.60, 5, "Slowdown + unknown processes → possible malware"),

    # ── Ransomware ───────────────────────────────────────────────────────────
    Rule("R07", ["ransomware_indicators","file_modification"],  "ransomware_attack",  0.92, 9, "Ransom indicators + file changes → ransomware"),
    Rule("R08", ["ransomware_indicators","network_anomaly"],    "ransomware_attack",  0.80, 8, "Ransom indicators + network anomaly → ransomware"),

    # ── APT ──────────────────────────────────────────────────────────────────
    Rule("R09", ["active_intrusion","data_theft_attempt","log_tampering"],   "apt_attack", 0.88, 9, "Intrusion + data theft + log tampering → APT"),
    Rule("R10", ["lateral_movement","c2_communication","privilege_escalation"], "apt_attack", 0.85, 9, "Lateral movement + C2 + privesc → APT"),
    Rule("R11", ["data_exfiltration","file_modification","dns_anomaly"],     "apt_attack", 0.75, 7, "Exfiltration + file mod + DNS anomaly → APT"),

    # ── Brute force ──────────────────────────────────────────────────────────
    Rule("R12", ["credential_attack"],                          "brute_force_attack", 0.82, 7, "Credential attack → brute force"),
    Rule("R13", ["failed_auth","port_scanning"],                "brute_force_attack", 0.75, 7, "Failed logins + port scanning → brute force"),

    # ── Insider threat ───────────────────────────────────────────────────────
    Rule("R14", ["insider_access","data_exfiltration"],         "insider_threat",     0.80, 8, "Suspicious insider + exfiltration → insider threat"),
    Rule("R15", ["insider_access","log_tampering"],             "insider_threat",     0.85, 8, "Suspicious insider + log tampering → insider threat"),
    Rule("R16", ["insider_access","privilege_escalation","data_exfiltration"], "insider_threat", 0.90, 9, "Insider + privesc + exfiltration → insider threat (high spec.)"),

    # ── DDoS ────────────────────────────────────────────────────────────────
    Rule("R17", ["network_anomaly","system_slowdown","port_scanning"], "ddos_attack", 0.83, 8, "Network flood + slowdown + port scan → DDoS"),

    # ── Phishing ────────────────────────────────────────────────────────────
    Rule("R18", ["phishing_email","email_spoofing"],            "phishing_campaign",  0.87, 8, "Phishing email + spoofed sender → phishing campaign"),
    Rule("R19", ["phishing_email","credential_attack"],         "phishing_campaign",  0.80, 7, "Phishing + credential attack → phishing campaign"),
    Rule("R20", ["email_spoofing"],                             "phishing_campaign",  0.60, 5, "Email spoofing alone → possible phishing"),

    # ── Cryptojacking ───────────────────────────────────────────────────────
    Rule("R21", ["high_cpu_usage","network_anomaly","unusual_processes"], "cryptojacking", 0.82, 8, "CPU spike + network + unknown procs → cryptojacking"),
    Rule("R22", ["high_cpu_usage","dns_anomaly"],               "cryptojacking",      0.65, 6, "CPU spike + DNS anomaly → possible cryptojacking"),

    # ── Data breach ─────────────────────────────────────────────────────────
    Rule("R23", ["data_theft_attempt","privilege_escalation"],  "data_breach",        0.85, 8, "Data theft attempt + privesc → data breach"),
    Rule("R24", ["data_exfiltration","credential_attack"],      "data_breach",        0.80, 8, "Exfiltration + credential attack → data breach"),

    # ── Supply chain ────────────────────────────────────────────────────────
    Rule("R25", ["file_modification","unusual_processes","vulnerability_scan"], "supply_chain_attack", 0.75, 8, "File mod + unknown procs + vuln scan → supply chain"),
    Rule("R26", ["dns_anomaly","c2_communication","log_tampering"],             "supply_chain_attack", 0.80, 8, "DNS anomaly + C2 + log tampering → supply chain"),
]

# ── NLP keyword patterns ────────────────────────────────────────────────────
NL_PATTERNS: dict[str, dict] = {
    "network_anomaly": {
        "regex": [r"(unusual|suspicious|abnormal|unexpected).{0,25}(traffic|network|packet|bandwidth|connection)",
                  r"(network|traffic|bandwidth).{0,25}(spike|surge|flood|anomal|weird|high)"],
        "keywords": ["network spike","traffic anomaly","unusual traffic","suspicious connection",
                     "bandwidth surge","network flood","abnormal traffic","high traffic"],
        "base_cf": 0.80,
    },
    "failed_auth": {
        "regex": [r"(failed|multiple|repeated).{0,20}(login|auth|password|attempt)",
                  r"(brute.?force|credential.?stuffing|password.?attack)"],
        "keywords": ["failed login","login failure","authentication failed","password attempt",
                     "brute force","too many logins","login attempts"],
        "base_cf": 0.85,
    },
    "privilege_escalation": {
        "regex": [r"(privilege|permission|admin|root|sudo).{0,20}(escalat|gain|grant|change|unexpected)",
                  r"(unexpect|unauthori).{0,20}(admin|root|privilege|permission)"],
        "keywords": ["privilege escalation","gained admin","root access","sudo abuse",
                     "unexpected permissions","permission change"],
        "base_cf": 0.85,
    },
    "data_exfiltration": {
        "regex": [r"(large|huge|massive|unusual).{0,20}(data|file|upload|outbound|transfer|sent)",
                  r"(data|file).{0,15}(leak|exfil|stolen|transfer).{0,15}(out|external|foreign)"],
        "keywords": ["data exfiltration","data leak","outbound transfer","data stolen",
                     "large upload","suspicious upload","files transferred out"],
        "base_cf": 0.80,
    },
    "ransomware_indicators": {
        "regex": [r"(ransom|encrypt).{0,20}(file|note|demand|message|key)",
                  r"(file|folder).{0,20}(encrypt|lock|scrambl|corrupt)"],
        "keywords": ["ransomware","ransom note","encrypted files","files locked","crypto locker",
                     "pay ransom","file encryption","decryption key"],
        "base_cf": 0.90,
    },
    "phishing_email": {
        "regex": [r"(phish|suspect|spam|malicious).{0,20}(email|mail|message|link)",
                  r"(email|mail).{0,20}(phish|scam|fake|fraud|suspicious)"],
        "keywords": ["phishing email","phishing link","suspicious email","malicious email",
                     "email scam","fake email","spam campaign"],
        "base_cf": 0.80,
    },
    "system_slowdown": {
        "regex": [r"(system|computer|server|device).{0,20}(slow|sluggish|unresponsive|hang|freeze)",
                  r"(slow|sluggish|lag).{0,20}(performance|response|system|computer)"],
        "keywords": ["system slow","slowdown","performance degraded","system unresponsive",
                     "computer slow","sluggish","system hanging"],
        "base_cf": 0.70,
    },
    "high_cpu_usage": {
        "regex": [r"(cpu|processor|processing).{0,20}(high|spike|100|max|overload|unusual)",
                  r"(high|excessive|unusual).{0,20}(cpu|processor|compute)"],
        "keywords": ["high cpu","cpu spike","100% cpu","cpu maxed","processor overload",
                     "cpu usage high","cpu at max","processor spike"],
        "base_cf": 0.75,
    },
    "unusual_processes": {
        "regex": [r"(unknown|suspicious|unusual|strange|unexpected).{0,20}(process|program|executable|app)",
                  r"(process|program|task).{0,20}(unknown|not recogni|suspicious|weird)"],
        "keywords": ["unknown process","suspicious process","strange program","unexpected executable",
                     "unrecognized program","mystery process","weird process running"],
        "base_cf": 0.80,
    },
    "file_modification": {
        "regex": [r"(system|critical|important).{0,20}(file|config|setting).{0,20}(changed|modified|altered|tampered)",
                  r"(file|config).{0,20}(tamper|modify|alter|change).{0,20}(unexpect|unauthori|suspicious)"],
        "keywords": ["file modified","config changed","system file altered","tampered file",
                     "file tampering","unauthorized change","modified system file"],
        "base_cf": 0.80,
    },
    "log_tampering": {
        "regex": [r"(log|audit|event).{0,20}(delet|clear|tamper|modify|missing|wipe)",
                  r"(security|event|system).{0,20}log.{0,20}(gone|missing|clear|delet|tamper)"],
        "keywords": ["log deleted","logs cleared","log tampering","audit log missing",
                     "logs wiped","event log cleared","security log deleted"],
        "base_cf": 0.85,
    },
    "lateral_movement": {
        "regex": [r"(lateral|internal|network).{0,20}(movement|spread|hop|pivot|jump)",
                  r"(connected|access).{0,20}(other|multiple|different).{0,20}(system|server|machine|host)"],
        "keywords": ["lateral movement","network pivot","internal spread","moving laterally",
                     "accessed other systems","hopping machines","internal compromise spread"],
        "base_cf": 0.82,
    },
    "c2_communication": {
        "regex": [r"(command.and.control|c2|c&c|beacon|callback).{0,20}(server|commun|contact|traffic)",
                  r"(contact|commun).{0,20}(known.malicious|blacklist|threat.intel|c2)"],
        "keywords": ["c2 server","command and control","c&c communication","beacon traffic",
                     "malicious server contact","threat intel hit","blacklisted ip"],
        "base_cf": 0.90,
    },
    "port_scanning": {
        "regex": [r"(port.?scan|nmap|masscan|port.{0,10}probe)",
                  r"(multiple|many|numerous).{0,20}port.{0,20}(attempt|connection|probe|request)"],
        "keywords": ["port scan","port scanning","nmap","port probe","network scan",
                     "scanning ports","port enumeration"],
        "base_cf": 0.82,
    },
    "dns_anomaly": {
        "regex": [r"(dns|domain).{0,20}(anomal|unusual|suspicious|tunnel|fast.?flux|weird|strange)",
                  r"(unusual|high).{0,20}dns.{0,20}(query|request|lookup|traffic)"],
        "keywords": ["dns anomaly","dns tunneling","suspicious dns","fast flux","unusual dns",
                     "dns exfiltration","high dns queries","weird dns"],
        "base_cf": 0.75,
    },
    "insider_access": {
        "regex": [r"(authoris|legitimate|valid|employee|staff|user).{0,25}(suspicious|unusual|strange|unexpect).{0,20}(access|behav|action)",
                  r"(insider|employee|staff|user).{0,20}(access|download|copy).{0,20}(sensitive|confidential|restricted)"],
        "keywords": ["suspicious employee","insider access","staff anomaly","trusted user suspicious",
                     "employee downloading","insider behavior","authorized but suspicious"],
        "base_cf": 0.75,
    },
    "vulnerability_scan": {
        "regex": [r"(exploit|cve|vulnerability|vuln).{0,20}(attempt|scan|probe|attack|trigger)",
                  r"(scan|probe).{0,20}(vulnerability|exploit|weakness)"],
        "keywords": ["vulnerability scan","exploit attempt","cve exploit","vuln probe",
                     "scanning for vulnerabilities","exploit scan","attack probe"],
        "base_cf": 0.80,
    },
    "email_spoofing": {
        "regex": [r"(spoof|fake|forg).{0,20}(email|sender|from|address|domain)",
                  r"(email|sender).{0,20}(spoof|forg|fake|impersonat)"],
        "keywords": ["email spoofing","spoofed sender","forged email","fake sender",
                     "impersonation email","domain spoofing","sender forgery"],
        "base_cf": 0.80,
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# Natural-language parser
# ══════════════════════════════════════════════════════════════════════════════

class NLParser:
    """Extract cybersecurity facts and confidence scores from natural text."""

    def parse(self, text: str) -> dict[str, float]:
        findings: dict[str, float] = {}
        low = text.lower()
        for fact_id, cfg in NL_PATTERNS.items():
            cf = 0.0
            for pat in cfg["regex"]:
                if re.search(pat, low):
                    cf = cf_combine(cf, cfg["base_cf"])
            for kw in cfg["keywords"]:
                if kw in low:
                    cf = cf_combine(cf, cfg["base_cf"] * 0.9)
            if cf >= THRESHOLD:
                findings[fact_id] = round(min(cf, 1.0), 3)
        return findings

    def explain_extraction(self, text: str) -> list[tuple[str, str, float]]:
        """Return (fact_id, matching_trigger, cf) triples for display."""
        results = []
        low = text.lower()
        for fact_id, cfg in NL_PATTERNS.items():
            for pat in cfg["regex"]:
                m = re.search(pat, low)
                if m:
                    results.append((fact_id, f"regex: «{m.group()}»", cfg["base_cf"]))
                    break
            else:
                for kw in cfg["keywords"]:
                    if kw in low:
                        results.append((fact_id, f"keyword: «{kw}»", cfg["base_cf"] * 0.9))
                        break
        return results


# ══════════════════════════════════════════════════════════════════════════════
# Inference engine
# ══════════════════════════════════════════════════════════════════════════════

class InferenceEngine:
    def __init__(self, rules: list[Rule] | None = None):
        self.rules = rules or RULES
        self._load_learned()

    # ── Learning persistence ────────────────────────────────────────────────
    def _load_learned(self) -> None:
        LEARN_FILE.parent.mkdir(exist_ok=True)
        try:
            data = json.loads(LEARN_FILE.read_text())
            adj  = data.get("adjustments", {})
            for rule in self.rules:
                if rule.id in adj:
                    rule.cf = max(-1.0, min(1.0, rule.cf + adj[rule.id]))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def record_feedback(self, diagnosis: str, correct: bool) -> None:
        """Adjust CF of rules that concluded `diagnosis`."""
        LEARN_FILE.parent.mkdir(exist_ok=True)
        try:
            data = json.loads(LEARN_FILE.read_text())
        except Exception:
            data = {"adjustments": {}, "history": []}
        delta = 0.03 if correct else -0.05
        for rule in self.rules:
            if rule.conclusion == diagnosis:
                cur = data["adjustments"].get(rule.id, 0.0)
                data["adjustments"][rule.id] = round(cur + delta, 4)
                rule.cf = max(-1.0, min(1.0, rule.cf + delta))
        data["history"].append({"diagnosis": diagnosis, "correct": correct})
        LEARN_FILE.write_text(json.dumps(data, indent=2))

    def get_learning_stats(self) -> dict:
        try:
            data = json.loads(LEARN_FILE.read_text())
            hist  = data.get("history", [])
            adj   = data.get("adjustments", {})
            total = len(hist)
            correct = sum(1 for h in hist if h["correct"])
            return {"total": total, "correct": correct,
                    "accuracy": correct/total if total else None,
                    "adjustments": adj}
        except Exception:
            return {"total": 0, "correct": 0, "accuracy": None, "adjustments": {}}

    # ── Forward chaining ────────────────────────────────────────────────────
    def forward_chain(self, wm: dict[str, float]) -> tuple[dict[str, float], list[FiredRule], list[ConflictEvent]]:
        wm         = dict(wm)
        fired      : list[FiredRule]      = []
        conflicts  : list[ConflictEvent]  = []
        fired_ids  : set[str]             = set()

        changed = True
        while changed:
            changed  = False
            eligible = [
                r for r in self.rules
                if r.id not in fired_ids
                and all(wm.get(a, 0.0) >= THRESHOLD for a in r.antecedents)
            ]
            # Sort by (priority DESC, specificity DESC) for conflict resolution
            eligible.sort(key=lambda r: (r.priority, r.specificity), reverse=True)

            # Detect conflicts: multiple rules firing for same conclusion this cycle
            by_conclusion: dict[str, list[Rule]] = {}
            for r in eligible:
                by_conclusion.setdefault(r.conclusion, []).append(r)
            for conc, competing in by_conclusion.items():
                if len(competing) > 1:
                    winner = competing[0]
                    for loser in competing[1:]:
                        reason = ("higher priority" if winner.priority > loser.priority
                                  else "greater specificity")
                        conflicts.append(ConflictEvent(conc, winner, loser, winner, reason))

            for rule in eligible:
                new_cf = cf_rule(rule, wm)
                if new_cf < THRESHOLD:
                    continue
                old_cf  = wm.get(rule.conclusion)
                final_cf = cf_combine(old_cf, new_cf) if old_cf is not None else new_cf
                wm[rule.conclusion] = round(final_cf, 4)
                fired.append(FiredRule(rule, {a: wm[a] for a in rule.antecedents}, round(new_cf, 4)))
                fired_ids.add(rule.id)
                changed = True

        return wm, fired, conflicts

    # ── Backward chaining ───────────────────────────────────────────────────
    def backward_chain(
        self, goal: str, wm: dict[str, float],
        depth: int = 0, visited: set[str] | None = None
    ) -> tuple[float, list[FiredRule], list[str]]:
        """
        Returns (cf, fired_rules, asked_facts).
        asked_facts: observable facts the engine needs but aren't in wm.
        """
        if visited is None:
            visited = set()
        if goal in visited:
            return 0.0, [], []
        visited = visited | {goal}

        if goal in wm:
            return wm[goal], [], []

        relevant = [r for r in self.rules if r.conclusion == goal]
        if not relevant:
            # Leaf fact — not yet known, ask the user
            return 0.0, [], [goal]

        best_cf      = 0.0
        all_fired    : list[FiredRule]  = []
        all_to_ask   : list[str]        = []

        for rule in sorted(relevant, key=lambda r: (r.priority, r.specificity), reverse=True):
            ant_cfs  : dict[str, float] = {}
            sub_fired: list[FiredRule]  = []
            sub_ask  : list[str]        = []
            ok = True
            for ant in rule.antecedents:
                cf, sf, sa = self.backward_chain(ant, wm, depth + 1, visited)
                if cf < THRESHOLD:
                    sub_ask.extend(sa)
                    ok = False
                    break
                ant_cfs[ant] = cf
                sub_fired.extend(sf)
            if ok:
                new_cf  = rule.cf * min(ant_cfs.values())
                best_cf = cf_combine(best_cf, new_cf)
                all_fired.extend(sub_fired)
                all_fired.append(FiredRule(rule, ant_cfs, round(new_cf, 4)))
            else:
                all_to_ask.extend(sub_ask)

        return round(best_cf, 4), all_fired, all_to_ask

    # ── Natural-language explanation ────────────────────────────────────────
    def explain(self, wm: dict[str, float], fired: list[FiredRule], conflicts: list[ConflictEvent]) -> str:
        diagnoses = [(f, wm[f]) for f in DIAGNOSIS_FACTS if wm.get(f, 0) >= THRESHOLD]
        if not diagnoses:
            return "No threats reached the confidence threshold. The evidence collected does not conclusively point to a known attack pattern."

        diagnoses.sort(key=lambda x: x[1], reverse=True)
        top_d, top_cf = diagnoses[0]

        parts = [f"**Primary finding: {FACT_LABELS[top_d]}** (confidence: {top_cf:.0%})\n"]
        parts.append(f"The system analysed {len(fired)} inference step(s) to reach this conclusion.\n")

        # Describe the highest-confidence rules for the top diagnosis
        top_rules = [fr for fr in fired if fr.rule.conclusion == top_d]
        if top_rules:
            fr = max(top_rules, key=lambda r: r.conclusion_cf)
            ant_list = " and ".join(f"**{FACT_LABELS[a]}** (CF {fr.antecedent_cfs[a]:.0%})" for a in fr.rule.antecedents)
            parts.append(f"The key trigger was {ant_list}, which activated *{fr.rule.label}* (rule {fr.rule.id}) with a certainty factor of {fr.rule.cf:.0%}.")

        # Secondary findings
        secondaries = [(f, c) for f, c in diagnoses[1:] if c >= 0.40]
        if secondaries:
            sec_str = ", ".join(f"{FACT_LABELS[f]} ({c:.0%})" for f, c in secondaries)
            parts.append(f"\nSecondary threat indicators: {sec_str}.")

        # Conflict resolution note
        if conflicts:
            c = conflicts[0]
            parts.append(f"\nDuring inference, a conflict arose between rule {c.rule_a.id} and rule {c.rule_b.id} for the conclusion '{FACT_LABELS.get(c.conclusion, c.conclusion)}'. Rule {c.winner.id} was selected due to {c.reason}.")

        # Recommendations
        parts.append("\n**Recommended actions:**")
        recs = {
            "malware_infection":   "- Isolate affected hosts immediately\n- Run endpoint detection & response (EDR) scan\n- Preserve memory dumps for forensic analysis",
            "ransomware_attack":   "- Disconnect affected systems from network immediately\n- Do NOT pay the ransom\n- Restore from last known-good backup\n- Engage incident response team",
            "apt_attack":          "- Assume full network compromise\n- Engage threat-hunting team\n- Review all privileged accounts\n- Conduct full forensic investigation",
            "brute_force_attack":  "- Block offending IPs\n- Enable MFA on all accounts\n- Review account lockout policies\n- Reset compromised credentials",
            "insider_threat":      "- Suspend user account pending investigation\n- Preserve audit logs immediately\n- Involve HR and legal\n- Review data access permissions",
            "ddos_attack":         "- Activate DDoS mitigation / scrubbing service\n- Contact upstream ISP\n- Implement rate limiting\n- Failover to backup infrastructure",
            "phishing_campaign":   "- Block malicious sender domains\n- Issue user awareness alert\n- Reset credentials for targeted users\n- Scan endpoints for malware",
            "cryptojacking":       "- Kill unauthorised processes\n- Patch exploited vulnerabilities\n- Audit cloud resource costs\n- Harden container/server configurations",
            "data_breach":         "- Initiate breach notification procedures\n- Identify and contain the exfiltration vector\n- Notify legal / compliance team\n- Inform affected parties per regulation (GDPR, etc.)",
            "supply_chain_attack": "- Audit all third-party software and dependencies\n- Roll back to verified-clean builds\n- Contact software vendor immediately\n- Scan all systems that installed affected software",
        }
        parts.append(recs.get(top_d, "- Follow your organisation's incident response plan"))

        return "\n".join(parts)
