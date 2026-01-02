#!/usr/bin/env python3
"""
Cash tracker CLI with SQLite backend and CSV migration/export.

Usage examples:
  python app.py add --amount 5000 --direction income --category Salary --account Wallet --description "January salary"
  python app.py add                # interactive prompts
  python app.py list --limit 20
  python app.py balance
  python app.py monthly --month 2026-01
  python app.py export --out backup.csv
  python app.py migrate         # import from transactions.csv into SQLite
"""
import csv
import uuid
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

DB_FILE = Path("transactions.db")
CSV_FILE = Path("transactions.csv")
FIELDNAMES = ["id", "date", "amount", "direction", "category", "account", "description", "tags"]

SQL_INIT = """
CREATE TABLE IF NOT EXISTS transactions (
  id TEXT PRIMARY KEY,
  date TEXT NOT NULL,
  amount REAL NOT NULL,
  direction TEXT CHECK(direction IN ('income','expense')) NOT NULL,
  category TEXT,
  account TEXT,
  description TEXT,
  tags TEXT
);
"""


def get_conn():
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    with conn:
        conn.executescript(SQL_INIT)
    conn.close()


def add_transaction_db(amount: float, direction: str, category: str, account: str, description: str, tags: str, date: Optional[str] = None, tid: Optional[str] = None):
    init_db()
    tid = tid or str(uuid.uuid4())
    date = date or datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO transactions (id, date, amount, direction, category, account, description, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (tid, date, float(amount), direction, category or None, account or None, description or None, tags or None)
        )
    print(f"Saved transaction {tid}")


def read_transactions_db() -> List[Dict]:
    init_db()
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM transactions ORDER BY date DESC")
        rows = [dict(r) for r in cur.fetchall()]
    return rows


def list_transactions(limit: int = 50):
    rows = read_transactions_db()
    for row in rows[:limit]:
        date = row.get("date", "")
        amt = f"{row.get('amount', 0):.2f}"
        dir_ = row.get("direction", "")
        cat = row.get("category", "") or ""
        acc = row.get("account", "") or ""
        desc = row.get("description", "") or ""
        print(f"{date} | {dir_:7} | {amt:>10} | {cat:12} | {acc:8} | {desc}")


def show_balance():
    init_db()
    income = expense = 0.0
    with get_conn() as conn:
        cur = conn.execute("SELECT amount, direction FROM transactions")
        for r in cur.fetchall():
            a = float(r["amount"] or 0)
            if r["direction"] == "income":
                income += a
            else:
                expense += a
    bal = income - expense
    print(f"Income total : {income:.2f}")
    print(f"Expense total: {expense:.2f}")
    print(f"Balance      : {bal:.2f}")


def monthly_report(month: str):
    # month format: YYYY-MM
    init_db()
    income = expense = 0.0
    with get_conn() as conn:
        cur = conn.execute("SELECT amount, direction, date FROM transactions WHERE date LIKE ?", (f"{month}%",))
        for r in cur.fetchall():
            a = float(r["amount"] or 0)
            if r["direction"] == "income":
                income += a
            else:
                expense += a
    print(f"Report for {month}:")
    print(f"  Income : {income:.2f}")
    print(f"  Expense: {expense:.2f}")
    print(f"  Net    : {income - expense:.2f}")


def export_csv(out: str):
    rows = read_transactions_db()
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in rows:
            # ensure values match fieldnames order
            row = {k: (r.get(k) if r.get(k) is not None else "") for k in FIELDNAMES}
            writer.writerow(row)
    print(f"Exported to {out}")


def migrate_from_csv():
    if not CSV_FILE.exists():
        print("No transactions.csv file found to migrate.")
        return
    init_db()
    imported = 0
    with open(CSV_FILE, "r", newline="", encoding="utf-8") as f, get_conn() as conn:
        reader = csv.DictReader(f)
        for r in reader:
            # Basic validation/normalization
            tid = r.get("id") or str(uuid.uuid4())
            date = r.get("date") or datetime.now().isoformat()
            try:
                amount = float(r.get("amount") or 0)
            except ValueError:
                print(f"Skipping row with invalid amount: {r}")
                continue
            direction = r.get("direction") or ("income" if amount >= 0 else "expense")
            category = r.get("category") or None
            account = r.get("account") or None
            description = r.get("description") or None
            tags = r.get("tags") or None
            conn.execute(
                "INSERT OR IGNORE INTO transactions (id, date, amount, direction, category, account, description, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (tid, date, amount, direction, category, account, description, tags)
            )
            imported += 1
    print(f"Imported {imported} transactions from transactions.csv into SQLite database {DB_FILE}")


def prompt_text(prompt: str, default: Optional[str] = None) -> str:
    if default:
        val = input(f"{prompt} [{default}]: ").strip()
        return val if val else default
    return input(f"{prompt}: ").strip()


def prompt_amount() -> float:
    while True:
        val = input("Amount: ").strip()
        try:
            a = float(val)
            return a
        except ValueError:
            print("Please enter a valid number for amount.")


def prompt_direction() -> str:
    while True:
        val = input("Direction (income/expense): ").strip().lower()
        if val in ("income", "expense"):
            return val
        print("Please enter 'income' or 'expense'.")


def interactive_add(args):
    # Fill missing fields via interactive prompts
    amount = args.amount if args.amount is not None else prompt_amount()
    direction = args.direction if args.direction is not None else prompt_direction()
    category = args.category if args.category else prompt_text("Category (optional)", "")
    account = args.account if args.account else prompt_text("Account (optional)", "")
    description = args.description if args.description else prompt_text("Description (optional)", "")
    tags = args.tags if args.tags else prompt_text("Tags (comma separated, optional)", "")
    date = args.date if getattr(args, "date", None) else prompt_text("Date (ISO 8601, leave blank for now)", "")
    date = date if date else None
    add_transaction_db(amount, direction, category, account, description, tags, date)


def parse_args():
    p = argparse.ArgumentParser(prog="app.py", description="Simple cash tracker (SQLite)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a_add = sub.add_parser("add", help="Add a transaction (use flags or run interactively)")
    a_add.add_argument("--amount", type=float, required=False)
    a_add.add_argument("--direction", choices=["income", "expense"], required=False)
    a_add.add_argument("--category", default="")
    a_add.add_argument("--account", default="")
    a_add.add_argument("--description", default="")
    a_add.add_argument("--tags", default="")
    a_add.add_argument("--date", default=None, help="ISO date/time, defaults to now")

    a_list = sub.add_parser("list", help="List recent transactions")
    a_list.add_argument("--limit", type=int, default=50)

    a_bal = sub.add_parser("balance", help="Show totals and balance")

    a_mon = sub.add_parser("monthly", help="Show monthly totals (YYYY-MM)")
    a_mon.add_argument("--month", default=datetime.now().strftime("%Y-%m"), help="Format YYYY-MM")

    a_exp = sub.add_parser("export", help="Export CSV copy")
    a_exp.add_argument("--out", default="transactions-export.csv")

    a_mig = sub.add_parser("migrate", help="Migrate existing transactions.csv into SQLite database")

    return p.parse_args()


def main():
    args = parse_args()
    if args.cmd == "add":
        if args.amount is None or args.direction is None:
            interactive_add(args)
        else:
            add_transaction_db(args.amount, args.direction, args.category, args.account, args.description, args.tags, args.date)
    elif args.cmd == "list":
        list_transactions(args.limit)
    elif args.cmd == "balance":
        show_balance()
    elif args.cmd == "monthly":
        monthly_report(args.month)
    elif args.cmd == "export":
        export_csv(args.out)
    elif args.cmd == "migrate":
        migrate_from_csv()
    else:
        print("Unknown command")


if __name__ == "__main__":
    main()
