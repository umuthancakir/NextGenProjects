#!/usr/bin/env python3
"""
Scientific calculator — expressions, variables, ASCII plots, statistics, and more.
Run interactively or use CLI flags.
"""

import ast
import csv
import json
import math
import operator
import re
import shutil
import sys
import argparse
from datetime import datetime
from typing import Optional

# ── Colors ────────────────────────────────────────────────────────────────────

_NO_COLOR = not sys.stdout.isatty()
def _c(code: str, t: str) -> str:
    return t if _NO_COLOR else f"\033[{code}m{t}\033[0m"

GREEN   = lambda t: _c("32", t)
RED     = lambda t: _c("31", t)
CYAN    = lambda t: _c("36", t)
YELLOW  = lambda t: _c("33", t)
BOLD    = lambda t: _c("1",  t)
DIM     = lambda t: _c("2",  t)
MAGENTA = lambda t: _c("35", t)
BLUE    = lambda t: _c("34", t)


# ── Math surface ──────────────────────────────────────────────────────────────

def _mean(*a):     return sum(a) / len(a)
def _median(*a):
    s = sorted(a); n = len(s)
    return s[n//2] if n % 2 else (s[n//2-1] + s[n//2]) / 2
def _stdev(*a):
    m = sum(a)/len(a); return math.sqrt(sum((x-m)**2 for x in a)/len(a))
def _variance(*a):
    m = sum(a)/len(a); return sum((x-m)**2 for x in a)/len(a)
def _isprime(n: float) -> float:
    n = int(abs(n))
    if n < 2: return 0.0
    if n == 2: return 1.0
    if n % 2 == 0: return 0.0
    return 0.0 if any(n % i == 0 for i in range(3, int(n**0.5)+1, 2)) else 1.0
def _gcd(a, b): return float(math.gcd(int(a), int(b)))
def _lcm(a, b):
    a, b = int(a), int(b)
    return float(abs(a*b) // math.gcd(a, b)) if a and b else 0.0

FUNCTIONS: dict = {
    # Trigonometry
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan, "atan2": math.atan2,
    "degrees": math.degrees, "radians": math.radians,
    # Exponential / logarithm
    "sqrt": math.sqrt, "exp": math.exp,
    "log": math.log, "log2": math.log2, "log10": math.log10,
    # Rounding / misc
    "abs": abs, "ceil": math.ceil, "floor": math.floor, "round": round,
    "factorial": lambda x: float(math.factorial(int(x))),
    "hypot": math.hypot, "pow": math.pow,
    # Statistics  (variadic — call as mean(1,2,3,4,5))
    "mean": _mean, "median": _median, "stdev": _stdev, "variance": _variance,
    "sum": lambda *a: float(sum(a)),
    "min": lambda *a: float(min(a)),
    "max": lambda *a: float(max(a)),
    # Number theory
    "gcd": _gcd, "lcm": _lcm, "isprime": _isprime,
    "ndigits": lambda n: float(len(str(int(abs(n))))),
}

CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf}

OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}

# current variable scope — set by evaluate() before each AST walk
_eval_vars: dict[str, float] = {}


# ── Preprocessing / validation ────────────────────────────────────────────────

def preprocess(expr: str) -> str:
    expr = expr.replace("×", "*").replace("÷", "/").replace("^", "**")
    expr = re.sub(r"(\d+(?:\.\d+)?)\s*%", lambda m: f"({m.group(1)}/100)", expr)
    return expr.strip()


def validate(expr: str) -> bool:
    try:
        _eval_node(ast.parse(preprocess(expr), mode="eval").body)
        return True
    except Exception:
        return False


# ── AST evaluator ─────────────────────────────────────────────────────────────

def _eval_node(node: ast.expr) -> float:
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise TypeError("Only numeric literals allowed")
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op = OPS.get(type(node.op))
        if op is None: raise ValueError(f"Unsupported op: {type(node.op).__name__}")
        return op(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        val = _eval_node(node.operand)
        if isinstance(node.op, ast.USub): return -val
        if isinstance(node.op, ast.UAdd): return val
        raise ValueError("Unsupported unary op")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only named functions are allowed")
        name = node.func.id
        if name not in FUNCTIONS: raise ValueError(f"Unknown function: '{name}'")
        return FUNCTIONS[name](*[_eval_node(a) for a in node.args])
    if isinstance(node, ast.Name):
        if node.id in CONSTANTS:   return CONSTANTS[node.id]
        if node.id in _eval_vars:  return _eval_vars[node.id]
        raise ValueError(f"Unknown name: '{node.id}'  (define it with  {node.id} = ...)")
    raise ValueError(f"Unsupported: {type(node).__name__}")


def evaluate(expr: str, variables: Optional[dict] = None) -> float:
    """Evaluate a math expression, optionally with a variable scope."""
    global _eval_vars
    _eval_vars = variables or {}
    try:
        tree = ast.parse(preprocess(expr), mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Syntax error: {exc}") from exc
    return _eval_node(tree.body)


# ── Memory ────────────────────────────────────────────────────────────────────

class Memory:
    def __init__(self) -> None: self._v = 0.0
    def store(self, v: float):   self._v = v
    def recall(self) -> float:   return self._v
    def add(self, v: float):     self._v += v
    def subtract(self, v: float): self._v -= v
    def clear(self):             self._v = 0.0


# ── History ───────────────────────────────────────────────────────────────────

class History:
    def __init__(self, limit: int = 200) -> None:
        self._rows: list[dict] = []; self._limit = limit

    def push(self, expr: str, result: float) -> None:
        self._rows.append({"ts": datetime.now().isoformat(timespec="seconds"),
                           "expr": expr, "result": result})
        if len(self._rows) > self._limit: self._rows.pop(0)

    def show(self, n: int = 15) -> None:
        if not self._rows: print("  (empty)"); return
        for i, r in enumerate(self._rows[-n:], 1):
            print(f"  {i:>3}. [{DIM(r['ts'])}]  {r['expr']}  =  {GREEN(_fmt(r['result']))}")

    def export_json(self, path: str = "history.json") -> None:
        with open(path, "w") as f: json.dump(self._rows, f, indent=2)
        print(f"  Exported {len(self._rows)} entries → {path}")

    def export_csv(self, path: str = "history.csv") -> None:
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["ts", "expr", "result"])
            w.writeheader(); w.writerows(self._rows)
        print(f"  Exported {len(self._rows)} entries → {path}")

    def clear(self) -> None: self._rows.clear()


# ── ASCII function plotter ────────────────────────────────────────────────────

def plot_ascii(expr: str, x_min: float = -10.0, x_max: float = 10.0,
               variables: Optional[dict] = None) -> None:
    W = max(50, min(72, shutil.get_terminal_size((80, 24)).columns - 8))
    H = 20
    base_vars = dict(variables or {})

    # Sample the function
    ys: list[Optional[float]] = []
    for i in range(W):
        xv = x_min + (x_max - x_min) * i / (W - 1)
        try:
            ys.append(evaluate(expr, {**base_vars, "x": xv}))
        except Exception:
            ys.append(None)

    valid = [y for y in ys if y is not None and math.isfinite(y)]
    if not valid:
        print(RED("  No finite values to plot.")); return

    lo, hi = min(valid), max(valid)
    if abs(hi - lo) < 1e-12: lo -= 1.0; hi += 1.0

    # Build character grid
    grid = [[" "] * W for _ in range(H)]
    for col, y in enumerate(ys):
        if y is None or not math.isfinite(y): continue
        row = round((hi - y) / (hi - lo) * (H - 1))
        grid[max(0, min(H-1, row))][col] = "●"

    # Draw axes at y=0 and x=0 if they fall within range
    zr = round(hi / (hi - lo) * (H-1)) if lo <= 0 <= hi else -1
    zc = round(-x_min / (x_max - x_min) * (W-1)) if x_min <= 0 <= x_max else -1

    if 0 <= zr < H:
        for c in range(W):
            if grid[zr][c] == " ": grid[zr][c] = "─"
    if 0 <= zc < W:
        for r in range(H):
            if grid[r][zc] == " ": grid[r][zc] = "│"
    if 0 <= zr < H and 0 <= zc < W:
        grid[zr][zc] = "┼"

    # Header
    hi_s  = DIM(_fmt(hi))
    lo_s  = DIM(_fmt(lo))
    mid_s = DIM(_fmt((lo + hi) / 2))
    print(f"\n  {CYAN('▶ plot')} {BOLD(expr)}")
    print(f"    x ∈ [{YELLOW(_fmt(x_min))}, {YELLOW(_fmt(x_max))}]   "
          f"y ∈ [{YELLOW(_fmt(lo))}, {YELLOW(_fmt(hi))}]\n")

    # Grid
    print(f"  {hi_s:>10}  ┐")
    print(f"  {'':10}  ┌{'─'*W}┐")
    for r, row in enumerate(grid):
        label = f"  {mid_s}" if r == H // 2 else ""
        print(f"  {'':10}  │{''.join(row)}│{label}")
    print(f"  {'':10}  └{'─'*W}┘")
    print(f"  {lo_s:>10}  ┘")

    # x-axis labels
    x_mid = _fmt((x_min + x_max) / 2)
    x_l, x_r = _fmt(x_min), _fmt(x_max)
    pad_l = max(0, W//2 - len(x_l) - 1)
    pad_r = max(0, W//2 - len(x_mid) - len(x_r))
    print(f"  {'':12} {DIM(x_l)}{' '*pad_l}{DIM(x_mid)}{' '*pad_r}{DIM(x_r)}\n")


# ── Number-theory helpers ─────────────────────────────────────────────────────

def _prime_factors(n: int) -> list[int]:
    n = abs(n); factors = []
    d = 2
    while d * d <= n:
        while n % d == 0: factors.append(d); n //= d
        d += 1
    if n > 1: factors.append(n)
    return factors

def _all_factors(n: int) -> list[int]:
    n = abs(n)
    return sorted(i for i in range(1, n+1) if n % i == 0)

def cmd_factors(n: int) -> None:
    pf = _prime_factors(n)
    af = _all_factors(n)
    print(f"\n  {CYAN('Factors of')} {BOLD(str(n))}")
    print(f"    All factors   : {', '.join(map(str, af))}")
    print(f"    Prime factors : {' × '.join(map(str, pf)) or str(n)}")
    print(f"    Is prime      : {GREEN('yes') if _isprime(n) else RED('no')}")
    print(f"    # of factors  : {len(af)}\n")

def cmd_bases(n: int) -> None:
    print(f"\n  {CYAN('Bases for')} {BOLD(str(n))}")
    print(f"    Decimal  (base 10) :  {YELLOW(str(n))}")
    print(f"    Binary   (base  2) :  {YELLOW(bin(n))}  →  {DIM(str(n) + ' = ' + ' + '.join(str(2**i) for i,b in enumerate(reversed(bin(n)[2:])) if b=='1'))}")
    print(f"    Octal    (base  8) :  {YELLOW(oct(n))}")
    print(f"    Hex      (base 16) :  {YELLOW(hex(n).upper().replace('X','x'))}\n")

def cmd_stats(nums: list[float]) -> None:
    n = len(nums)
    s = sum(nums)
    mu = s / n
    med = _median(*nums)
    sd = _stdev(*nums) if n > 1 else 0.0
    var = _variance(*nums) if n > 1 else 0.0
    lo, hi = min(nums), max(nums)
    print(f"\n  {CYAN('Statistics')}  ({n} values)")
    print(f"    Count    : {YELLOW(str(n))}")
    print(f"    Sum      : {YELLOW(_fmt(s))}")
    print(f"    Min / Max: {YELLOW(_fmt(lo))} / {YELLOW(_fmt(hi))}")
    print(f"    Mean     : {YELLOW(_fmt(mu))}")
    print(f"    Median   : {YELLOW(_fmt(med))}")
    print(f"    Std dev  : {YELLOW(_fmt(sd))}")
    print(f"    Variance : {YELLOW(_fmt(var))}\n")


# ── Natural-language → expression ─────────────────────────────────────────────

_NL_RULES: list[tuple[str, str]] = [
    (r"^\s*(?:what(?:'s|\s+is|\s+are)|calculate|compute|find|evaluate|how\s+much\s+is|solve|tell\s+me)\s+", ""),
    (r"(\d+(?:\.\d+)?)\s*(?:percent|%)\s+of\s+",  r"(\1/100)*"),
    (r"(?:the\s+)?square\s+root\s+of\s+(\d+(?:\.\d+)?)", r"sqrt(\1)"),
    (r"(?:the\s+)?cube\s+root\s+of\s+(\d+(?:\.\d+)?)",   r"(\1**(1/3))"),
    (r"sqrt\s+of\s+(\d+(?:\.\d+)?)", r"sqrt(\1)"),
    (r"\b(sin|cos|tan|asin|acos|atan|log|log10|log2|exp)\s+of\s+(\d+(?:\.\d+)?)", r"\1(\2)"),
    (r"(\d+(?:\.\d+)?)\s+to\s+the\s+power\s+of\s+(\d+(?:\.\d+)?)", r"(\1**\2)"),
    (r"(\d+(?:\.\d+)?)\s+to\s+the\s+(\d+)(?:st|nd|rd|th)?",        r"(\1**\2)"),
    (r"(\d+(?:\.\d+)?)\s+squared\b", r"(\1**2)"),
    (r"(\d+(?:\.\d+)?)\s+cubed\b",   r"(\1**3)"),
    (r"\bdouble\s+(\d+(?:\.\d+)?)",  r"(2*\1)"),
    (r"\btwice\s+(\d+(?:\.\d+)?)",   r"(2*\1)"),
    (r"\btriple\s+(\d+(?:\.\d+)?)",  r"(3*\1)"),
    (r"\bhalf\s+of\s+(\d+(?:\.\d+)?)", r"(\1/2)"),
    (r"\bmultiplied\s+by\b", "*"), (r"\bdivided\s+by\b", "/"),
    (r"\bplus\b", "+"), (r"\bminus\b", "-"), (r"\btimes\b", "*"),
    (r"\bover\b", "/"), (r"\bmod(?:ulo)?\b", "%"),
    (r"(\d+)(?:st|nd|rd|th)\b", r"\1"), (r"\bthe\b", ""), (r"\s{2,}", " "),
]

def nl_to_expr(query: str) -> str:
    s = query.strip()
    for pat, repl in _NL_RULES:
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)
    return s.strip()


# ── Formatting ────────────────────────────────────────────────────────────────

def _fmt(v: float) -> str:
    if v != v: return "NaN"
    if v == math.inf: return "∞"
    if v == -math.inf: return "-∞"
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return str(int(v))
    return f"{v:.10g}"


# ── Tab completion ────────────────────────────────────────────────────────────

def _setup_readline(user_vars: dict) -> None:
    try:
        import readline
        _words = (sorted(FUNCTIONS) + sorted(CONSTANTS) +
                  ["plot", "factors", "bases", "stats", "vars",
                   "history", "history clear", "export json", "export csv",
                   "ms", "mr", "m+", "m-", "mc", "help", "quit", "ai", "ans"])

        def _completer(text: str, state: int):
            all_words = _words + list(user_vars)
            matches = [w for w in all_words if w.startswith(text)]
            return matches[state] if state < len(matches) else None

        readline.set_completer(_completer)
        readline.parse_and_bind("tab: complete")
    except ImportError:
        pass


# ── Help ──────────────────────────────────────────────────────────────────────

def _print_help() -> None:
    w = "─" * 56
    print(f"\n  {CYAN('┌' + w + '┐')}")
    print(f"  {CYAN('│')}" + BOLD("  Scientific Calculator").center(57) + f"{CYAN('│')}")
    print(f"  {CYAN('└' + w + '┘')}\n")

    sections = [
        ("EXPRESSIONS", [
            ("3 + 4 * 2",        "proper order of operations"),
            ("2^10  or  2**10",  "powers"),
            ("sqrt(16)",         "scientific functions"),
            ("sin(pi/2)",        "trig (values in radians)"),
            ("20% * 150",        "percentage shorthand"),
            ("ans * 2",          "last result"),
        ]),
        ("VARIABLES", [
            ("r = 7",            "define a variable"),
            ("area = pi * r^2",  "use it in expressions"),
            ("vars",             "list all defined variables"),
        ]),
        ("STATISTICS  (call inside expressions too)", [
            ("stats 1,2,3,4,5",  "full summary"),
            ("mean(2,4,6,8)",     "mean of values"),
            ("stdev(2,4,6,8)",    "standard deviation"),
            ("median(1,3,5)",     "median"),
        ]),
        ("PLOTTING", [
            ("plot sin(x)",                "graph over x ∈ [−10, 10]"),
            ("plot x^2 - 4 from -3 to 3",  "custom range"),
            ("plot sin(x)*cos(x) from 0 to tau", "combined"),
        ]),
        ("NUMBER THEORY", [
            ("factors 84",       "all & prime factors, primality"),
            ("bases 255",        "binary, octal, decimal, hex"),
            ("gcd(12, 8)",       "greatest common divisor"),
            ("lcm(4, 6)",        "least common multiple"),
            ("isprime(17)",      "1.0 = prime, 0.0 = composite"),
        ]),
        ("MEMORY", [
            ("ms",  "store last result"),
            ("mr",  "recall memory"),
            ("m+  /  m-", "add / subtract last result"),
            ("mc",  "clear memory"),
        ]),
        ("HISTORY", [
            ("history",              "show last 15 entries"),
            ("history clear",        "wipe history"),
            ("export json [file]",   "export to JSON"),
            ("export csv  [file]",   "export to CSV"),
        ]),
        ("NATURAL LANGUAGE", [
            ("ai what is 20% of 150 plus 30", ""),
            ("? square root of 144 times 3",  ""),
        ]),
    ]

    for title, items in sections:
        print(f"  {YELLOW(title)}")
        for cmd, desc in items:
            pad = 38 - len(cmd)
            tail = DIM(f"— {desc}") if desc else ""
            print(f"    {BOLD(cmd)}{' '*max(1,pad)}{tail}")
        print()

    fns = "sin cos tan asin acos atan sqrt exp log log10 log2 abs ceil floor factorial degrees radians hypot round"
    print(f"  {YELLOW('ALL FUNCTIONS')}")
    print(f"  {DIM(fns)}")
    print(f"  {DIM('Constants: pi  e  tau  inf')}\n")


# ── Variable-assignment detector ──────────────────────────────────────────────

_ASSIGN_RE = re.compile(r"^([a-zA-Z_][a-zA-Z_0-9]*)\s*=\s*(.+)$")
_RESERVED   = frozenset(
    list(FUNCTIONS) + list(CONSTANTS) +
    ["ans", "quit", "exit", "q", "help", "history", "vars",
     "plot", "factors", "bases", "stats", "ms", "mr", "mc", "ai"]
)


# ── Interactive REPL ──────────────────────────────────────────────────────────

def repl(mem: Memory, hist: History) -> None:
    user_vars: dict[str, float] = {}
    _setup_readline(user_vars)
    last: Optional[float] = None

    # Banner
    print(f"\n  {CYAN('╔══════════════════════════════════════╗')}")
    print(f"  {CYAN('║')}  {BOLD('Scientific Calculator')}  {DIM('— type help')}  {CYAN('║')}")
    print(f"  {CYAN('╚══════════════════════════════════════╝')}\n")

    while True:
        try:
            prompt = f"\n  {CYAN('calc')} {BLUE('›')} "
            raw = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {DIM('Bye!')}"); return
        if not raw:
            continue
        lo = raw.lower()

        # ── Quit ─────────────────────────────────────────────────────────────
        if lo in ("quit", "exit", "q"):
            print(f"  {DIM('Bye!')}"); return

        # ── Help ─────────────────────────────────────────────────────────────
        elif lo == "help":
            _print_help()

        # ── Plot ─────────────────────────────────────────────────────────────
        elif lo.startswith("plot "):
            rest = raw[5:].strip()
            m = re.match(r"(.+?)\s+from\s+(.+?)\s+to\s+(.+)$", rest, re.I)
            if m:
                expr_s = m.group(1).strip()
                try:
                    x0 = evaluate(m.group(2).strip(), user_vars)
                    x1 = evaluate(m.group(3).strip(), user_vars)
                except Exception as exc:
                    print(RED(f"  Range error: {exc}")); continue
            else:
                expr_s, x0, x1 = rest, -10.0, 10.0
            try:
                plot_ascii(expr_s, x0, x1, user_vars)
            except Exception as exc:
                print(RED(f"  Plot error: {exc}"))

        # ── factors N ────────────────────────────────────────────────────────
        elif lo.startswith("factors "):
            try:
                cmd_factors(int(evaluate(raw[8:].strip(), user_vars)))
            except Exception as exc:
                print(RED(f"  Error: {exc}"))

        # ── bases N ──────────────────────────────────────────────────────────
        elif lo.startswith("bases "):
            try:
                n = int(evaluate(raw[6:].strip(), user_vars))
                if n < 0:
                    print(RED("  bases requires a non-negative integer")); continue
                cmd_bases(n)
            except Exception as exc:
                print(RED(f"  Error: {exc}"))

        # ── stats a,b,c,... ──────────────────────────────────────────────────
        elif lo.startswith("stats ") or lo == "stats":
            parts = raw[6:].strip() if lo.startswith("stats ") else ""
            if not parts:
                print(DIM("  Usage: stats 1, 2, 3, 4, 5")); continue
            try:
                nums = [evaluate(x.strip(), user_vars) for x in parts.split(",") if x.strip()]
                if len(nums) < 2:
                    print(DIM("  Need at least 2 values.")); continue
                cmd_stats(nums)
            except Exception as exc:
                print(RED(f"  Error: {exc}"))

        # ── vars ─────────────────────────────────────────────────────────────
        elif lo == "vars":
            if not user_vars:
                print(DIM("  No variables defined yet."))
            else:
                print(f"\n  {CYAN('Variables:')}")
                for k, v in sorted(user_vars.items()):
                    print(f"    {BOLD(k):20} = {GREEN(_fmt(v))}")
                print()

        # ── history ──────────────────────────────────────────────────────────
        elif lo == "history":
            hist.show()
        elif lo == "history clear":
            hist.clear(); print(DIM("  History cleared."))
        elif lo.startswith("export json"):
            parts = raw.split(maxsplit=2)
            hist.export_json(parts[2] if len(parts) > 2 else "history.json")
        elif lo.startswith("export csv"):
            parts = raw.split(maxsplit=2)
            hist.export_csv(parts[2] if len(parts) > 2 else "history.csv")

        # ── Memory ───────────────────────────────────────────────────────────
        elif lo == "ms":
            if last is None: print(DIM("  No result yet."))
            else: mem.store(last); print(f"  {CYAN('M')} ← {GREEN(_fmt(last))}")
        elif lo == "mr":
            print(f"  {CYAN('M')} = {GREEN(_fmt(mem.recall()))}")
        elif lo == "m+":
            if last is None: print(DIM("  No result yet."))
            else: mem.add(last); print(f"  {CYAN('M')} = {GREEN(_fmt(mem.recall()))}")
        elif lo == "m-":
            if last is None: print(DIM("  No result yet."))
            else: mem.subtract(last); print(f"  {CYAN('M')} = {GREEN(_fmt(mem.recall()))}")
        elif lo == "mc":
            mem.clear(); print(DIM("  Memory cleared."))

        # ── Natural language ─────────────────────────────────────────────────
        elif lo.startswith("ai ") or lo.startswith("? "):
            query = raw[3:].strip() if lo.startswith("ai ") else raw[2:].strip()
            try:
                expr = nl_to_expr(query)
                print(f"  {DIM('→')} {expr}")
                result = evaluate(expr, user_vars)
                last = result
                hist.push(f"[ai] {query}", result)
                print(f"  = {GREEN(BOLD(_fmt(result)))}")
            except Exception as exc:
                print(RED(f"  Error: {exc}"))

        # ── Variable assignment: x = ... ─────────────────────────────────────
        else:
            # Check for assignment before trying to evaluate as expression
            m = _ASSIGN_RE.match(raw)
            if m and m.group(1) not in _RESERVED:
                name, rhs = m.group(1), m.group(2).strip()
                try:
                    val = evaluate(rhs, user_vars)
                    user_vars[name] = val
                    last = val
                    print(f"  {CYAN(name)} = {GREEN(_fmt(val))}")
                    _setup_readline(user_vars)  # refresh completions
                except Exception as exc:
                    print(RED(f"  Error: {exc}"))
            else:
                # Plain expression — substitute 'ans' and eval
                expr = re.sub(r"\bans\b", str(last) if last is not None else "0", raw)
                try:
                    result = evaluate(expr, user_vars)
                    last = result
                    hist.push(expr, result)
                    print(f"  = {GREEN(BOLD(_fmt(result)))}")
                except Exception as exc:
                    print(RED(f"  Error: {exc}"))


# ── Self-tests ────────────────────────────────────────────────────────────────

def run_tests() -> None:
    cases = [
        ("3 + 4 * 2",                 11),
        ("(3 + 4) * 2",               14),
        ("2 ** 10",                   1024),
        ("2^10",                      1024),
        ("sqrt(16)",                  4),
        ("sin(0)",                    0),
        ("cos(0)",                    1),
        ("20% * 150",                 30),
        ("10 / 2 + 3",                8),
        ("-5 + 3",                    -2),
        ("factorial(5)",              120),
        ("log10(1000)",               3),
        ("abs(-7)",                   7),
        ("pi",                        math.pi),
        ("floor(3.9)",                3),
        ("ceil(3.1)",                 4),
        ("mean(2,4,6,8)",             5),
        ("median(1,3,5,7)",           4),
        ("gcd(12,8)",                 4),
        ("lcm(4,6)",                  12),
        ("isprime(17)",               1),
        ("isprime(4)",                0),
    ]
    passed = failed = 0
    for expr, expected in cases:
        try:
            got = evaluate(expr)
            assert abs(got - expected) < 1e-9, f"got {got}"
            print(f"  PASS  {expr!r:35s} = {expected}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {expr!r:35s}  {exc}")
            failed += 1

    # Variables
    assert evaluate("x + 1", {"x": 4}) == 5.0
    assert evaluate("r * r * pi", {"r": 1.0}) == math.pi
    print("  PASS  Variable scope")
    passed += 1

    # Memory
    m = Memory()
    m.store(10); m.add(5); assert m.recall() == 15
    m.subtract(3); assert m.recall() == 12; m.clear(); assert m.recall() == 0
    print("  PASS  Memory")
    passed += 1

    # Security: eval blocks unsafe input
    assert not validate("import os")
    assert not validate("__import__('os')")
    assert not validate("open('x')")
    print("  PASS  Security (blocks unsafe input)")
    passed += 1

    print(f"\n  {GREEN(str(passed))} passed, {RED(str(failed)) if failed else '0'} failed")
    if failed: sys.exit(1)


# ── Menu helpers ─────────────────────────────────────────────────────────────

def _get_float(prompt: str) -> Optional[float]:
    while True:
        try:
            raw = input(f"  {prompt}: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if raw.lower() in ("q", "quit", "back", "exit", ""):
            return None
        try:
            return float(evaluate(raw))
        except Exception:
            try:
                return float(raw)
            except ValueError:
                print(RED("  Please enter a valid number (or 0 to go back)."))


def _menu_select(title: str, options: list) -> int:
    bar = CYAN("━" * 44)
    print(f"\n  {bar}")
    print(f"  {BOLD(title)}")
    print(f"  {bar}")
    for i, opt in enumerate(options, 1):
        print(f"    {YELLOW(str(i))}.  {opt}")
    print(f"    {YELLOW('0')}.  {DIM('← Back')}")
    print(f"  {bar}")
    while True:
        try:
            raw = input(f"  {BLUE('›')} ").strip()
        except (EOFError, KeyboardInterrupt):
            return -1
        if raw in ("0", "q", "quit", "back", "exit"):
            return -1
        try:
            c = int(raw)
            if 1 <= c <= len(options):
                return c - 1
            print(RED(f"  Enter a number from 0 to {len(options)}."))
        except ValueError:
            print(RED("  Please enter a number."))


def _show_result(label: str, value: float, unit: str = "") -> None:
    u = f"  {DIM(unit)}" if unit else ""
    print(f"\n  {CYAN(label)}")
    print(f"  {GREEN(BOLD(_fmt(value)))}{u}\n")


def _show_results(**kwargs) -> None:
    print()
    for label, (val, unit) in kwargs.items():
        u = f"  {DIM(unit)}" if unit else ""
        print(f"  {CYAN(label + ':'):25} {GREEN(BOLD(_fmt(val)))}{u}")
    print()


# ── Basic Arithmetic ──────────────────────────────────────────────────────────

def menu_basic_arithmetic() -> None:
    bar = CYAN("━" * 44)
    print(f"\n  {bar}")
    print(f"  {BOLD('Basic Arithmetic')}")
    print(f"  {bar}")
    print(f"  Type any expression and press Enter.")
    print(f"  {DIM('Examples:  10 + 14 * 2 / 6')}")
    print(f"  {DIM('           (3 + 5)^2 - sqrt(16)')}")
    print(f"  {DIM('           25% * 200  |  100 // 7  |  2^10')}")
    print(f"  {DIM('Type  0  or  back  to return to the main menu.')}")
    print(f"  {bar}\n")
    last: Optional[float] = None
    while True:
        try:
            raw = input(f"  {CYAN('calc')} {BLUE('›')} ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not raw:
            continue
        if raw.lower() in ("0", "back", "exit", "quit", "q"):
            return
        expr = re.sub(r"\bans\b", str(last) if last is not None else "0", raw)
        try:
            result = evaluate(expr)
            last = result
            print(f"  = {GREEN(BOLD(_fmt(result)))}\n")
        except Exception as exc:
            print(RED(f"  Error: {exc}\n"))


# ── Geometric Shapes ──────────────────────────────────────────────────────────

def _shape_circle() -> None:
    while True:
        idx = _menu_select("Circle", [
            "Area          π · r²",
            "Circumference  2 · π · r",
            "Both",
        ])
        if idx < 0:
            return
        r = _get_float("Enter radius r")
        if r is None:
            continue
        if r < 0:
            print(RED("  Radius must be non-negative.")); continue
        if idx in (0, 2):
            _show_result("Area  =", math.pi * r * r, "units²")
        if idx in (1, 2):
            _show_result("Circumference  =", 2 * math.pi * r, "units")


def _shape_triangle() -> None:
    while True:
        idx = _menu_select("Triangle", [
            "Area  — base & height   (½ · b · h)",
            "Area  — 3 sides         (Heron's formula)",
            "Perimeter               (a + b + c)",
            "Hypotenuse (right)      (√(a² + b²))",
        ])
        if idx < 0:
            return
        if idx == 0:
            b = _get_float("Enter base (b)")
            if b is None: continue
            h = _get_float("Enter height (h)")
            if h is None: continue
            _show_result("Area  =", 0.5 * b * h, "units²")
        elif idx == 1:
            a = _get_float("Enter side a")
            if a is None: continue
            b = _get_float("Enter side b")
            if b is None: continue
            c = _get_float("Enter side c")
            if c is None: continue
            s = (a + b + c) / 2
            disc = s * (s - a) * (s - b) * (s - c)
            if disc < 0:
                print(RED("  These side lengths cannot form a valid triangle.")); continue
            _show_result("Area (Heron)  =", math.sqrt(disc), "units²")
        elif idx == 2:
            a = _get_float("Enter side a")
            if a is None: continue
            b = _get_float("Enter side b")
            if b is None: continue
            c = _get_float("Enter side c")
            if c is None: continue
            _show_result("Perimeter  =", a + b + c, "units")
        elif idx == 3:
            a = _get_float("Enter leg a")
            if a is None: continue
            b = _get_float("Enter leg b")
            if b is None: continue
            _show_result("Hypotenuse  =", math.hypot(a, b), "units")


def _shape_square() -> None:
    while True:
        idx = _menu_select("Square", ["Area  (s²)", "Perimeter  (4·s)", "Diagonal  (s·√2)"])
        if idx < 0:
            return
        s = _get_float("Enter side length s")
        if s is None: continue
        if idx == 0: _show_result("Area  =", s * s, "units²")
        elif idx == 1: _show_result("Perimeter  =", 4 * s, "units")
        else: _show_result("Diagonal  =", s * math.sqrt(2), "units")


def _shape_rectangle() -> None:
    while True:
        idx = _menu_select("Rectangle", [
            "Area          (l · w)",
            "Perimeter     (2·(l + w))",
            "Diagonal      (√(l² + w²))",
            "All three",
        ])
        if idx < 0:
            return
        l = _get_float("Enter length (l)")
        if l is None: continue
        w = _get_float("Enter width  (w)")
        if w is None: continue
        if idx in (0, 3): _show_result("Area  =", l * w, "units²")
        if idx in (1, 3): _show_result("Perimeter  =", 2 * (l + w), "units")
        if idx in (2, 3): _show_result("Diagonal  =", math.hypot(l, w), "units")


def _shape_hexagon() -> None:
    while True:
        idx = _menu_select("Regular Hexagon", [
            "Area      ((3√3 / 2) · s²)",
            "Perimeter  (6 · s)",
            "Apothem   ((√3 / 2) · s)",
        ])
        if idx < 0:
            return
        s = _get_float("Enter side length s")
        if s is None: continue
        if idx == 0: _show_result("Area  =", (3 * math.sqrt(3) / 2) * s * s, "units²")
        elif idx == 1: _show_result("Perimeter  =", 6 * s, "units")
        else: _show_result("Apothem  =", (math.sqrt(3) / 2) * s, "units")


def _shape_pentagon() -> None:
    while True:
        idx = _menu_select("Regular Pentagon", [
            "Area      ((s²/4)·√(25 + 10√5))",
            "Perimeter  (5 · s)",
            "Apothem   (s / (2·tan(π/5)))",
        ])
        if idx < 0:
            return
        s = _get_float("Enter side length s")
        if s is None: continue
        if idx == 0:
            _show_result("Area  =", (s * s / 4) * math.sqrt(25 + 10 * math.sqrt(5)), "units²")
        elif idx == 1:
            _show_result("Perimeter  =", 5 * s, "units")
        else:
            _show_result("Apothem  =", s / (2 * math.tan(math.pi / 5)), "units")


def _shape_octagon() -> None:
    while True:
        idx = _menu_select("Regular Octagon", [
            "Area      (2·(1+√2)·s²)",
            "Perimeter  (8 · s)",
            "Apothem   ((s/2)·(1+√2))",
        ])
        if idx < 0:
            return
        s = _get_float("Enter side length s")
        if s is None: continue
        if idx == 0: _show_result("Area  =", 2 * (1 + math.sqrt(2)) * s * s, "units²")
        elif idx == 1: _show_result("Perimeter  =", 8 * s, "units")
        else: _show_result("Apothem  =", (s / 2) * (1 + math.sqrt(2)), "units")


def menu_geometric_shapes() -> None:
    SHAPES = [
        ("Circle",            _shape_circle),
        ("Triangle",          _shape_triangle),
        ("Square",            _shape_square),
        ("Rectangle",         _shape_rectangle),
        ("Hexagon  (regular)", _shape_hexagon),
        ("Pentagon (regular)", _shape_pentagon),
        ("Octagon  (regular)", _shape_octagon),
    ]
    while True:
        idx = _menu_select("Geometric Shapes", [s[0] for s in SHAPES])
        if idx < 0:
            return
        SHAPES[idx][1]()


# ── Numerical methods (used by Advanced Math) ─────────────────────────────────

def _nderiv(expr: str, x: float, order: int = 1, h: float = 1e-5,
            uv: Optional[dict] = None) -> float:
    vars_ = dict(uv or {})
    def f(t): return evaluate(expr, {**vars_, "x": t})
    if order == 1:
        return (f(x + h) - f(x - h)) / (2 * h)
    if order == 2:
        return (f(x + h) - 2 * f(x) + f(x - h)) / (h * h)
    if order == 3:
        return (f(x+2*h) - 2*f(x+h) + 2*f(x-h) - f(x-2*h)) / (2 * h**3)
    if order == 4:
        return (f(x+2*h) - 4*f(x+h) + 6*f(x) - 4*f(x-h) + f(x-2*h)) / h**4
    raise ValueError(f"Order {order} not supported")


def _ninteg(expr: str, a: float, b: float, n: int = 2000,
            uv: Optional[dict] = None) -> float:
    vars_ = dict(uv or {})
    if n % 2: n += 1
    h = (b - a) / n
    def f(t): return evaluate(expr, {**vars_, "x": t})
    total = f(a) + f(b)
    for i in range(1, n):
        total += (4 if i % 2 else 2) * f(a + i * h)
    return total * h / 3


def _nlimit(expr: str, a: float, uv: Optional[dict] = None):
    vars_ = dict(uv or {})
    def f(t): return evaluate(expr, {**vars_, "x": t})
    eps = [1e-3, 1e-5, 1e-7, 1e-9]
    def approach(sign):
        vals = [f(a + sign * e) for e in eps]
        if all(math.isfinite(v) for v in vals):
            return vals[-1]
        return math.nan
    return approach(-1), approach(+1)


def _get_expr_prompt(label: str) -> Optional[str]:
    try:
        raw = input(f"  {label} (in terms of x): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    return None if raw.lower() in ("q", "quit", "back", "") else raw


# ── Advanced → Calculus ───────────────────────────────────────────────────────

def menu_calculus() -> None:
    while True:
        idx = _menu_select("Calculus", [
            "Limit   lim(x→a) f(x)",
            "Derivative   f '(a)   (numerical)",
            "Definite integral   ∫ f(x) dx  from a to b",
        ])
        if idx < 0:
            return

        if idx == 0:
            expr = _get_expr_prompt("f(x)")
            if expr is None: continue
            a = _get_float("Approach point a")
            if a is None: continue
            left, right = _nlimit(expr, a)
            print(f"\n  {CYAN('Limit of')} {BOLD(expr)} {CYAN('as x →')} {YELLOW(_fmt(a))}")
            print(f"  From the left  (x → a⁻)  :  {GREEN(_fmt(left))}")
            print(f"  From the right (x → a⁺)  :  {GREEN(_fmt(right))}")
            if abs(left - right) < 1e-6 and math.isfinite(left):
                print(f"  {CYAN('Limit exists')}  ≈  {GREEN(BOLD(_fmt(left)))}")
            else:
                print(f"  {RED('Limit does not exist (left ≠ right).')}")
            print()

        elif idx == 1:
            expr = _get_expr_prompt("f(x)")
            if expr is None: continue
            a = _get_float("Point a")
            if a is None: continue
            try:
                d1 = _nderiv(expr, a, 1)
                d2 = _nderiv(expr, a, 2)
                print(f"\n  {CYAN('f(x)')}  = {BOLD(expr)}")
                lbl_f  = CYAN("f(" + _fmt(a) + ")")
                lbl_d1 = CYAN("f'(" + _fmt(a) + ")")
                lbl_d2 = CYAN('f"(' + _fmt(a) + ")")
                print(f"  {lbl_f}   = {GREEN(_fmt(evaluate(expr, {'x': a})))}")
                print(f"  {lbl_d1}  = {GREEN(BOLD(_fmt(d1)))}  {DIM('(first derivative)')}")
                print(f"  {lbl_d2}  = {GREEN(_fmt(d2))}  {DIM('(second derivative)')}")
                print()
            except Exception as exc:
                print(RED(f"  Error: {exc}"))

        elif idx == 2:
            expr = _get_expr_prompt("f(x)")
            if expr is None: continue
            a = _get_float("Lower bound a")
            if a is None: continue
            b = _get_float("Upper bound b")
            if b is None: continue
            try:
                val = _ninteg(expr, a, b)
                print(f"\n  {CYAN('∫')} {BOLD(expr)} dx  from {YELLOW(_fmt(a))} to {YELLOW(_fmt(b))}")
                print(f"  = {GREEN(BOLD(_fmt(val)))}  {DIM('(Simpson rule, n=2000)')}\n")
            except Exception as exc:
                print(RED(f"  Error: {exc}"))


# ── Advanced → Linear Algebra ─────────────────────────────────────────────────

def _input_matrix(n: int, label: str) -> Optional[list]:
    print(f"\n  {CYAN('Enter')} {BOLD(label)} {CYAN(f'({n}×{n} matrix, row by row)')}")
    m = []
    for i in range(n):
        row = []
        for j in range(n):
            v = _get_float(f"  [{i+1},{j+1}]")
            if v is None: return None
            row.append(v)
        m.append(row)
    return m


def _print_matrix(m: list, label: str = "") -> None:
    if label:
        print(f"  {CYAN(label)}")
    n = len(m)
    for i, row in enumerate(m):
        L = ("⌈" if i == 0 else "⌊" if i == n-1 else "│")
        R = ("⌉" if i == 0 else "⌋" if i == n-1 else "│")
        vals = "  ".join(f"{v:>10.5g}" for v in row)
        print(f"    {L} {vals} {R}")
    print()


def _det2(m): return m[0][0]*m[1][1] - m[0][1]*m[1][0]

def _det3(m):
    return (m[0][0] * (m[1][1]*m[2][2] - m[1][2]*m[2][1])
          - m[0][1] * (m[1][0]*m[2][2] - m[1][2]*m[2][0])
          + m[0][2] * (m[1][0]*m[2][1] - m[1][1]*m[2][0]))

def _mat_mul(a: list, b: list) -> list:
    n = len(a)
    return [[sum(a[i][k]*b[k][j] for k in range(n)) for j in range(n)] for i in range(n)]

def _solve2x2(a: list, bv: list) -> Optional[tuple]:
    d = _det2(a)
    if abs(d) < 1e-14: return None
    x = (bv[0]*a[1][1] - bv[1]*a[0][1]) / d
    y = (a[0][0]*bv[1] - a[1][0]*bv[0]) / d
    return x, y

def _inverse2x2(m: list) -> Optional[list]:
    d = _det2(m)
    if abs(d) < 1e-14: return None
    return [[ m[1][1]/d, -m[0][1]/d],
            [-m[1][0]/d,  m[0][0]/d]]


def menu_linear_algebra() -> None:
    while True:
        idx = _menu_select("Linear Algebra", [
            "2×2 Determinant",
            "3×3 Determinant",
            "2×2 Matrix × Matrix",
            "2×2 Matrix Inverse",
            "Solve 2×2 linear system  (Ax = b)",
            "Dot product (vectors)",
            "Cross product (3D vectors)",
        ])
        if idx < 0:
            return

        if idx == 0:
            m = _input_matrix(2, "Matrix A")
            if m is None: continue
            _print_matrix(m, "A =")
            _show_result("det(A)  =", _det2(m))

        elif idx == 1:
            m = _input_matrix(3, "Matrix A")
            if m is None: continue
            _print_matrix(m, "A =")
            _show_result("det(A)  =", _det3(m))

        elif idx == 2:
            a = _input_matrix(2, "Matrix A")
            if a is None: continue
            b = _input_matrix(2, "Matrix B")
            if b is None: continue
            _print_matrix(a, "A =")
            _print_matrix(b, "B =")
            _print_matrix(_mat_mul(a, b), "A × B =")

        elif idx == 3:
            m = _input_matrix(2, "Matrix A")
            if m is None: continue
            inv = _inverse2x2(m)
            _print_matrix(m, "A =")
            if inv is None:
                print(RED("  Matrix is singular (determinant = 0); no inverse."))
            else:
                _print_matrix(inv, "A⁻¹ =")

        elif idx == 4:
            print(f"\n  {CYAN('System:')}  a·x + b·y = e")
            print(f"          c·x + d·y = f\n")
            a11 = _get_float("a"); a12 = _get_float("b")
            if a11 is None or a12 is None: continue
            a21 = _get_float("c"); a22 = _get_float("d")
            if a21 is None or a22 is None: continue
            e  = _get_float("e"); f = _get_float("f")
            if e is None or f is None: continue
            sol = _solve2x2([[a11, a12],[a21, a22]], [e, f])
            if sol is None:
                print(RED("  No unique solution (singular system)."))
            else:
                print(f"\n  {CYAN('Solution:')}")
                print(f"    x = {GREEN(BOLD(_fmt(sol[0])))}")
                print(f"    y = {GREEN(BOLD(_fmt(sol[1])))}\n")

        elif idx == 5:
            print(f"\n  {CYAN('Dot product:')}  a·b")
            n = 3
            a = [_get_float(f"a[{i+1}]") for i in range(n)]
            if any(v is None for v in a): continue
            b = [_get_float(f"b[{i+1}]") for i in range(n)]
            if any(v is None for v in b): continue
            dot = sum(ai * bi for ai, bi in zip(a, b))
            mag_a = math.sqrt(sum(v*v for v in a))
            mag_b = math.sqrt(sum(v*v for v in b))
            print(f"\n  {CYAN('a · b')}  = {GREEN(BOLD(_fmt(dot)))}")
            print(f"  {CYAN('|a|')}    = {GREEN(_fmt(mag_a))}")
            print(f"  {CYAN('|b|')}    = {GREEN(_fmt(mag_b))}")
            if mag_a > 0 and mag_b > 0:
                angle = math.acos(max(-1, min(1, dot / (mag_a * mag_b))))
                print(f"  {CYAN('Angle')}  = {GREEN(_fmt(math.degrees(angle)))}°\n")

        elif idx == 6:
            print(f"\n  {CYAN('Cross product:')}  a × b  (3D)")
            a = [_get_float(f"a[{i+1}]") for i in range(3)]
            if any(v is None for v in a): continue
            b = [_get_float(f"b[{i+1}]") for i in range(3)]
            if any(v is None for v in b): continue
            cx = a[1]*b[2] - a[2]*b[1]
            cy = a[2]*b[0] - a[0]*b[2]
            cz = a[0]*b[1] - a[1]*b[0]
            print(f"\n  {CYAN('a × b')}  = ({GREEN(_fmt(cx))},  {GREEN(_fmt(cy))},  {GREEN(_fmt(cz))})")
            print(f"  {CYAN('|a × b|')} = {GREEN(BOLD(_fmt(math.sqrt(cx*cx + cy*cy + cz*cz))))}\n")


# ── Advanced → Differential Calculus ─────────────────────────────────────────

def menu_differential_calculus() -> None:
    while True:
        idx = _menu_select("Differential Calculus", [
            "Higher-order derivatives  f ⁽ⁿ⁾(a)",
            "Taylor polynomial at a  (up to 4th order)",
            "Critical points  (find x where f '(x) ≈ 0)",
            "Tangent line at a point",
            "Concavity & inflection points",
        ])
        if idx < 0:
            return

        if idx == 0:
            expr = _get_expr_prompt("f(x)")
            if expr is None: continue
            a = _get_float("Point a")
            if a is None: continue
            print(f"\n  {CYAN('f(x)')}  = {BOLD(expr)}  at  x = {YELLOW(_fmt(a))}\n")
            for order in range(5):
                try:
                    if order == 0:
                        val = evaluate(expr, {"x": a})
                        lbl = "f(a)"
                    else:
                        val = _nderiv(expr, a, order)
                        primes = "'" * order
                        lbl = ("f" + primes + "(a)") if order <= 3 else "f⁽⁴⁾(a)"
                    print(f"    {CYAN(lbl):20} = {GREEN(_fmt(val))}")
                except Exception as exc:
                    print(f"    {CYAN(f'order {order}'):20}   {RED(str(exc))}")
            print()

        elif idx == 1:
            expr = _get_expr_prompt("f(x)")
            if expr is None: continue
            a = _get_float("Expansion point a")
            if a is None: continue
            try:
                f0 = evaluate(expr, {"x": a})
                d = [_nderiv(expr, a, k) for k in range(1, 5)]
                print(f"\n  {CYAN('Taylor polynomial')} of {BOLD(expr)} around x = {YELLOW(_fmt(a))}\n")
                print(f"  P(x) ≈  {GREEN(_fmt(f0))}")
                factorials = [1, 1, 2, 6, 24]
                signs = ["+"] * 4
                for k, dk in enumerate(d, 1):
                    c = dk / factorials[k]
                    s = "+" if c >= 0 else "-"
                    print(f"       {s}  {GREEN(_fmt(abs(c)))} · (x − {_fmt(a)})^{k}")
                print()
            except Exception as exc:
                print(RED(f"  Error: {exc}"))

        elif idx == 2:
            expr = _get_expr_prompt("f(x)")
            if expr is None: continue
            a = _get_float("Search range start")
            if a is None: continue
            b = _get_float("Search range end")
            if b is None: continue
            n_pts = 500
            step = (b - a) / n_pts
            crits = []
            try:
                prev_d = _nderiv(expr, a, 1)
                for i in range(1, n_pts + 1):
                    x1 = a + i * step
                    cur_d = _nderiv(expr, x1, 1)
                    if prev_d * cur_d < 0:
                        xm = x1 - step / 2
                        crits.append(xm)
                    prev_d = cur_d
            except Exception as exc:
                print(RED(f"  Error sampling: {exc}")); continue
            print(f"\n  {CYAN('Critical points of')} {BOLD(expr)}")
            if not crits:
                print(f"  {DIM('None found in ['+ _fmt(a) + ', ' + _fmt(b) + ']')}")
            else:
                for xc in crits:
                    try:
                        fc = evaluate(expr, {"x": xc})
                        d2 = _nderiv(expr, xc, 2)
                        kind = "local min" if d2 > 0 else "local max" if d2 < 0 else "saddle?"
                        print(f"    x ≈ {YELLOW(_fmt(xc)):15}  f(x) ≈ {GREEN(_fmt(fc)):15}  {DIM('→ ' + kind)}")
                    except Exception:
                        print(f"    x ≈ {YELLOW(_fmt(xc))}")
            print()

        elif idx == 3:
            expr = _get_expr_prompt("f(x)")
            if expr is None: continue
            a = _get_float("Point a")
            if a is None: continue
            try:
                fa = evaluate(expr, {"x": a})
                slope = _nderiv(expr, a, 1)
                intercept = fa - slope * a
                s = "+" if intercept >= 0 else "-"
                print(f"\n  {CYAN('Tangent line at')} x = {YELLOW(_fmt(a))}")
                print(f"    f({_fmt(a)}) = {GREEN(_fmt(fa))}")
                print(f"    slope     = {GREEN(_fmt(slope))}")
                print(f"    y = {GREEN(_fmt(slope))}·x  {s}  {GREEN(_fmt(abs(intercept)))}\n")
            except Exception as exc:
                print(RED(f"  Error: {exc}"))

        elif idx == 4:
            expr = _get_expr_prompt("f(x)")
            if expr is None: continue
            a = _get_float("Interval start")
            if a is None: continue
            b = _get_float("Interval end")
            if b is None: continue
            n_pts = 300
            step = (b - a) / n_pts
            inflections = []
            try:
                prev_d2 = _nderiv(expr, a, 2)
                for i in range(1, n_pts + 1):
                    x1 = a + i * step
                    cur_d2 = _nderiv(expr, x1, 2)
                    if prev_d2 * cur_d2 < 0:
                        inflections.append(x1 - step / 2)
                    prev_d2 = cur_d2
                # Report concavity
                mid = (a + b) / 2
                d2mid = _nderiv(expr, mid, 2)
                conc = "concave up (f'' > 0)" if d2mid > 0 else "concave down (f'' < 0)"
                print(f"\n  {CYAN('Concavity of')} {BOLD(expr)} on [{_fmt(a)}, {_fmt(b)}]")
                print(f"  Mid-interval: {CYAN(conc)}")
                if inflections:
                    print(f"  Inflection points:")
                    for xi in inflections:
                        print(f"    x ≈ {YELLOW(_fmt(xi))}")
                else:
                    print(f"  {DIM('No inflection points found.')}")
                print()
            except Exception as exc:
                print(RED(f"  Error: {exc}"))


# ── Advanced → Complex Analysis ───────────────────────────────────────────────

def _cplx_input(label: str) -> Optional[complex]:
    try:
        raw = input(f"  {label} (e.g.  3+4j  or  3,4): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if raw.lower() in ("q", "quit", "back", ""):
        return None
    raw_clean = raw.replace("(", "").replace(")", "").replace(" ", "")
    if "," in raw_clean:
        parts = raw_clean.split(",")
        try:
            return complex(float(parts[0]), float(parts[1]))
        except (ValueError, IndexError):
            pass
    raw_j = re.sub(r"(\d)i\b", r"\1j", raw_clean)
    try:
        return complex(raw_j)
    except ValueError:
        print(RED(f"  Invalid: use 3+4j or 3,4")); return None

def _cplx_show(z: complex, label: str = "z") -> None:
    r   = abs(z)
    arg = math.atan2(z.imag, z.real)
    print(f"  {CYAN(label):6} = {GREEN(_fmt(z.real))} + {GREEN(_fmt(z.imag))}j")
    print(f"  {'|'+label+'|':6} = {YELLOW(_fmt(r))}  {DIM('(modulus)')}")
    print(f"  {'arg':6} = {YELLOW(_fmt(math.degrees(arg)))}°  {DIM('(' + _fmt(arg) + ' rad)')}")
    print()


def menu_complex_analysis() -> None:
    while True:
        idx = _menu_select("Complex Analysis", [
            "Arithmetic  (z₁ ± × ÷ z₂)",
            "Modulus & argument (polar form)",
            "Conjugate  (z*)",
            "Complex power  (zⁿ)",
            "nth roots of a complex number",
            "Euler's formula  e^(iθ)",
        ])
        if idx < 0:
            return

        if idx == 0:
            z1 = _cplx_input("z₁")
            if z1 is None: continue
            z2 = _cplx_input("z₂")
            if z2 is None: continue
            print()
            for sym, val in [("+", z1+z2), ("-", z1-z2), ("×", z1*z2)]:
                r = abs(val)
                print(f"  z₁ {sym} z₂  = {GREEN(_fmt(val.real))} + {GREEN(_fmt(val.imag))}j  "
                      f"{DIM('|·| = ' + _fmt(r))}")
            if abs(z2) > 1e-15:
                val = z1 / z2
                print(f"  z₁ ÷ z₂  = {GREEN(_fmt(val.real))} + {GREEN(_fmt(val.imag))}j  "
                      f"{DIM('|·| = ' + _fmt(abs(val)))}")
            else:
                print(f"  z₁ ÷ z₂  = {RED('undefined (z₂ = 0)')}")
            print()

        elif idx == 1:
            z = _cplx_input("z")
            if z is None: continue
            r   = abs(z)
            arg = math.atan2(z.imag, z.real)
            print(f"\n  {CYAN('Rectangular')} : {GREEN(_fmt(z.real))} + {GREEN(_fmt(z.imag))}j")
            print(f"  {CYAN('Polar')}        : {YELLOW(_fmt(r))} · e^(i·{_fmt(arg)} rad)")
            print(f"  {CYAN('Degrees')}      : {YELLOW(_fmt(math.degrees(arg)))}°\n")

        elif idx == 2:
            z = _cplx_input("z")
            if z is None: continue
            conj = z.conjugate()
            print(f"\n  {CYAN('z')}   = {GREEN(_fmt(z.real))} + {GREEN(_fmt(z.imag))}j")
            print(f"  {CYAN('z*')}  = {GREEN(_fmt(conj.real))} + {GREEN(_fmt(conj.imag))}j")
            print(f"  {CYAN('z·z*')} = {YELLOW(_fmt((z * conj).real))}  {DIM('(= |z|²)')}\n")

        elif idx == 3:
            z = _cplx_input("z")
            if z is None: continue
            n = _get_float("Exponent n (integer or fractional)")
            if n is None: continue
            val = z ** n
            print(f"\n  {CYAN('z^n')}  = {GREEN(_fmt(val.real))} + {GREEN(_fmt(val.imag))}j  "
                  f"{DIM('|·| = ' + _fmt(abs(val)))}\n")

        elif idx == 4:
            z = _cplx_input("z")
            if z is None: continue
            n = _get_float("Root order n")
            if n is None or n == 0: continue
            n = int(abs(n))
            r    = abs(z) ** (1.0 / n)
            arg0 = math.atan2(z.imag, z.real)
            print(f"\n  {CYAN(str(n)+'th roots of')} {GREEN(_fmt(z.real))} + {GREEN(_fmt(z.imag))}j\n")
            for k in range(n):
                angle = (arg0 + 2 * math.pi * k) / n
                root = complex(r * math.cos(angle), r * math.sin(angle))
                print(f"  k={k}:  {GREEN(_fmt(root.real))} + {GREEN(_fmt(root.imag))}j  "
                      f"{DIM('|·| = ' + _fmt(abs(root)))}")
            print()

        elif idx == 5:
            theta = _get_float("Angle θ in degrees")
            if theta is None: continue
            rad = math.radians(theta)
            val = complex(math.cos(rad), math.sin(rad))
            print(f"\n  {CYAN('e^(iθ)')}  where θ = {YELLOW(_fmt(theta))}°  ({_fmt(rad)} rad)")
            print(f"  = cos(θ) + i·sin(θ)")
            print(f"  = {GREEN(_fmt(val.real))} + {GREEN(_fmt(val.imag))}j\n")


# ── Advanced Mathematics (top menu) ──────────────────────────────────────────

def menu_advanced_math() -> None:
    SECTIONS = [
        ("Calculus                (limits, derivatives, integrals)", menu_calculus),
        ("Linear Algebra          (matrices, determinants, systems)", menu_linear_algebra),
        ("Differential Calculus   (Taylor, critical points, concavity)", menu_differential_calculus),
        ("Complex Analysis        (arithmetic, polar, roots, Euler)", menu_complex_analysis),
    ]
    while True:
        idx = _menu_select("Advanced Mathematics", [s[0] for s in SECTIONS])
        if idx < 0:
            return
        SECTIONS[idx][1]()


# ── Main interactive menu ─────────────────────────────────────────────────────

def run_main_menu(mem: Memory, hist: History) -> None:
    print(f"\n  {CYAN('╔══════════════════════════════════════════╗')}")
    print(f"  {CYAN('║')}  {BOLD('Scientific Calculator')}                  {CYAN('║')}")
    print(f"  {CYAN('║')}  {DIM('zero dependencies · free forever')}       {CYAN('║')}")
    print(f"  {CYAN('╚══════════════════════════════════════════╝')}\n")

    SECTIONS = [
        ("Basic Arithmetic          (+  −  ×  ÷  ^  mod)", menu_basic_arithmetic),
        ("Geometric Shapes          (area & perimeter)",    menu_geometric_shapes),
        ("Advanced Mathematics      (calculus · algebra · complex)", menu_advanced_math),
        ("Expression Calculator     (free-form REPL + variables + plot)", lambda: repl(mem, hist)),
    ]
    while True:
        idx = _menu_select("Main Menu", [s[0] for s in SECTIONS])
        if idx < 0:
            print(f"\n  {DIM('Goodbye!')}\n"); return
        SECTIONS[idx][1]()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Scientific calculator")
    ap.add_argument("expression", nargs="?", help="Evaluate one expression and exit")
    ap.add_argument("--ai",   metavar="QUERY", help="Natural-language query")
    ap.add_argument("--plot", metavar="EXPR",  help="Plot a function of x")
    ap.add_argument("--from", dest="x_min", type=float, default=-10.0)
    ap.add_argument("--to",   dest="x_max", type=float, default=10.0)
    ap.add_argument("--test", action="store_true", help="Run built-in tests")
    args = ap.parse_args()

    if args.test:
        run_tests(); return

    if args.plot:
        plot_ascii(args.plot, args.x_min, args.x_max); return

    mem, hist = Memory(), History()

    if args.ai:
        try:
            expr = nl_to_expr(args.ai)
            result = evaluate(expr)
            print(f"{args.ai!r}  →  {expr}  =  {_fmt(result)}")
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr); sys.exit(1)
    elif args.expression:
        try:
            print(_fmt(evaluate(args.expression)))
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr); sys.exit(1)
    else:
        run_main_menu(mem, hist)


if __name__ == "__main__":
    main()
