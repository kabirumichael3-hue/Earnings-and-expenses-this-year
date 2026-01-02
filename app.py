#!/usr/bin/env python3
"""
Simple cash tracker CLI (CSV backend)

Usage examples:
  python app.py add --amount 5000 --direction income --category Salary --account Wallet --description "January salary"
  python app.py add --amount 200 --direction expense --category Food --account Cash --description "Lunch"
  python app.py add                # interactive prompts
  python app.py list --limit 20
  python app.py balance
  python app.py monthly --month 2026-01
  python app.py export --out backup.csv
"""
import csv
import uuid
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Optional

CSV_FILE = Path("transactions.csv")
FIELDNAMES = ["id", "date", "amount", "direction", "category", "account", "description", "tags"]


def ensure_csv():
    if not CSV_FILE.exists():
        with CSV_FILE.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()


def add_transaction(amount: float, direction: str, category: str, account: str, description: str, tags: str, date: Optional[str] = None):
    ensure_csv()
    tid = str(uuid.uuid4())
    date = date or datetime.now().isoformat()
    row = {
        "id": tid,
        "date": date,
        "amount": f"{abs(amount):.2f}",
        "direction": direction,
        "category": category or "",
        "account": account or "",
        "description": description or "",
        "tags": tags or ""
    }
    with CSV_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(row)
    print(f"Saved transaction {tid}")


def read_transactions() -> List[dict]:
    ensure_csv()
    with CSV_FILE.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [r for r in reader]


def list_transactions(limit: int = 50):
    rows = read_transactions()
    rows_sorted = sorted(rows, key=lambda r: r["date"], reverse=True)
    for row in rows_sorted[:limit]:
        date = row["date"]
        amt = row["amount"]
        dir_ = row["direction"]
        cat = row.get("category",
")
        acc = row.get("account",
")
        desc = row.get("description",
")
        print(f"{date} | {dir_:7} | {amt:>10} | {cat:12} | {acc:8} | {desc}")


def show_balance():
    rows = read_transactions()
    bal = 0.0
    income = 0.0
    expense = 0.0
    for r in rows:
        a = float(r.get("amount") or 0)
        if r.get("direction") == "income":
            income += a
            bal += a
        else:
            expense += a
            bal -= a
    print(f"Income total : {income:.2f}")
    print(f"Expense total: {expense:.2f}")
    print(f"Balance      : {bal:.2f}")


def monthly_report(month: str):
    # month format: YYYY-MM
    rows = read_transactions()
    income = expense = 0.0
    for r in rows:
        if r.get("date", "").startswith(month):
            a = float(r.get("amount") or 0)
            if r.get("direction") == "income":
                income += a
            else:
                expense += a
    print(f"Report for {month}:")
    print(f"  Income : {income:.2f}")
    print(f"  Expense: {expense:.2f}")
    print(f"  Net    : {income - expense:.2f}")


def export_csv(out: str):
    ensure_csv()
    with CSV_FILE.open("r", newline="", encoding="utf-8") as src, open(out, "w", newline="", encoding="utf-8") as dst:
        dst.write(src.read())
    print(f"Exported to {out}")


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
    add_transaction(amount, direction, category, account, description, tags, date)


def parse_args():
    p = argparse.ArgumentParser(prog="app.py", description="Simple cash tracker (CSV)")
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

    return p.parse_args()


def main():
    args = parse_args()
    if args.cmd == "add":
        # If amount or direction missing, run interactive prompts; otherwise use provided flags.
        if args.amount is None or args.direction is None:
            interactive_add(args)
        else:
            add_transaction(args.amount, args.direction, args.category, args.account, args.description, args.tags, args.date)
    elif args.cmd == "list":
        list_transactions(args.limit)
    elif args.cmd == "balance":
        show_balance()
    elif args.cmd == "monthly":
        monthly_report(args.month)
    elif args.cmd == "export":
        export_csv(args.out)
    else:
        print("Unknown command")


if __name__ == "__main__":
    main()
