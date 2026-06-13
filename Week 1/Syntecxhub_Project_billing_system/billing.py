"""
Restaurant Billing System — Syntec Internship Week 1
Run: python billing.py
"""

import csv
import datetime
import os
import sys
import uuid
from collections import deque
from pathlib import Path
from typing import Optional

# ── ANSI colour helpers ────────────────────────────────────────────────────────
def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m"

GREEN   = lambda t: _c("92", t)
RED     = lambda t: _c("91", t)
YELLOW  = lambda t: _c("93", t)
CYAN    = lambda t: _c("96", t)
BLUE    = lambda t: _c("94", t)
MAGENTA = lambda t: _c("95", t)
BOLD    = lambda t: _c("1",  t)
DIM     = lambda t: _c("2",  t)
WHITE   = lambda t: _c("97", t)

def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")

def pause() -> None:
    input(DIM("\n  Press Enter to continue…"))

def hr(char: str = "─", width: int = 56) -> str:
    return char * width

# ── File paths ─────────────────────────────────────────────────────────────────
BASE        = Path(__file__).parent
DATA_DIR    = BASE / "data"
MENU_FILE   = DATA_DIR / "menu.csv"
HISTORY_FILE= DATA_DIR / "order_history.csv"

DATA_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# Domain models
# ══════════════════════════════════════════════════════════════════════════════

class MenuItem:
    """A single item available on the restaurant menu."""

    # (CGST %, SGST %)  per category
    TAX_RATES: dict[str, tuple[float, float]] = {
        "Food":     (2.5, 2.5),
        "Beverage": (6.0, 6.0),
        "Dessert":  (2.5, 2.5),
        "Special":  (6.0, 6.0),
    }
    CATEGORIES = list(TAX_RATES.keys())

    def __init__(self, item_id: str, name: str, price: float, category: str) -> None:
        self.item_id  = item_id
        self.name     = name
        self.price    = float(price)
        self.category = category
        cgst, sgst    = self.TAX_RATES.get(category, (2.5, 2.5))
        self.cgst     = cgst
        self.sgst     = sgst

    @property
    def total_tax_rate(self) -> float:
        return self.cgst + self.sgst

    def __repr__(self) -> str:
        return f"MenuItem({self.item_id}, {self.name!r}, ₹{self.price:.2f}, {self.category})"


class OrderItem:
    """A menu item paired with a quantity in a specific order."""

    def __init__(self, item: MenuItem, qty: int) -> None:
        self.item = item
        self.qty  = qty

    @property
    def subtotal(self) -> float:
        return self.item.price * self.qty

    @property
    def cgst_amount(self) -> float:
        return self.subtotal * self.item.cgst / 100

    @property
    def sgst_amount(self) -> float:
        return self.subtotal * self.item.sgst / 100

    @property
    def tax_total(self) -> float:
        return self.cgst_amount + self.sgst_amount

    @property
    def line_total(self) -> float:
        return self.subtotal + self.tax_total


class Order:
    """A bill for one table — holds ordered items, discount, payment info."""

    DISCOUNT_CODES: dict[str, tuple[str, float]] = {
        "HAPPY10":  ("Happy Hour",       10.0),
        "WELCOME5": ("Welcome Offer",     5.0),
        "LOYAL15":  ("Loyalty Discount", 15.0),
        "STAFF20":  ("Staff Discount",   20.0),
    }

    def __init__(self, table_no: int) -> None:
        date_tag       = datetime.datetime.now().strftime("%Y%m%d")
        uid            = uuid.uuid4().hex[:6].upper()
        self.order_id  = f"ORD-{date_tag}-{uid}"
        self.table_no  = table_no
        self.created_at: datetime.datetime = datetime.datetime.now()
        self.items: list[OrderItem] = []
        self.discount_code  = ""
        self.discount_pct   = 0.0
        self.discount_label = ""
        self.payment_method = ""
        self.amount_tendered = 0.0
        self.is_closed      = False

    # ── Item management ───────────────────────────────────────────────────────
    def add_item(self, item: MenuItem, qty: int) -> None:
        for oi in self.items:
            if oi.item.item_id == item.item_id:
                oi.qty += qty
                return
        self.items.append(OrderItem(item, qty))

    def remove_item(self, item_id: str) -> bool:
        for i, oi in enumerate(self.items):
            if oi.item.item_id == item_id:
                self.items.pop(i)
                return True
        return False

    def update_qty(self, item_id: str, qty: int) -> bool:
        for oi in self.items:
            if oi.item.item_id == item_id:
                if qty <= 0:
                    return self.remove_item(item_id)
                oi.qty = qty
                return True
        return False

    def apply_discount(self, code: str) -> bool:
        code = code.strip().upper()
        if code in self.DISCOUNT_CODES:
            label, pct          = self.DISCOUNT_CODES[code]
            self.discount_code  = code
            self.discount_pct   = pct
            self.discount_label = label
            return True
        return False

    def remove_discount(self) -> None:
        self.discount_code  = ""
        self.discount_pct   = 0.0
        self.discount_label = ""

    # ── Financial totals ──────────────────────────────────────────────────────
    @property
    def subtotal(self) -> float:
        return sum(oi.subtotal for oi in self.items)

    @property
    def discount_amount(self) -> float:
        return round(self.subtotal * self.discount_pct / 100, 2)

    @property
    def taxable_base(self) -> float:
        return self.subtotal - self.discount_amount

    @property
    def total_cgst(self) -> float:
        factor = 1 - self.discount_pct / 100
        return round(sum(oi.cgst_amount for oi in self.items) * factor, 2)

    @property
    def total_sgst(self) -> float:
        factor = 1 - self.discount_pct / 100
        return round(sum(oi.sgst_amount for oi in self.items) * factor, 2)

    @property
    def grand_total(self) -> float:
        return round(self.taxable_base + self.total_cgst + self.total_sgst, 2)

    @property
    def change_due(self) -> float:
        if self.payment_method == "Cash":
            return max(0.0, round(self.amount_tendered - self.grand_total, 2))
        return 0.0

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Menu manager  (loads / saves menu.csv)
# ══════════════════════════════════════════════════════════════════════════════

class Menu:
    """Manages the restaurant's item catalogue with CSV persistence."""

    _DEFAULT_ITEMS = [
        ("Butter Chicken",        320, "Food"),
        ("Paneer Tikka",          280, "Food"),
        ("Dal Makhani",           220, "Food"),
        ("Veg Biryani",           260, "Food"),
        ("Naan",                   40, "Food"),
        ("Jeera Rice",            120, "Food"),
        ("Samosa (2 pcs)",         60, "Food"),
        ("Masala Chai",            30, "Beverage"),
        ("Cold Coffee",           120, "Beverage"),
        ("Fresh Lime Soda",        80, "Beverage"),
        ("Mango Lassi",           100, "Beverage"),
        ("Mineral Water",          20, "Beverage"),
        ("Gulab Jamun (2 pcs)",    80, "Dessert"),
        ("Kulfi",                  90, "Dessert"),
        ("Rasgulla (2 pcs)",       70, "Dessert"),
        ("Chef's Special Thali",  450, "Special"),
        ("Family Combo",          890, "Special"),
    ]

    def __init__(self) -> None:
        self.items: dict[str, MenuItem] = {}
        self._next_id = 1
        self._load()

    def _load(self) -> None:
        if not MENU_FILE.exists():
            self._seed()
            return
        with open(MENU_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                m = MenuItem(row["id"], row["name"], float(row["price"]), row["category"])
                self.items[m.item_id] = m
                try:
                    n = int(m.item_id.replace("M", ""))
                    if n >= self._next_id:
                        self._next_id = n + 1
                except ValueError:
                    pass

    def save(self) -> None:
        with open(MENU_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["id", "name", "price", "category"])
            w.writeheader()
            for m in self.items.values():
                w.writerow({"id": m.item_id, "name": m.name,
                             "price": m.price, "category": m.category})

    def _seed(self) -> None:
        for name, price, cat in self._DEFAULT_ITEMS:
            mid = f"M{self._next_id:03d}"
            self._next_id += 1
            self.items[mid] = MenuItem(mid, name, float(price), cat)
        self.save()

    def add_item(self, name: str, price: float, category: str) -> MenuItem:
        mid = f"M{self._next_id:03d}"
        self._next_id += 1
        m = MenuItem(mid, name, price, category)
        self.items[mid] = m
        self.save()
        return m

    def remove_item(self, item_id: str) -> bool:
        if item_id in self.items:
            del self.items[item_id]
            self.save()
            return True
        return False

    def get(self, item_id: str) -> Optional[MenuItem]:
        return self.items.get(item_id)

    def by_category(self) -> dict[str, list[MenuItem]]:
        cats: dict[str, list[MenuItem]] = {c: [] for c in MenuItem.CATEGORIES}
        for m in self.items.values():
            cats.setdefault(m.category, []).append(m)
        return cats


# ══════════════════════════════════════════════════════════════════════════════
# Table manager  (multiple concurrent active orders)
# ══════════════════════════════════════════════════════════════════════════════

class TableManager:
    """Opens, tracks, and closes orders across multiple tables."""

    def __init__(self) -> None:
        self.tables: dict[int, Order] = {}   # table_no → active Order
        self.closed: list[Order]      = []   # completed orders this session

    def open_table(self, table_no: int) -> Order:
        if table_no in self.tables:
            raise ValueError(f"Table {table_no} already has an open order.")
        order = Order(table_no)
        self.tables[table_no] = order
        return order

    def get(self, table_no: int) -> Optional[Order]:
        return self.tables.get(table_no)

    def close_table(self, table_no: int) -> Optional[Order]:
        order = self.tables.pop(table_no, None)
        if order:
            order.is_closed = True
            self.closed.append(order)
        return order

    @property
    def open_table_numbers(self) -> list[int]:
        return sorted(self.tables.keys())


# ══════════════════════════════════════════════════════════════════════════════
# History & Reporting
# ══════════════════════════════════════════════════════════════════════════════

class HistoryManager:
    """Appends closed orders to a CSV log and provides session reports."""

    FIELDS = ["order_id", "table_no", "closed_at", "payment_method",
              "subtotal", "discount_pct", "discount_amount",
              "total_cgst", "total_sgst", "grand_total"]

    def log(self, order: Order) -> None:
        write_header = not HISTORY_FILE.exists()
        with open(HISTORY_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=self.FIELDS)
            if write_header:
                w.writeheader()
            w.writerow({
                "order_id":        order.order_id,
                "table_no":        order.table_no,
                "closed_at":       datetime.datetime.now().isoformat(timespec="seconds"),
                "payment_method":  order.payment_method,
                "subtotal":        f"{order.subtotal:.2f}",
                "discount_pct":    f"{order.discount_pct:.1f}",
                "discount_amount": f"{order.discount_amount:.2f}",
                "total_cgst":      f"{order.total_cgst:.2f}",
                "total_sgst":      f"{order.total_sgst:.2f}",
                "grand_total":     f"{order.grand_total:.2f}",
            })

    def load_history(self) -> list[dict]:
        if not HISTORY_FILE.exists():
            return []
        with open(HISTORY_FILE, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def session_report(self, closed: list[Order]) -> None:
        if not closed:
            print(RED("  No orders completed this session."))
            return

        total_rev  = sum(o.grand_total for o in closed)
        total_tax  = sum(o.total_cgst + o.total_sgst for o in closed)
        n_orders   = len(closed)

        # Most popular item
        item_counts: dict[str, tuple[str, int]] = {}
        for o in closed:
            for oi in o.items:
                mid = oi.item.item_id
                name, qty = item_counts.get(mid, (oi.item.name, 0))
                item_counts[mid] = (name, qty + oi.qty)
        top = max(item_counts.values(), key=lambda x: x[1]) if item_counts else ("—", 0)

        payment_summary: dict[str, int] = {}
        for o in closed:
            payment_summary[o.payment_method] = payment_summary.get(o.payment_method, 0) + 1

        W = 56
        print(f"\n  {CYAN(hr('═', W))}")
        print(f"  {BOLD(CYAN('SESSION REPORT'.center(W)))}")
        print(f"  {CYAN(hr('═', W))}")
        print(f"  {'Orders Processed':<28} {BOLD(str(n_orders)):>20}")
        print(f"  {'Total Revenue':<28} {GREEN(BOLD(f'₹{total_rev:,.2f}')):>20}")
        print(f"  {'Total Tax Collected':<28} {YELLOW(f'₹{total_tax:,.2f}'):>20}")
        print(f"  {'Avg. Bill Value':<28} {f'₹{total_rev/n_orders:,.2f}':>20}")
        print(f"  {'Most Popular Item':<28} {top[0][:18]:>20} {DIM(f'x{top[1]}')}")
        if payment_summary:
            print(f"  {CYAN(hr('─', W))}")
            print(f"  {BOLD('Payment Methods:')}")
            for method, count in payment_summary.items():
                print(f"    {method:<20} {count} order(s)")
        print(f"  {CYAN(hr('═', W))}")


# ══════════════════════════════════════════════════════════════════════════════
# Receipt printer
# ══════════════════════════════════════════════════════════════════════════════

RESTAURANT_NAME = "SPICE GARDEN"
RESTAURANT_SUB  = "Authentic Indian Cuisine"
RESTAURANT_ADDR = "42 MG Road, Bengaluru – 560001"
RESTAURANT_GST  = "GSTIN: 29ABCDE1234F1Z5"
RESTAURANT_TEL  = "Tel: +91 80 4567 8901"

ASCII_LOGO = r"""
   _____ ____ ___ ____ _____     ____   _    ____  ____  _____ _   _
  / ____|  _ \_ _/ ___| ____|   / ___| / \  |  _ \|  _ \| ____| \ | |
  \___ \| |_) | | |   |  _|    | |  _ / _ \ | |_) | | | |  _| |  \| |
   ___) |  __/| | |___| |___   | |_| / ___ \|  _ <| |_| | |___| |\  |
  |____/|_|  |___\____|_____|   \____/_/   \_\_| \_\____/|_____|_| \_|
"""

def _pad(label: str, value: str, width: int = 52) -> str:
    space = width - len(label) - len(value)
    return f"  {label}{'.' * max(1, space)}{value}"

def print_receipt(order: Order) -> None:
    W   = 58
    div = "─" * W
    dbl = "═" * W

    ts  = datetime.datetime.now().strftime("%d %b %Y  %H:%M:%S")

    print(f"\n  {CYAN(dbl)}")
    # ASCII restaurant name (compact version)
    print(f"\n  {BOLD(WHITE(RESTAURANT_NAME.center(W)))}")
    print(f"  {DIM(RESTAURANT_SUB.center(W))}")
    print(f"  {DIM(RESTAURANT_ADDR.center(W))}")
    print(f"  {DIM(RESTAURANT_TEL.center(W))}")
    print(f"  {DIM(RESTAURANT_GST.center(W))}")
    print(f"\n  {CYAN(dbl)}")

    print(f"  {BOLD('TAX INVOICE')}")
    print(f"  Order ID : {YELLOW(order.order_id)}")
    print(f"  Table    : {BOLD(str(order.table_no))}")
    print(f"  Date     : {ts}")
    print(f"  {CYAN(div)}")

    # Column header
    hdr = f"  {'Item':<28} {'Qty':>4}  {'Rate':>7}  {'Amount':>8}"
    print(BOLD(hdr))
    print(f"  {div}")

    for oi in order.items:
        name = oi.item.name[:27]
        rate = f"₹{oi.item.price:>6.2f}"
        amt  = f"₹{oi.subtotal:>7.2f}"
        print(f"  {name:<28} {oi.qty:>4}  {rate:>7}  {amt:>8}")
        # Tax detail per line
        tax_info = (f"    {DIM('CGST')} {DIM(f'{oi.item.cgst:.1f}%')} "
                    f"{DIM(f'₹{oi.cgst_amount:.2f}')}  "
                    f"{DIM('SGST')} {DIM(f'{oi.item.sgst:.1f}%')} "
                    f"{DIM(f'₹{oi.sgst_amount:.2f}')}")
        print(tax_info)

    print(f"  {div}")

    # Subtotal
    sub_s = f"₹{order.subtotal:.2f}"
    print(f"  {'Subtotal':<44} {sub_s:>8}")

    # Discount
    if order.discount_pct > 0:
        disc_s = f"-₹{order.discount_amount:.2f}"
        label  = f"Discount ({order.discount_label} {order.discount_pct:.0f}%)"
        print(f"  {RED(label):<44} {RED(disc_s):>8}")
        tax_base_s = f"₹{order.taxable_base:.2f}"
        print(f"  {'Taxable Amount':<44} {tax_base_s:>8}")

    # Tax summary
    cgst_s = f"₹{order.total_cgst:.2f}"
    sgst_s = f"₹{order.total_sgst:.2f}"
    print(f"  {'CGST':<44} {YELLOW(cgst_s):>8}")
    print(f"  {'SGST':<44} {YELLOW(sgst_s):>8}")

    print(f"  {dbl}")
    gt_s = f"₹{order.grand_total:.2f}"
    print(f"  {BOLD('GRAND TOTAL'):<44} {GREEN(BOLD(gt_s)):>8}")
    print(f"  {dbl}")

    # Payment
    print(f"  {'Payment Method':<30} {BOLD(order.payment_method)}")
    if order.payment_method == "Cash":
        print(f"  {'Amount Tendered':<30} ₹{order.amount_tendered:.2f}")
        print(f"  {'Change Due':<30} {GREEN(BOLD(f'₹{order.change_due:.2f}'))}")

    print(f"  {CYAN(div)}")
    print(f"  {DIM('Thank you for dining with us!')}")
    print(f"  {DIM('Visit again at spicegarden.in')}")
    print(f"  {CYAN(dbl)}\n")


# ══════════════════════════════════════════════════════════════════════════════
# Input helpers
# ══════════════════════════════════════════════════════════════════════════════

def ask(prompt: str) -> str:
    try:
        return input(f"  {CYAN('›')} {prompt}").strip()
    except (EOFError, KeyboardInterrupt):
        return ""

def ask_int(prompt: str, lo: int = 1, hi: int = 9999) -> Optional[int]:
    raw = ask(prompt)
    if not raw:
        return None
    try:
        n = int(raw)
        if lo <= n <= hi:
            return n
        print(RED(f"  Please enter a number between {lo} and {hi}."))
        return None
    except ValueError:
        print(RED(f"  '{raw}' is not a valid number."))
        return None

def ask_float(prompt: str, lo: float = 0.01) -> Optional[float]:
    raw = ask(prompt)
    if not raw:
        return None
    try:
        v = float(raw)
        if v >= lo:
            return v
        print(RED(f"  Value must be ≥ {lo}."))
        return None
    except ValueError:
        print(RED(f"  '{raw}' is not a valid number."))
        return None

def pick(options: list[str], title: str = "") -> Optional[int]:
    """Show a numbered list and return the chosen 1-based index, or None."""
    W = 54
    if title:
        print(f"\n  {BOLD(CYAN(title))}")
        print(f"  {CYAN(hr('─', W))}")
    for i, opt in enumerate(options, 1):
        print(f"  {DIM(str(i)+'.')} {opt}")
    print(f"  {DIM('0.')} Back / Cancel")
    print(f"  {CYAN(hr('─', W))}")
    raw = ask("Choose: ")
    if raw == "0" or raw.lower() in ("", "back", "cancel"):
        return None
    try:
        n = int(raw)
        if 1 <= n <= len(options):
            return n
        print(RED("  Invalid choice."))
        return None
    except ValueError:
        print(RED("  Enter a number."))
        return None


# ══════════════════════════════════════════════════════════════════════════════
# View helpers
# ══════════════════════════════════════════════════════════════════════════════

def display_menu(menu: Menu, show_ids: bool = False) -> None:
    cats = menu.by_category()
    W    = 56

    print(f"\n  {BOLD(CYAN(hr('═', W)))}")
    print(f"  {BOLD(CYAN('MENU'.center(W)))}")
    print(f"  {BOLD(CYAN(hr('═', W)))}")

    for cat, items in cats.items():
        if not items:
            continue
        cat_colors = {"Food": GREEN, "Beverage": BLUE, "Dessert": MAGENTA, "Special": YELLOW}
        col = cat_colors.get(cat, WHITE)
        print(f"\n  {col(BOLD(f'── {cat} ──'))}")
        print(f"  {DIM(hr('─', W))}")
        hdr_id = f"  {'ID':<7}" if show_ids else "  "
        print(BOLD(f"{hdr_id}{'Item':<30} {'Price':>7}  {'GST':>6}"))
        print(f"  {DIM(hr('─', W))}")
        for m in sorted(items, key=lambda x: x.price):
            id_part = f"{DIM(m.item_id):<7} " if show_ids else "  "
            gst_str = f"{m.total_tax_rate:.0f}%"
            print(f"  {id_part}{m.name:<30} {YELLOW(f'₹{m.price:>6.2f}')}  {DIM(gst_str):>6}")
    print(f"\n  {CYAN(hr('═', W))}")


def display_order(order: Order) -> None:
    if order.is_empty:
        print(YELLOW("  Order is empty."))
        return

    W = 58
    print(f"\n  {BOLD(CYAN(hr('═', W)))}")
    print(f"  {BOLD(f'Table {order.table_no}  ·  {order.order_id}')}")
    print(f"  {CYAN(hr('─', W))}")
    hdr = f"  {'#':<3} {'Item':<27} {'Qty':>4}  {'Price':>7}  {'Amount':>8}"
    print(BOLD(hdr))
    print(f"  {DIM(hr('─', W))}")

    for i, oi in enumerate(order.items, 1):
        name = oi.item.name[:26]
        print(f"  {i:<3} {name:<27} {oi.qty:>4}  ₹{oi.item.price:>6.2f}  ₹{oi.subtotal:>7.2f}")

    print(f"  {CYAN(hr('─', W))}")
    print(f"  {'Subtotal':<46} ₹{order.subtotal:>7.2f}")
    if order.discount_pct:
        disc_lbl = f"Discount ({order.discount_label} −{order.discount_pct:.0f}%)"
        print(f"  {RED(disc_lbl):<46} {RED(f'-₹{order.discount_amount:>6.2f}')}")
    print(f"  {YELLOW('CGST'):<46} {YELLOW(f'₹{order.total_cgst:>7.2f}')}")
    print(f"  {YELLOW('SGST'):<46} {YELLOW(f'₹{order.total_sgst:>7.2f}')}")
    print(f"  {CYAN(hr('─', W))}")
    print(f"  {BOLD('GRAND TOTAL'):<46} {GREEN(BOLD(f'₹{order.grand_total:>7.2f}'))}")
    print(f"  {BOLD(CYAN(hr('═', W)))}")


# ══════════════════════════════════════════════════════════════════════════════
# Table / Order workflow
# ══════════════════════════════════════════════════════════════════════════════

def add_items_flow(order: Order, menu: Menu) -> None:
    display_menu(menu, show_ids=True)
    print(f"\n  {BOLD('Add items to Table ' + str(order.table_no))}")
    print(f"  {DIM('Enter item ID (e.g. M001) or 0 to finish.')}")
    print(f"  {CYAN(hr('─', 54))}")

    while True:
        item_id = ask("Item ID (or 0): ").upper()
        if not item_id or item_id == "0":
            break
        item = menu.get(item_id)
        if not item:
            print(RED(f"  '{item_id}' not found on menu."))
            continue
        qty = ask_int(f"Quantity for '{item.name}': ", lo=1, hi=100)
        if qty is None:
            continue
        order.add_item(item, qty)
        print(GREEN(f"  ✓ Added {qty}× {item.name}  (₹{item.price * qty:.2f})"))


def remove_item_flow(order: Order) -> None:
    if order.is_empty:
        print(YELLOW("  No items to remove."))
        return
    display_order(order)
    item_id = ask("Enter Item ID to remove (e.g. M001): ").upper()
    if order.remove_item(item_id):
        print(GREEN("  ✓ Item removed."))
    else:
        print(RED("  Item not in this order."))


def update_qty_flow(order: Order) -> None:
    if order.is_empty:
        print(YELLOW("  No items to update."))
        return
    display_order(order)
    item_id = ask("Enter Item ID to update (e.g. M001): ").upper()
    qty = ask_int("New quantity (0 to remove): ", lo=0, hi=100)
    if qty is None:
        return
    if order.update_qty(item_id, qty):
        msg = "Removed." if qty == 0 else f"Quantity updated to {qty}."
        print(GREEN(f"  ✓ {msg}"))
    else:
        print(RED("  Item not found in this order."))


def discount_flow(order: Order) -> None:
    if order.discount_code:
        print(f"  Current discount: {GREEN(order.discount_label)} ({order.discount_pct:.0f}%)")
        choice = ask("Remove discount? (y/n): ").lower()
        if choice == "y":
            order.remove_discount()
            print(GREEN("  ✓ Discount removed."))
        return

    print(f"\n  {BOLD('Available Discount Codes:')}")
    for code, (label, pct) in Order.DISCOUNT_CODES.items():
        print(f"  {DIM('•')} {CYAN(code):<12} {label}  ({pct:.0f}% off)")
    print()
    code = ask("Enter discount code (or leave blank to skip): ").upper()
    if not code:
        return
    if order.apply_discount(code):
        print(GREEN(f"  ✓ '{order.discount_label}' applied — {order.discount_pct:.0f}% off."))
    else:
        print(RED(f"  Code '{code}' is not valid."))


def payment_flow(order: Order, tables: TableManager, history: HistoryManager) -> bool:
    """Collect payment details, print receipt, close the order. Returns True on success."""
    if order.is_empty:
        print(RED("  Cannot process payment — order is empty."))
        return False

    display_order(order)

    methods = ["Cash", "Card (Debit/Credit)", "UPI / Digital Wallet"]
    idx = pick(methods, "Select Payment Method")
    if idx is None:
        return False

    method_labels = {1: "Cash", 2: "Card", 3: "UPI"}
    order.payment_method = method_labels[idx]

    if order.payment_method == "Cash":
        while True:
            amount = ask_float(f"Amount tendered (≥ ₹{order.grand_total:.2f}): ",
                               lo=order.grand_total)
            if amount is None:
                return False
            if amount < order.grand_total:
                print(RED(f"  Insufficient — minimum ₹{order.grand_total:.2f} required."))
                continue
            order.amount_tendered = amount
            break

    clear()
    print_receipt(order)
    history.log(order)
    tables.close_table(order.table_no)
    print(GREEN(f"  ✓ Payment complete. Table {order.table_no} is now free.\n"))
    return True


def table_menu(table_no: int, tables: TableManager,
               menu: Menu, history: HistoryManager) -> None:
    """Sub-menu for managing a single active table's order."""
    order = tables.get(table_no)
    if order is None:
        print(RED(f"  Table {table_no} has no open order."))
        return

    while True:
        clear()
        W = 54
        status = GREEN("open") if not order.is_empty else YELLOW("empty")
        items_n = len(order.items)
        gt = f"₹{order.grand_total:.2f}" if not order.is_empty else "—"

        print(f"\n  {BOLD(CYAN(hr('═', W)))}")
        print(f"  {BOLD(f'TABLE {table_no}  ·  {order.order_id}')}")
        print(f"  Items: {items_n}   Total: {GREEN(BOLD(gt))}")
        print(f"  {CYAN(hr('═', W))}")

        options = [
            "Add items",
            "Remove an item",
            "Update item quantity",
            "Apply / remove discount",
            "View current bill",
            f"{BOLD(GREEN('Process payment & print receipt'))}",
        ]
        choice = pick(options)
        if choice is None:
            break
        if choice == 1:
            add_items_flow(order, menu)
            pause()
        elif choice == 2:
            remove_item_flow(order)
            pause()
        elif choice == 3:
            update_qty_flow(order)
            pause()
        elif choice == 4:
            discount_flow(order)
            pause()
        elif choice == 5:
            display_order(order)
            pause()
        elif choice == 6:
            if payment_flow(order, tables, history):
                pause()
                break   # table is closed, go back


# ══════════════════════════════════════════════════════════════════════════════
# Menu management flow
# ══════════════════════════════════════════════════════════════════════════════

def menu_management(menu: Menu) -> None:
    while True:
        clear()
        options = [
            "View full menu",
            "Add new item",
            "Remove an item",
        ]
        choice = pick(options, "Menu Management")
        if choice is None:
            break

        if choice == 1:
            display_menu(menu, show_ids=True)
            pause()

        elif choice == 2:
            print(f"\n  {BOLD('Add New Menu Item')}")
            print(f"  {CYAN(hr('─', 54))}")
            name = ask("Item name: ")
            if not name:
                continue
            price = ask_float("Price (₹): ", lo=0.01)
            if price is None:
                continue
            print("  Categories: " + "  ".join(
                f"{i}. {c}" for i, c in enumerate(MenuItem.CATEGORIES, 1)))
            cat_idx = ask_int("Category number: ", lo=1, hi=len(MenuItem.CATEGORIES))
            if cat_idx is None:
                continue
            category = MenuItem.CATEGORIES[cat_idx - 1]
            item = menu.add_item(name, price, category)
            print(GREEN(f"  ✓ '{item.name}' added as {item.item_id} (₹{item.price:.2f}, {category})."))
            pause()

        elif choice == 3:
            display_menu(menu, show_ids=True)
            item_id = ask("Enter Item ID to remove (e.g. M001): ").upper()
            item = menu.get(item_id)
            if not item:
                print(RED(f"  '{item_id}' not found."))
                pause()
                continue
            confirm = ask(f"Remove '{item.name}'? (y/n): ").lower()
            if confirm == "y":
                menu.remove_item(item_id)
                print(GREEN(f"  ✓ '{item.name}' removed from menu."))
            else:
                print(DIM("  Cancelled."))
            pause()


# ══════════════════════════════════════════════════════════════════════════════
# History viewer
# ══════════════════════════════════════════════════════════════════════════════

def view_history(history: HistoryManager) -> None:
    rows = history.load_history()
    W    = 58

    if not rows:
        print(YELLOW("\n  No order history found."))
        pause()
        return

    print(f"\n  {BOLD(CYAN(hr('═', W)))}")
    print(f"  {BOLD(CYAN('ORDER HISTORY'.center(W)))}")
    print(f"  {CYAN(hr('─', W))}")
    print(BOLD(f"  {'Order ID':<26} {'Table':>5} {'Total':>9} {'Method':<12} Date"))
    print(f"  {DIM(hr('─', W))}")

    total_rev = 0.0
    for row in rows[-30:]:   # last 30
        gt = float(row.get("grand_total", 0))
        total_rev += gt
        print(f"  {DIM(row['order_id']):<26} "
              f"{row['table_no']:>5}  "
              f"{GREEN(f'₹{gt:>7.2f}'):>9}  "
              f"{row['payment_method']:<12}  "
              f"{row.get('closed_at','')[:16]}")

    print(f"  {CYAN(hr('─', W))}")
    print(f"  {'All-time revenue (logged)':<38} {GREEN(BOLD(f'₹{total_rev:,.2f}'))}")
    print(f"  {CYAN(hr('═', W))}")
    pause()


# ══════════════════════════════════════════════════════════════════════════════
# Main menu
# ══════════════════════════════════════════════════════════════════════════════

def print_header(tables: TableManager) -> None:
    W    = 56
    open_tables = tables.open_table_numbers
    closed_n    = len(tables.closed)

    print(f"\n  {BOLD(CYAN(hr('═', W)))}")
    print(f"  {BOLD(WHITE('SPICE GARDEN'.center(W)))}")
    print(f"  {DIM('Restaurant Billing System'.center(W))}")
    print(f"  {CYAN(hr('─', W))}")

    if open_tables:
        tbl_str = "  ".join(
            f"{YELLOW('Table')} {BOLD(str(t))}"
            for t in open_tables
        )
        print(f"  Active: {tbl_str}")
    else:
        print(f"  {DIM('No tables open.')}")

    print(f"  {DIM(f'Orders completed this session: {closed_n}')}")
    print(f"  {CYAN(hr('═', W))}")


def main() -> None:
    clear()
    menu    = Menu()
    tables  = TableManager()
    history = HistoryManager()

    while True:
        clear()
        print_header(tables)

        # Build dynamic main menu
        main_opts: list[str] = []

        # Tables section
        if tables.open_table_numbers:
            for t in tables.open_table_numbers:
                order = tables.get(t)
                items_n = len(order.items) if order else 0
                gt      = f"₹{order.grand_total:.2f}" if order and not order.is_empty else "empty"
                main_opts.append(
                    f"{BOLD(YELLOW('Table ' + str(t)))}  "
                    f"({items_n} item(s), {GREEN(gt)})"
                )

        main_opts.append(f"{CYAN('Open new table')}")
        main_opts.append(f"{'View / edit menu'}")
        main_opts.append(f"{'Session report'}")
        main_opts.append(f"{'Order history (all-time)'}")
        main_opts.append(f"{RED('Exit')}")

        choice = pick(main_opts)
        if choice is None:
            continue

        n_open = len(tables.open_table_numbers)

        # If the choice is one of the open tables
        if choice <= n_open:
            t = tables.open_table_numbers[choice - 1]
            table_menu(t, tables, menu, history)
            continue

        # Offset past the open-table entries
        adjusted = choice - n_open

        if adjusted == 1:       # Open new table
            table_no = ask_int("Table number: ", lo=1, hi=50)
            if table_no is None:
                continue
            if table_no in tables.tables:
                print(RED(f"  Table {table_no} is already open."))
                pause()
                continue
            tables.open_table(table_no)
            print(GREEN(f"  ✓ Table {table_no} opened."))
            pause()
            table_menu(table_no, tables, menu, history)

        elif adjusted == 2:     # View / edit menu
            menu_management(menu)

        elif adjusted == 3:     # Session report
            clear()
            history.session_report(tables.closed)
            pause()

        elif adjusted == 4:     # Order history
            view_history(history)

        elif adjusted == 5:     # Exit
            if tables.open_table_numbers:
                confirm = ask(
                    f"There are {len(tables.open_table_numbers)} open table(s). "
                    "Exit anyway? (y/n): "
                ).lower()
                if confirm != "y":
                    continue
            clear()
            print(f"\n  {GREEN(BOLD('Thank you! Goodbye.'))}\n")
            sys.exit(0)


if __name__ == "__main__":
    main()
