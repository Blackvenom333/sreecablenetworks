from flask import Flask, request, redirect, session, render_template
import sqlite3
import pandas as pd

app = Flask(__name__)
app.secret_key = "tv_portal_secret_key_2026"

DB_NAME = "/tmp/tv.db"
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
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section TEXT,
        customer_id TEXT,
        name TEXT,
        phone TEXT,
        status TEXT,
        total_paid INTEGER,
        UNIQUE(section, customer_id)
    )
    """)

    # default login
    cur.execute("SELECT COUNT(*) FROM owner")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO owner (username, password) VALUES (?, ?)",
            ("owner", "admin123")
        )

    conn.commit()
    conn.close()


# ---------------- LOGIC ---------------- #

def calculate(total_paid):
    months = total_paid // MONTHLY_FEE
    rem = total_paid % MONTHLY_FEE

    if total_paid == 0:
        due = MONTHLY_FEE
    elif rem == 0:
        due = 0
    else:
        due = MONTHLY_FEE - rem

    return months, due


# ---------------- ROUTES ---------------- #

@app.route("/", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        c = request.form["captcha"]

        if c != "7":
            error = "Captcha wrong"
            return render_template("login.html", error=error)

        conn = get_db_connection()
        owner = conn.execute(
            "SELECT * FROM owner WHERE username=? AND password=?",
            (u, p)
        ).fetchone()
        conn.close()

        if not owner:
            error = "Invalid login"
            return render_template("login.html", error=error)

        session["login"] = True
        return redirect("/owner")

    return render_template("login.html", error=error)


@app.route("/owner")
def owner():
    if not session.get("login"):
        return redirect("/")

    conn = get_db_connection()
    data = conn.execute("SELECT * FROM customers ORDER BY section").fetchall()
    conn.close()

    customers = []
    pending = 0
    paid = 0

    for c in data:
        months, due = calculate(c["total_paid"])
        obj = dict(c)
        obj["months"] = months
        obj["due"] = due

        if due == 0 and c["total_paid"] > 0:
            paid += 1
        else:
            pending += 1

        customers.append(obj)

    return render_template(
        "owner.html",
        customers=customers,
        pending=pending,
        paid=paid,
        monthly_fee=MONTHLY_FEE
    )


@app.route("/add_customer", methods=["POST"])
def add_customer():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO customers VALUES (NULL,?,?,?,?,?,?)",
        (
            request.form["section"],
            request.form["customer_id"],
            request.form["name"],
            request.form["phone"],
            request.form["status"],
            int(request.form["opening_paid"])
        )
    )

    conn.commit()
    conn.close()
    return redirect("/owner")


@app.route("/update_payment", methods=["POST"])
def update_payment():
    conn = get_db_connection()
    cur = conn.cursor()

    c = cur.execute(
        "SELECT * FROM customers WHERE section=? AND customer_id=?",
        (request.form["section"], request.form["customer_id"])
    ).fetchone()

    if c:
        new_total = c["total_paid"] + int(request.form["amount"])

        cur.execute(
            "UPDATE customers SET total_paid=? WHERE section=? AND customer_id=?",
            (new_total, request.form["section"], request.form["customer_id"])
        )

        conn.commit()

    conn.close()
    return redirect("/owner")


# ---------------- EXCEL IMPORT ---------------- #

@app.route("/import_excel", methods=["POST"])
def import_excel():
    file = request.files["file"]

    if not file:
        return redirect("/owner")

    try:
        df = pd.read_excel(file, engine="openpyxl")
    except Exception as e:
        return f"Excel Error: {e}"

    conn = get_db_connection()
    cur = conn.cursor()

    for _, row in df.iterrows():
        try:
            cur.execute(
                "INSERT OR IGNORE INTO customers VALUES (NULL,?,?,?,?,?,?)",
                (
                    str(row.get("Section", "")).strip(),
                    str(row.get("Customer ID", "")).strip(),
                    str(row.get("Name", "")).strip(),
                    str(row.get("Phone", "")).strip(),
                    str(row.get("Status", "Active")).strip(),
                    int(row.get("Total Paid", 0))
                )
            )
        except:
            continue

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
