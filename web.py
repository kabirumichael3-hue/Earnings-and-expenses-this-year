#!/usr/bin/env python3
"""Flask web UI for the cash tracker.

Run:
  pip install -r requirements.txt
  python web.py

The web UI uses the same SQLite DB file (transactions.db) as the CLI.
If you haven't migrated your CSV yet, run: python app.py migrate
"""
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import sqlite3
from pathlib import Path
from datetime import datetime
import csv
import io
import json

DB_FILE = Path("transactions.db")
FIELDNAMES = ["id", "date", "amount", "direction", "category", "account", "description", "tags"]

app = Flask(__name__)
app.secret_key = "dev-secret-for-local-use-only"  # change for production


def get_conn():
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    # totals
    with get_conn() as conn:
        cur = conn.execute("SELECT SUM(CASE WHEN direction='income' THEN amount ELSE 0 END) AS income, SUM(CASE WHEN direction='expense' THEN amount ELSE 0 END) AS expense FROM transactions")
        totals = cur.fetchone()
        income = totals["income"] or 0.0
        expense = totals["expense"] or 0.0
        balance = income - expense

        # expense by category
        cur = conn.execute("SELECT COALESCE(category, 'Uncategorized') AS category, SUM(amount) AS total FROM transactions WHERE direction='expense' GROUP BY category ORDER BY total DESC")
        expense_by_cat = [{"category": r["category"], "total": r["total"]} for r in cur.fetchall()]

        # monthly net for last 12 months (YYYY-MM)
        cur = conn.execute("""
            SELECT substr(date,1,7) AS month, SUM(CASE WHEN direction='income' THEN amount ELSE -amount END) AS net
            FROM transactions
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """)
        rows = cur.fetchall()
        monthly = list(reversed([{"month": r["month"], "net": r["net"] or 0.0} for r in rows]))

    # Pass data to template as JSON for charts
    return render_template("index.html",
                           income=income,
                           expense=expense,
                           balance=balance,
                           expense_by_cat=json.dumps(expense_by_cat),
                           monthly=json.dumps(monthly))


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", "0").strip())
        except ValueError:
            flash("Please enter a valid amount.", "danger")
            return redirect(url_for("add"))

        direction = request.form.get("direction") or "expense"
        category = request.form.get("category") or None
        account = request.form.get("account") or None
        description = request.form.get("description") or None
        tags = request.form.get("tags") or None
        date_in = request.form.get("date") or None
        date = date_in.strip() if date_in else datetime.now().isoformat()

        tid = request.form.get("id")  # optional hidden id
        if not tid:
            import uuid
            tid = str(uuid.uuid4())

        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO transactions (id, date, amount, direction, category, account, description, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (tid, date, amount, direction, category, account, description, tags)
            )
        flash("Transaction saved.", "success")
        return redirect(url_for("index"))
    # GET
    return render_template("add.html")


@app.route("/list")
def list_view():
    limit = int(request.args.get("limit", 200))
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM transactions ORDER BY date DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
    return render_template("list.html", rows=rows)


@app.route("/export")
def export():
    # Stream CSV from DB
    si = io.StringIO()
    writer = csv.DictWriter(si, fieldnames=FIELDNAMES)
    writer.writeheader()
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM transactions ORDER BY date DESC")
        for r in cur.fetchall():
            row = {k: (r[k] if r[k] is not None else "") for k in FIELDNAMES}
            writer.writerow(row)
    mem = io.BytesIO()
    mem.write(si.getvalue().encode("utf-8"))
    mem.seek(0)
    now = datetime.now().strftime("%Y%m%d-%H%M%S")
    return send_file(mem, as_attachment=True, download_name=f"transactions-{now}.csv", mimetype="text/csv")


if __name__ == "__main__":
    # Ensure DB exists; if not, the CLI app.py can create/init schema via migrate or we create minimal table here.
    if not DB_FILE.exists():
        # create minimal table if missing (same schema as CLI)
        with get_conn() as conn:
            conn.executescript("""
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
            """)
    app.run(host="0.0.0.0", port=5000, debug=True)
