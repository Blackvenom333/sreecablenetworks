from flask import Flask, request, redirect, session, render_template
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "tv_portal_secret_key_2026"

DB_NAME = "tv.db"
MONTHLY_FEE = 250


# ---------------- DATABASE ---------------- #

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS owner (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Active',
        total_paid INTEGER NOT NULL DEFAULT 0,
        UNIQUE(section, customer_id)
    )
    """)

    # Default login
    cur.execute("SELECT COUNT(*) FROM owner")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO owner (username, password) VALUES (?, ?)",
            ("owner", "admin123")
        )

    conn.commit()
    conn.close()


# ---------------- LOGIC ---------------- #

def calculate_customer_status(total_paid):
    months_covered = total_paid // MONTHLY_FEE
    remainder = total_paid % MONTHLY_FEE

    if total_paid == 0:
        due_this_month = MONTHLY_FEE
    elif remainder == 0:
        due_this_month = 0
    else:
        due_this_month = MONTHLY_FEE - remainder

    return months_covered, due_this_month


# ---------------- ROUTES ---------------- #

@app.route("/", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        captcha = request.form.get("captcha")

        if captcha != "7":
            error = "Captcha is incorrect."
            return render_template("login.html", error=error)

        conn = get_db_connection()
        owner = conn.execute(
            "SELECT * FROM owner WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if owner is None:
            error = "Invalid username or password."
            return render_template("login.html", error=error)

        session["owner_logged_in"] = True
        return redirect("/owner")

    return render_template("login.html", error=error)


@app.route("/owner")
def owner_dashboard():
    if not session.get("owner_logged_in"):
        return redirect("/")

    conn = get_db_connection()
    raw_customers = conn.execute(
        "SELECT * FROM customers ORDER BY section, customer_id"
    ).fetchall()
    conn.close()

    customers = []
    pending_count = 0
    paid_count = 0

    for c in raw_customers:
        months, due = calculate_customer_status(c["total_paid"])

        obj = dict(c)
        obj["months_covered"] = months
        obj["due_this_month"] = due

        if due == 0 and c["total_paid"] > 0:
            paid_count += 1
        else:
            pending_count += 1

        customers.append(obj)

    return render_template(
        "owner.html",
        customers=customers,
        monthly_fee=MONTHLY_FEE,
        pending_count=pending_count,
        paid_count=paid_count
    )


@app.route("/add_customer", methods=["POST"])
def add_customer():
    if not session.get("owner_logged_in"):
        return redirect("/")

    section = request.form.get("section")
    customer_id = request.form.get("customer_id")
    name = request.form.get("name")
    phone = request.form.get("phone")
    status = request.form.get("status")
    opening_paid = int(request.form.get("opening_paid", 0))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO customers (section, customer_id, name, phone, status, total_paid) VALUES (?, ?, ?, ?, ?, ?)",
        (section, customer_id, name, phone, status, opening_paid)
    )

    conn.commit()
    conn.close()

    return redirect("/owner")


@app.route("/update_payment", methods=["POST"])
def update_payment():
    if not session.get("owner_logged_in"):
        return redirect("/")

    section = request.form.get("section")
    customer_id = request.form.get("customer_id")
    amount = int(request.form.get("amount"))

    conn = get_db_connection()
    cur = conn.cursor()

    customer = cur.execute(
        "SELECT * FROM customers WHERE section=? AND customer_id=?",
        (section, customer_id)
    ).fetchone()

    if customer:
        new_total = customer["total_paid"] + amount

        cur.execute(
            "UPDATE customers SET total_paid=? WHERE section=? AND customer_id=?",
            (new_total, section, customer_id)
        )

        conn.commit()

    conn.close()
    return redirect("/owner")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- RUN ---------------- #

init_db()

if __name__ == "__main__":
    app.run(debug=True)
