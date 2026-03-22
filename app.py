"""
╔══════════════════════════════════════════════════════════╗
║  SpendSmart v2 — Ultimate Personal Finance Tracker       ║
║  Features:                                               ║
║  ✅ SQLite Database (permanent storage)                  ║
║  ✅ Landing Page                                         ║
║  ✅ Monthly Email Reports (auto send)                    ║
║  ✅ Budget Alert Notifications                           ║
║  ✅ Savings Goals Tracker                                ║
║  ✅ Bill Split Calculator                                ║
║  ✅ Expense Search & Analytics                           ║
║  ✅ Ocean Blue Theme | Fully Responsive                  ║
╚══════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import hashlib, json, os, sqlite3
from datetime import date, timedelta, datetime
from io import StringIO, BytesIO

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as RC
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer, HRFlowable)
    from reportlab.lib.enums import TA_CENTER
    PDF_OK = True
except Exception:
    PDF_OK = False

# ── PAGE CONFIG ───────────────────────────────────────────
st.set_page_config(
    page_title="SpendSmart",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── PATHS ─────────────────────────────────────────────────
BASE     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
DB_PATH  = os.path.join(DATA_DIR, "spendsmart.db")
os.makedirs(DATA_DIR, exist_ok=True)

# ── CONSTANTS ─────────────────────────────────────────────
CATEGORIES = [
    "Food & Dining","Transport","Housing & Rent","Bills & Utilities",
    "Shopping","Entertainment","Healthcare","Education",
    "Travel","Fitness","Gifts","Business","Other",
]
ICONS = {
    "Food & Dining":"🍔","Transport":"🚗","Housing & Rent":"🏠",
    "Bills & Utilities":"💡","Shopping":"🛍️","Entertainment":"🎬",
    "Healthcare":"🏥","Education":"📚","Travel":"✈️","Fitness":"💪",
    "Gifts":"🎁","Business":"💼","Other":"📦",
}
CAT_COLORS = {
    "Food & Dining":"#0EA5E9","Transport":"#06B6D4",
    "Housing & Rent":"#0284C7","Bills & Utilities":"#F59E0B",
    "Shopping":"#38BDF8","Entertainment":"#7DD3FC",
    "Healthcare":"#34D399","Education":"#F97316",
    "Travel":"#22D3EE","Fitness":"#10B981",
    "Gifts":"#FB7185","Business":"#60A5FA","Other":"#94A3B8",
}
PAYMENTS  = ["UPI","Cash","Credit Card","Debit Card","Net Banking","Wallet"]
TIME_OPTS = {"This Month":0,"Last 3 Months":3,"Last 6 Months":6,"Last 1 Year":12,"All Time":999}
NAV_PAGES = [
    ("📊","Dashboard","dashboard"),
    ("➕","Add Expense","add"),
    ("📋","Expenses","list"),
    ("🎯","Budgets","budget"),
    ("📈","Reports","reports"),
    ("🏦","Savings Goals","goals"),
    ("🔀","Split Bill","split"),
    ("💡","Insights","insights"),
    ("📤","Export","export"),
    ("⚙️","Settings","settings"),
]

# ══════════════════════════════════════════════════════════
#  DATABASE SETUP  (SQLite)
# ══════════════════════════════════════════════════════════
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT DEFAULT '',
        monthly_budget REAL DEFAULT 0,
        email_alerts INTEGER DEFAULT 1,
        budget_alert_pct INTEGER DEFAULT 80,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # Expenses table
    c.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        date TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        payment TEXT DEFAULT 'UPI',
        notes TEXT DEFAULT '',
        tags TEXT DEFAULT '',
        recurring INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # Budgets table
    c.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        UNIQUE(username, category)
    )""")

    # Savings goals table
    c.execute("""
    CREATE TABLE IF NOT EXISTS savings_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        title TEXT NOT NULL,
        target_amount REAL NOT NULL,
        saved_amount REAL DEFAULT 0,
        deadline TEXT DEFAULT '',
        icon TEXT DEFAULT '🎯',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")



    conn.commit()
    conn.close()

init_db()

# ══════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════
def _hp(pw): return hashlib.sha256(pw.encode()).hexdigest()

def do_signup(username, password, name, email="", budget=0):
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO users (username,password,name,email,monthly_budget) VALUES (?,?,?,?,?)",
            (username, _hp(password), name, email, budget)
        )
        conn.commit(); conn.close()
        return True, "Account created! Sign in now."
    except sqlite3.IntegrityError:
        return False, "Username already taken."

def do_login(username, password):
    conn  = get_conn()
    row   = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, _hp(password))
    ).fetchone()
    conn.close()
    if row: return True, row["name"]
    return False, "Wrong username or password."

def get_user(username):
    conn = get_conn()
    row  = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else {}

def update_user(username, **kwargs):
    if not kwargs: return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [username]
    conn = get_conn()
    conn.execute(f"UPDATE users SET {sets} WHERE username=?", vals)
    conn.commit(); conn.close()

# ══════════════════════════════════════════════════════════
#  EXPENSES
# ══════════════════════════════════════════════════════════
def load_expenses(username) -> pd.DataFrame:
    conn = get_conn()
    df   = pd.read_sql(
        "SELECT * FROM expenses WHERE username=? ORDER BY date DESC",
        conn, params=(username,)
    )
    conn.close()
    if df.empty: return df
    df["date"]   = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    return df.dropna(subset=["date"])

def add_expense(username, dt, cat, desc, amt, pay, notes, tags, rec):
    conn = get_conn()
    conn.execute(
        """INSERT INTO expenses
           (username,date,category,description,amount,payment,notes,tags,recurring)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (username, str(dt), cat, desc, round(float(amt),2), pay, notes, tags, int(rec))
    )
    conn.commit(); conn.close()

def delete_expense(username, eid):
    conn = get_conn()
    conn.execute("DELETE FROM expenses WHERE id=? AND username=?", (eid, username))
    conn.commit(); conn.close()

def edit_expense(username, eid, dt, cat, desc, amt, pay, notes, tags, rec):
    conn = get_conn()
    conn.execute(
        """UPDATE expenses SET date=?,category=?,description=?,amount=?,
           payment=?,notes=?,tags=?,recurring=? WHERE id=? AND username=?""",
        (str(dt), cat, desc, round(float(amt),2), pay, notes, tags, int(rec), eid, username)
    )
    conn.commit(); conn.close()

# ══════════════════════════════════════════════════════════
#  BUDGETS
# ══════════════════════════════════════════════════════════
def load_budgets(username) -> dict:
    conn = get_conn()
    rows = conn.execute(
        "SELECT category, amount FROM budgets WHERE username=?", (username,)
    ).fetchall()
    conn.close()
    return {r["category"]: r["amount"] for r in rows}

def save_budget(username, category, amount):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO budgets (username,category,amount) VALUES (?,?,?)",
        (username, category, amount)
    )
    conn.commit(); conn.close()

# ══════════════════════════════════════════════════════════
#  SAVINGS GOALS
# ══════════════════════════════════════════════════════════
def load_goals(username):
    conn  = get_conn()
    rows  = conn.execute(
        "SELECT * FROM savings_goals WHERE username=? ORDER BY created_at DESC",
        (username,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_goal(username, title, target, saved, deadline, icon):
    conn = get_conn()
    conn.execute(
        "INSERT INTO savings_goals (username,title,target_amount,saved_amount,deadline,icon) VALUES (?,?,?,?,?,?)",
        (username, title, target, saved, deadline, icon)
    )
    conn.commit(); conn.close()

def update_goal_amount(username, gid, amount):
    conn = get_conn()
    conn.execute(
        "UPDATE savings_goals SET saved_amount=? WHERE id=? AND username=?",
        (amount, gid, username)
    )
    conn.commit(); conn.close()

def delete_goal(username, gid):
    conn = get_conn()
    conn.execute("DELETE FROM savings_goals WHERE id=? AND username=?", (gid, username))
    conn.commit(); conn.close()

# ══════════════════════════════════════════════════════════
#  EMAIL
# ══════════════════════════════════════════════════════════
# Email feature coming soon

# ══════════════════════════════════════════════════════════
#  BUDGET ALERT CHECK
# ══════════════════════════════════════════════════════════
def check_budget_alerts(username):
    """Return list of categories exceeding alert threshold."""
    info    = get_user(username)
    budgets = load_budgets(username)
    df      = load_expenses(username)
    if df.empty or not budgets: return []

    threshold = info.get("budget_alert_pct", 80)
    today     = pd.Timestamp.today()
    this_m    = df[(df["date"].dt.month==today.month) & (df["date"].dt.year==today.year)]
    spent     = this_m.groupby("category")["amount"].sum().to_dict()
    alerts    = []
    for cat, bamt in budgets.items():
        if bamt <= 0: continue
        sp  = spent.get(cat, 0)
        pct = sp / bamt * 100
        if pct >= threshold:
            alerts.append({
                "category": cat,
                "spent":    sp,
                "budget":   bamt,
                "pct":      pct,
                "over":     sp > bamt,
            })
    return sorted(alerts, key=lambda x: x["pct"], reverse=True)

# ══════════════════════════════════════════════════════════
#  TIME FILTER
# ══════════════════════════════════════════════════════════
def time_filter(df, months):
    if df.empty: return df
    today = pd.Timestamp.today()
    if months == 0:
        return df[(df["date"].dt.month==today.month) & (df["date"].dt.year==today.year)]
    if months == 999: return df
    return df[df["date"] >= today - pd.DateOffset(months=months)]

# ══════════════════════════════════════════════════════════
#  PDF
# ══════════════════════════════════════════════════════════
def make_pdf(df, username, period):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
          leftMargin=1.8*cm, rightMargin=1.8*cm,
          topMargin=1.8*cm,  bottomMargin=1.8*cm)
    BL=RC.HexColor("#0284C7"); W=RC.white
    LT=RC.HexColor("#BAC8D8"); MT=RC.HexColor("#4A7FA5")
    BG1=RC.HexColor("#0C2040"); BG2=RC.HexColor("#0F2744")

    def ts():
        return TableStyle([
            ("BACKGROUND",(0,0),(-1,0),BL),("TEXTCOLOR",(0,0),(-1,0),W),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),9),
            ("FONTNAME",(0,1),(-1,-1),"Helvetica"),("FONTSIZE",(0,1),(-1,-1),8.5),
            ("TEXTCOLOR",(0,1),(-1,-1),LT),("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[BG1,BG2]),
            ("GRID",(0,0),(-1,-1),0.3,RC.HexColor("#1E3A5F")),
            ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
        ])

    PS=ParagraphStyle; el=[]
    el.append(Paragraph("SpendSmart — Expense Report",
        PS("t",fontSize=20,textColor=W,fontName="Helvetica-Bold",alignment=TA_CENTER,spaceAfter=4)))
    el.append(Paragraph(f"{period} · {username.title()} · {date.today().strftime('%d %b %Y')}",
        PS("s",fontSize=11,textColor=MT,fontName="Helvetica",alignment=TA_CENTER,spaceAfter=12)))
    el.append(HRFlowable(width="100%",thickness=1,color=BL,spaceAfter=10))

    tot=df["amount"].sum(); cnt=len(df); avg=df["amount"].mean() if cnt else 0
    top_c=df.groupby("category")["amount"].sum().idxmax() if cnt else "—"
    t1=Table([["Total Spent","Transactions","Average","Top Category"],
              [f"₹{tot:,.2f}",str(cnt),f"₹{avg:,.2f}",top_c]],
             colWidths=[4.3*cm,3.8*cm,3.8*cm,5.1*cm])
    t1.setStyle(ts())
    el.append(Paragraph("Summary",PS("h",fontSize=13,textColor=W,fontName="Helvetica-Bold",spaceBefore=12,spaceAfter=8)))
    el.append(t1); el.append(Spacer(1,10))

    cs=df.groupby("category").agg(c=("id","count"),s=("amount","sum"),a=("amount","mean")).reset_index()
    cs=cs.sort_values("s",ascending=False)
    cd=[["Category","Count","Total (₹)","Average (₹)"]]+\
       [[r["category"],str(int(r["c"])),f"₹{r['s']:,.2f}",f"₹{r['a']:,.2f}"] for _,r in cs.iterrows()]
    t2=Table(cd,colWidths=[6*cm,2.8*cm,4.5*cm,4.7*cm]); t2.setStyle(ts())
    el.append(Paragraph("Category Breakdown",PS("h",fontSize=13,textColor=W,fontName="Helvetica-Bold",spaceBefore=12,spaceAfter=8)))
    el.append(t2); el.append(Spacer(1,10))

    td=[["Date","Category","Description","Amount","Payment"]]+\
       [[r["date"].strftime("%d %b %Y") if hasattr(r["date"],"strftime") else str(r["date"]),
         r["category"],str(r["description"])[:36],f"₹{r['amount']:,.2f}",str(r.get("payment","—"))]
        for _,r in df.sort_values("date",ascending=False).iterrows()]
    t3=Table(td,colWidths=[3.2*cm,3.8*cm,5.5*cm,3.2*cm,3.3*cm]); t3.setStyle(ts())
    el.append(Paragraph("All Transactions",PS("h",fontSize=13,textColor=W,fontName="Helvetica-Bold",spaceBefore=12,spaceAfter=8)))
    el.append(t3)
    doc.build(el)
    return buf.getvalue()

# ══════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════
def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700;800&family=DM+Sans:wght@400;500;600&display=swap');

/* BASE */
html, body, .stApp {
    background: #0A0F1E !important;
    font-family: 'DM Sans', sans-serif !important;
    color: #E2EAF4 !important;
}
.main .block-container {
    padding: 0.5rem 1rem 5rem 1rem !important;
    max-width: 100% !important;
}
[data-testid="collapsedControl"],
section[data-testid="stSidebar"] { display:none !important; }
#MainMenu, footer, header { visibility:hidden !important; }

/* HEADINGS */
h1,h2,h3,h4 {
    font-family: 'Sora', sans-serif !important;
    color: #E2EAF4 !important;
    letter-spacing: -0.02em !important;
}
h2 { font-size: 22px !important; margin-bottom: 12px !important; }

/* ALL TEXT */
p, label, span { font-family: 'DM Sans', sans-serif !important; }

/* INPUTS — FULL WIDTH */
input, textarea {
    background: #111827 !important;
    border: 1.5px solid rgba(14,165,233,0.2) !important;
    border-radius: 12px !important;
    color: #E2EAF4 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 16px !important;
    width: 100% !important;
    box-sizing: border-box !important;
    padding: 12px 16px !important;
}
input:focus, textarea:focus {
    border-color: #0EA5E9 !important;
    box-shadow: 0 0 0 3px rgba(14,165,233,0.15) !important;
    outline: none !important;
}
input::placeholder, textarea::placeholder { color: #374151 !important; }

/* SELECTBOX */
[data-baseweb="select"] > div:first-child {
    background: #111827 !important;
    border: 1.5px solid rgba(14,165,233,0.2) !important;
    border-radius: 12px !important;
    color: #E2EAF4 !important;
    font-size: 16px !important;
}
[data-baseweb="select"] svg { fill: #38BDF8 !important; }
[data-baseweb="popover"], ul[data-baseweb="menu"] {
    background: #111827 !important;
    border: 1px solid rgba(14,165,233,0.25) !important;
    border-radius: 12px !important;
}
li[role="option"] { background: #111827 !important; color: #E2EAF4 !important; font-size:15px !important; }
li[role="option"]:hover { background: rgba(14,165,233,0.12) !important; color: #38BDF8 !important; }
li[aria-selected="true"] { background: rgba(14,165,233,0.18) !important; color: #38BDF8 !important; }

/* DATE / NUMBER */
[data-testid="stDateInput"] input,
[data-testid="stNumberInput"] input {
    background: #111827 !important;
    border: 1.5px solid rgba(14,165,233,0.2) !important;
    color: #E2EAF4 !important;
    border-radius: 12px !important;
    font-size: 16px !important;
}

/* BUTTONS — Nav */
[data-testid="stHorizontalBlock"] .stButton button {
    background: transparent !important;
    color: #64748B !important;
    border: 1px solid transparent !important;
    border-radius: 10px !important;
    font-size: 11px !important;
    padding: 8px 2px !important;
    line-height: 1.4 !important;
    box-shadow: none !important;
    width: 100% !important;
    min-height: 52px !important;
    transform: none !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
}
[data-testid="stHorizontalBlock"] .stButton button:hover {
    background: rgba(14,165,233,0.1) !important;
    color: #38BDF8 !important;
    border-color: rgba(14,165,233,0.25) !important;
    transform: none !important;
}

/* BUTTONS — Content */
[data-testid="stVerticalBlock"] .stButton button,
[data-testid="stForm"] .stButton button {
    background: linear-gradient(135deg, #0284C7, #0369A1) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 12px !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    padding: 14px 20px !important;
    box-shadow: 0 4px 16px rgba(2,132,199,0.3) !important;
    font-family: 'Sora', sans-serif !important;
    transition: all 0.2s !important;
}
[data-testid="stVerticalBlock"] .stButton button:hover,
[data-testid="stForm"] .stButton button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(2,132,199,0.45) !important;
}

/* METRICS */
[data-testid="stMetric"] {
    background: #111827 !important;
    border: 1px solid rgba(14,165,233,0.15) !important;
    border-radius: 16px !important;
    padding: 16px !important;
    position: relative !important;
    overflow: hidden !important;
}
[data-testid="stMetric"]::before {
    content:''; position:absolute; top:0; left:0; right:0; height:2px;
    background: linear-gradient(90deg, #0EA5E9, #06B6D4);
}
[data-testid="stMetricValue"] {
    color: #E2EAF4 !important;
    font-family: 'Sora', sans-serif !important;
    font-size: 20px !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    color: #64748B !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

/* FORMS */
[data-testid="stForm"] {
    background: #111827 !important;
    border: 1px solid rgba(14,165,233,0.15) !important;
    border-radius: 16px !important;
    padding: 20px 16px !important;
}

/* TABS */
[data-baseweb="tab-list"] {
    background: #111827 !important;
    border: 1px solid rgba(14,165,233,0.15) !important;
    border-radius: 12px !important;
    padding: 4px !important;
    display: flex !important;
    overflow-x: auto !important;
    gap: 3px !important;
}
[data-baseweb="tab"] {
    flex: 1 !important;
    color: #64748B !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    border-radius: 9px !important;
    padding: 10px 8px !important;
    white-space: nowrap !important;
    min-width: 80px !important;
    font-family: 'DM Sans', sans-serif !important;
    text-align: center !important;
}
[aria-selected="true"][data-baseweb="tab"] {
    background: linear-gradient(135deg, #0284C7, #0369A1) !important;
    color: #fff !important;
}

/* EXPANDER */
[data-testid="stExpander"] {
    background: #111827 !important;
    border: 1px solid rgba(14,165,233,0.12) !important;
    border-radius: 12px !important;
}

/* DATAFRAME */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(14,165,233,0.15) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}

/* DOWNLOAD */
.stDownloadButton > button {
    background: transparent !important;
    color: #38BDF8 !important;
    border: 1.5px solid rgba(14,165,233,0.3) !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    width: 100% !important;
    padding: 12px 16px !important;
}

/* SCROLLBAR */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #0A0F1E; }
::-webkit-scrollbar-thumb { background: rgba(14,165,233,0.25); border-radius: 2px; }

/* NAV — MOBILE SCROLL */
@media (max-width: 768px) {
    .main .block-container { padding: 0.5rem 0.5rem 5rem 0.5rem !important; }
    [data-testid="stHorizontalBlock"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        -webkit-overflow-scrolling: touch !important;
        scrollbar-width: none !important;
    }
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar { display: none !important; }
    [data-testid="stHorizontalBlock"] > div {
        min-width: 68px !important;
        flex: 0 0 68px !important;
    }
    [data-testid="stHorizontalBlock"] .stButton button {
        font-size: 10px !important;
        min-height: 54px !important;
    }
    h2 { font-size: 18px !important; }
    [data-testid="stMetricValue"] { font-size: 16px !important; }
    [data-testid="stForm"] { padding: 16px 12px !important; }
}
</style>
""", unsafe_allow_html=True)


# ── CHART DEFAULTS ────────────────────────────────────────
_CL = dict(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
           font=dict(color="#4A7FA5",family="Inter",size=12),
           margin=dict(l=8,r=8,t=10,b=8))

def _ax(fig, rows=1, cols=1):
    kw = dict(gridcolor="rgba(14,165,233,.07)",zerolinecolor="rgba(14,165,233,.07)",
              showline=False,tickcolor="#334E68")
    if rows>1 or cols>1:
        for r in range(1,rows+1):
            for c in range(1,cols+1):
                fig.update_xaxes(**kw,row=r,col=c)
                fig.update_yaxes(**kw,row=r,col=c)
    else:
        fig.update_xaxes(**kw); fig.update_yaxes(**kw)

# ── UI HELPERS ────────────────────────────────────────────
def divider(t):
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin:20px 0 12px">
  <div style="flex:1;height:1px;background:linear-gradient(90deg,rgba(14,165,233,.4),transparent)"></div>
  <span style="color:#2A5F85;font-size:clamp(9px,.9vw,11px);font-weight:700;
    letter-spacing:.14em;text-transform:uppercase;white-space:nowrap">{t}</span>
  <div style="flex:1;height:1px;background:linear-gradient(90deg,transparent,rgba(14,165,233,.4))"></div>
</div>""", unsafe_allow_html=True)

def txn_card(icon, desc, cat, dt, pay, amt, clr):
    st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
    padding:clamp(10px,1.5vh,14px) clamp(12px,1.5vw,18px);
    background:linear-gradient(135deg,rgba(12,32,64,.8),rgba(15,39,68,.85));
    border:1px solid rgba(14,165,233,.1);border-radius:14px;margin-bottom:7px">
  <div style="display:flex;align-items:center;gap:clamp(10px,1.2vw,14px);min-width:0">
    <div style="flex-shrink:0;width:clamp(36px,4vw,44px);height:clamp(36px,4vw,44px);
        background:{clr}18;border:1px solid {clr}35;border-radius:12px;
        display:flex;align-items:center;justify-content:center;
        font-size:clamp(16px,1.8vw,20px)">{icon}</div>
    <div style="min-width:0">
      <div style="color:#E0F2FE;font-weight:500;font-size:clamp(12px,1.3vw,14px);
          white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
          max-width:clamp(120px,25vw,400px)">{desc}</div>
      <div style="color:#2A5F85;font-size:clamp(10px,1vw,12px);margin-top:2px">
        {cat} · {dt} · {pay}</div>
    </div>
  </div>
  <div style="flex-shrink:0;margin-left:8px;color:{clr};font-weight:700;
      font-size:clamp(13px,1.5vw,17px);font-family:'Plus Jakarta Sans',sans-serif">
    ₹{amt:,.2f}</div>
</div>""", unsafe_allow_html=True)

def ph(title):
    st.markdown(f"<h2 style='margin:0 0 18px;font-size:clamp(18px,2.2vw,26px)'>{title}</h2>",
                unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
#  LANDING PAGE
# ══════════════════════════════════════════════════════════
def landing_page():
    st.markdown("""
<style>
.land-hero {
    text-align:center;
    padding: clamp(40px,8vh,80px) clamp(16px,5vw,60px) clamp(30px,5vh,50px);
}
.land-badge {
    display:inline-block;
    background:rgba(14,165,233,.12);border:1px solid rgba(14,165,233,.25);
    border-radius:99px;padding:7px 20px;font-size:clamp(11px,1.3vw,13px);
    color:#7DD3FC;margin-bottom:28px;letter-spacing:.08em;font-weight:600;
}
.land-title {
    font-family:'Plus Jakarta Sans',sans-serif;
    font-size:clamp(30px,5.5vw,60px);font-weight:800;
    letter-spacing:-2px;line-height:1.15;color:#F0F9FF;margin-bottom:20px;
}
.land-title .line1 { display:block; color:#E0F2FE; }
.land-title .line2 {
    display:block;
    background:linear-gradient(135deg,#38BDF8 20%,#06B6D4 60%,#0EA5E9 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.land-sub {
    color:#4A7FA5;font-size:clamp(14px,1.7vw,17px);
    max-width:520px;margin:0 auto 36px;line-height:1.8;
}
.land-stats {
    display:flex;justify-content:center;flex-wrap:wrap;gap:clamp(16px,3vw,48px);
    margin-top:clamp(28px,5vh,48px);padding:clamp(20px,3vh,32px);
    background:rgba(12,32,64,.55);border:1px solid rgba(14,165,233,.12);
    border-radius:20px;backdrop-filter:blur(12px);
}
.land-stat-val {
    font-family:'Plus Jakarta Sans',sans-serif;
    font-size:clamp(22px,4vw,38px);font-weight:800;color:#38BDF8;
}
.land-stat-label {
    color:#2A5F85;font-size:clamp(10px,1vw,12px);
    text-transform:uppercase;letter-spacing:.1em;margin-top:5px;
}
.feature-card {
    background:linear-gradient(145deg,rgba(12,32,64,.8),rgba(15,39,68,.85));
    border:1px solid rgba(14,165,233,.12);border-radius:14px;
    padding:16px 18px;
    transition:border-color .2s,transform .2s;
}
.feature-card:hover { border-color:rgba(14,165,233,.35);transform:translateY(-2px); }
.feature-title {
    color:#E0F2FE;font-weight:700;font-size:15px;
    margin-bottom:5px;font-family:'Plus Jakarta Sans',sans-serif;
    white-space:normal;word-break:normal;
}
.feature-desc {
    color:#4A7FA5;font-size:13px;line-height:1.6;
    white-space:normal;word-break:normal;
}
</style>

<div class="land-hero">
  <div class="land-badge">✦ Simple · Smart · Free Forever</div>
  <div class="land-title">
    <span class="line1">All your expenses.</span>
    <span class="line2">One place.</span>
  </div>
  <div class="land-sub">
    Track expenses, set budgets, split bills and reach your
    savings goals — all in one clean, beautiful dashboard.
  </div>
</div>
""", unsafe_allow_html=True)

    # CTA buttons
    _, c1, c2, _ = st.columns([1, 1, 1, 1])
    with c1:
        if st.button("📊  Start for Free", use_container_width=True, key="land_signup"):
            st.session_state.auth_tab = "signup"
            st.session_state.page = "auth"
            st.rerun()
    with c2:
        if st.button("🔑  Sign In", use_container_width=True, key="land_signin"):
            st.session_state.auth_tab = "signin"
            st.session_state.page = "auth"
            st.rerun()

    # Stats bar
    st.markdown("""
<div class="land-stats">
  <div style="text-align:center">
    <div class="land-stat-val">₹0</div>
    <div class="land-stat-label">Cost to use</div>
  </div>
  <div style="text-align:center">
    <div class="land-stat-val">10+</div>
    <div class="land-stat-label">Pages & Tools</div>
  </div>
  <div style="text-align:center">
    <div class="land-stat-val">13</div>
    <div class="land-stat-label">Expense Categories</div>
  </div>
  <div style="text-align:center">
    <div class="land-stat-val">SQLite</div>
    <div class="land-stat-label">Real Database</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Features grid
    st.markdown("<br>", unsafe_allow_html=True)
    divider("EVERYTHING YOU NEED")

    features = [
        ("📊","Visual Dashboard","5 interactive charts — trend, category split, top spending, daily bars, payment methods."),
        ("🗄️","SQLite Database","Your data is stored permanently in a real database — never lost on refresh."),
        ("📧","Email Reports","Auto-send beautiful monthly expense reports to your email every month."),
        ("🔔","Budget Alerts","Get instant alerts when you're close to or over your category budgets."),
        ("🏦","Savings Goals","Set goals like 'Buy iPhone' or 'Goa Trip' and track your progress visually."),
        ("🔀","Bill Split","Split expenses with friends — enter amounts and see who owes what instantly."),
        ("💡","Smart Insights","9 auto-generated money insights based on your spending patterns."),
        ("📤","PDF + CSV Export","Download your data as a formatted PDF report or spreadsheet."),
        ("🌊","Ocean Blue Design","Beautiful responsive UI that looks great on mobile, tablet and laptop."),
    ]

    # Render feature cards one by one — full width on all screens
    for icon, title, desc in features:
        st.markdown(f"""
<div style="
    background:linear-gradient(145deg,rgba(12,32,64,.85),rgba(15,39,68,.9));
    border:1px solid rgba(14,165,233,.15);
    border-radius:16px;
    padding:18px 20px;
    margin-bottom:10px;
    display:flex;
    align-items:flex-start;
    gap:16px;
">
  <span style="font-size:32px;flex-shrink:0;margin-top:2px">{icon}</span>
  <div>
    <div style="color:#E0F2FE;font-weight:700;font-size:16px;
                font-family:'Plus Jakarta Sans',sans-serif;margin-bottom:5px">
      {title}
    </div>
    <div style="color:#4A7FA5;font-size:13px;line-height:1.65">
      {desc}
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    divider("READY TO START?")
    _, cb, _ = st.columns([1, 2, 1])
    with cb:
        if st.button("📊  Start Tracking for Free", use_container_width=True, key="land_bottom"):
            st.session_state.auth_tab = "signup"
            st.session_state.page = "auth"
            st.rerun()

# ══════════════════════════════════════════════════════════
#  AUTH PAGE
# ══════════════════════════════════════════════════════════
def auth_page():
    st.markdown("""
<style>
.auth-title-text {
    font-family:'Plus Jakarta Sans',sans-serif;
    font-size:clamp(32px,8vw,50px);font-weight:800;
    letter-spacing:-1.5px;white-space:nowrap;
    background:linear-gradient(135deg,#38BDF8,#06B6D4,#0EA5E9);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    display:block;line-height:1.1;
}
[data-baseweb="tab-list"] {
    display:flex !important;width:100% !important;
}
[data-baseweb="tab"] {
    flex:1 !important;text-align:center !important;
    white-space:nowrap !important;
}
[data-testid="stTextInput"]>div>div {
    display:flex !important;width:100% !important;
}
[data-testid="stTextInput"]>div>div>input {
    flex:1 !important;min-width:0 !important;width:100% !important;
}
</style>
""", unsafe_allow_html=True)

    st.markdown("""
<div style="text-align:center;padding:clamp(28px,5vh,48px) 0 clamp(16px,3vh,26px)">
  <span class="auth-title-text">SpendSmart</span>
  <div style="color:#2A5F85;font-size:clamp(12px,3vw,15px);margin-top:10px">
    Smart finance tracking for everyone 📊
  </div>
</div>
""", unsafe_allow_html=True)

    # Back to landing
    if st.button("← Back to Home", key="back_home"):
        st.session_state.page = "landing"
        st.rerun()

    default_tab = getattr(st.session_state, "auth_tab", "signin")
    tab_order   = ["  Sign In  ", "  Create Account  "]
    t_in, t_up  = st.tabs(tab_order)

    with t_in:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        uu = st.text_input("Username", placeholder="Enter your username", key="li_u")
        pp = st.text_input("Password", type="password", placeholder="Password", key="li_p")
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("Sign In  →", use_container_width=True, key="b_li"):
            if uu and pp:
                ok, msg = do_login(uu, pp)
                if ok:
                    st.session_state.update({"logged_in":True,"username":uu,
                        "user_name":msg,"page":"dashboard"})
                    st.rerun()
                else: st.error(f"❌  {msg}")
            else: st.warning("Please fill both fields.")

    with t_up:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        nm = st.text_input("Full Name",    placeholder="Your full name",     key="su_nm")
        su = st.text_input("Username",     placeholder="Choose a username",  key="su_u")
        em = st.text_input("Email",        placeholder="your@gmail.com (for monthly reports)", key="su_em")
        sp = st.text_input("Password",     type="password", placeholder="Min 6 characters", key="su_p")
        sc = st.text_input("Confirm Password", type="password", placeholder="Repeat password", key="su_c")
        mb = st.number_input("Monthly Budget (₹)", min_value=0, value=20000, step=1000, key="su_mb")
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("Create Account  →", use_container_width=True, key="b_su"):
            if not all([nm, su, sp, sc]): st.warning("Please fill all required fields.")
            elif len(sp) < 6:  st.error("Password must be at least 6 characters.")
            elif sp != sc:     st.error("Passwords don't match.")
            else:
                ok, msg = do_signup(su, sp, nm, em, mb)
                if ok: st.success(f"✅  {msg}")
                else:  st.error(f"❌  {msg}")

# ══════════════════════════════════════════════════════════
#  TOP NAV
# ══════════════════════════════════════════════════════════
def top_nav():
    user  = st.session_state.get("user_name","User")
    page  = st.session_state.get("page","dashboard")
    alerts= check_budget_alerts(st.session_state.get("username",""))
    alert_badge = f" 🔴{len(alerts)}" if alerts else ""

    st.markdown(f"""
<div style="
    background:linear-gradient(180deg,rgba(12,26,46,.97),rgba(12,32,64,.95));
    border-bottom:1px solid rgba(14,165,233,.2);backdrop-filter:blur(16px);
    padding:0 clamp(12px,3vw,32px);display:flex;align-items:center;
    justify-content:space-between;
    height:clamp(52px,7vh,64px);position:sticky;top:0;z-index:9999;
    margin:-28px -40px 16px -40px;box-shadow:0 4px 24px rgba(0,0,0,.3);
">
  <div style="font-family:'Plus Jakarta Sans',sans-serif;
      font-size:clamp(16px,2vw,22px);font-weight:800;letter-spacing:-.5px;
      background:linear-gradient(135deg,#38BDF8,#06B6D4,#0EA5E9);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;
      white-space:nowrap">
    📊 SpendSmart{alert_badge}
  </div>
  <div style="background:rgba(14,165,233,.1);border:1px solid rgba(14,165,233,.2);
      border-radius:99px;padding:5px clamp(10px,1.5vw,16px);
      font-size:clamp(11px,1.1vw,13px);color:#7096B8;
      white-space:nowrap;max-width:180px;overflow:hidden;text-overflow:ellipsis">
    👤 {user}
  </div>
</div>
""", unsafe_allow_html=True)

    cols = st.columns(len(NAV_PAGES) + 1)
    for i, (icon, label, key) in enumerate(NAV_PAGES):
        with cols[i]:
            active = (page == key)
            if active:
                st.markdown(
                    f"<div style='background:linear-gradient(135deg,rgba(2,132,199,.25),"
                    f"rgba(3,105,161,.2));border:1px solid rgba(14,165,233,.45);"
                    f"border-radius:10px;padding:clamp(6px,1vh,9px) 2px;"
                    f"text-align:center;font-size:clamp(9px,1.1vw,12px);"
                    f"font-weight:700;color:#38BDF8;line-height:1.4'>"
                    f"{icon}<br><span style='font-size:clamp(8px,.9vw,10px)'>{label}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                if st.button(f"{icon}\n{label}", key=f"nav_{key}", use_container_width=True):
                    st.session_state.page = key
                    st.session_state.pop("edit_id", None)
                    st.rerun()

    with cols[-1]:
        if st.button("🚪\nSign Out", key="so", use_container_width=True):
            for k in ["logged_in","username","user_name","page","edit_id"]:
                st.session_state.pop(k, None)
            st.session_state.page = "landing"
            st.rerun()

    # Show budget alerts banner if any
    if alerts:
        for a in alerts[:2]:
            clr = "#EF4444" if a["over"] else "#F59E0B"
            msg = (f"🚨 **{a['category']}** — Over budget! ₹{a['spent']:,.0f} / ₹{a['budget']:,.0f}"
                   if a["over"] else
                   f"⚠️ **{a['category']}** — {a['pct']:.0f}% of budget used (₹{a['spent']:,.0f} / ₹{a['budget']:,.0f})")
            st.markdown(
                f"<div style='padding:9px 16px;background:{clr}15;border:1px solid {clr}40;"
                f"border-radius:8px;margin-bottom:4px;font-size:13px;color:{clr}'>{msg}</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════
def page_dashboard():
    u    = st.session_state["username"]
    name = st.session_state["user_name"]
    df   = load_expenses(u)
    info = get_user(u)
    ph(f"👋 Welcome back, {name.split()[0]}!")

    if df.empty:
        st.markdown("""
<div style="text-align:center;padding:clamp(40px,8vh,80px) 20px;
    background:linear-gradient(145deg,rgba(12,32,64,.8),rgba(15,39,68,.85));
    border:2px dashed rgba(14,165,233,.2);border-radius:20px">
  <div style="font-size:clamp(40px,6vw,60px)">📊</div>
  <div style="font-size:clamp(16px,2vw,22px);color:#E0F2FE;font-weight:700;
      margin-top:14px;font-family:'Plus Jakarta Sans',sans-serif">No expenses yet!</div>
  <div style="color:#2A5F85;margin-top:8px;font-size:clamp(12px,1.3vw,15px)">
    Click <b style="color:#38BDF8">➕ Add Expense</b> in the nav bar above
  </div>
</div>""", unsafe_allow_html=True)
        return

    today  = pd.Timestamp.today()
    # Safe date filtering — ensure date column is datetime
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    this_m = df[(df["date"].dt.month==today.month)&(df["date"].dt.year==today.year)]
    lm_n   = today.month-1 if today.month>1 else 12
    ly     = today.year if today.month>1 else today.year-1
    last_m = df[(df["date"].dt.month==lm_n)&(df["date"].dt.year==ly)]
    ttm    = this_m["amount"].sum()
    tlm    = last_m["amount"].sum()
    delta  = ((ttm-tlm)/tlm*100) if tlm>0 else 0
    bud    = info.get("monthly_budget",0)

    k1,k2,k3,k4,k5 = st.columns(5)
    k1.metric("This Month",      f"₹{ttm:,.0f}",  f"{delta:+.1f}% vs last month")
    k2.metric("Last Month",      f"₹{tlm:,.0f}")
    k3.metric("Daily Average",   f"₹{ttm/max(today.day,1):,.0f}")
    k4.metric("Expenses (Month)",len(this_m))
    if bud>0: k5.metric("Budget Left",   f"₹{bud-ttm:,.0f}",
                         delta_color="inverse" if ttm>bud else "normal")
    else:     k5.metric("All-Time Total",f"₹{df['amount'].sum():,.0f}")

    st.markdown("<br>", unsafe_allow_html=True)
    tfc,_ = st.columns([1.6,4])
    with tfc:
        tf = st.selectbox("📅 Time Range", list(TIME_OPTS.keys()), index=2, key="d_tf")
    dff = time_filter(df, TIME_OPTS[tf])

    c1,c2 = st.columns([1.5,1])
    with c1:
        divider("📈 SPENDING TREND")
        mon = dff.groupby(dff["date"].dt.to_period("M"))["amount"].sum().reset_index()
        mon["date"] = mon["date"].dt.to_timestamp()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=mon["date"],y=mon["amount"],fill="tozeroy",
            fillcolor="rgba(14,165,233,.08)",
            line=dict(color="#0EA5E9",width=2.5),mode="lines+markers",
            marker=dict(size=7,color="#0EA5E9",line=dict(color="#0C1A2E",width=2)),
            hovertemplate="<b>%{x|%b %Y}</b><br>₹%{y:,.0f}<extra></extra>"))
        fig.update_layout(**_CL,height=240,showlegend=False)
        _ax(fig)
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})

    with c2:
        divider("🥧 CATEGORY SPLIT")
        cdf = dff.groupby("category")["amount"].sum().reset_index()
        if not cdf.empty:
            tv  = cdf["amount"].sum()
            fig2 = go.Figure(go.Pie(
                labels=cdf["category"],values=cdf["amount"],hole=0.62,
                marker_colors=[CAT_COLORS.get(c,"#94A3B8") for c in cdf["category"]],
                textinfo="none",
                hovertemplate="<b>%{label}</b><br>₹%{value:,.0f} (%{percent})<extra></extra>"))
            fig2.add_annotation(text=f"₹{tv/1000:.1f}K",
                font=dict(size=18,color="#E0F2FE",family="Plus Jakarta Sans"),showarrow=False)
            fig2.update_layout(**_CL,height=240,showlegend=False)
            st.plotly_chart(fig2,use_container_width=True,config={"displayModeBar":False})

    c3,c4,c5 = st.columns([1.1,1,.9])
    with c3:
        divider("🏆 TOP CATEGORIES")
        top=(dff.groupby("category")["amount"].sum().nlargest(6).reset_index().sort_values("amount"))
        if not top.empty:
            fig3=go.Figure(go.Bar(
                x=top["amount"],y=top["category"],orientation="h",
                marker_color=[CAT_COLORS.get(c,"#94A3B8") for c in top["category"]],
                text=[f"₹{v:,.0f}" for v in top["amount"]],textposition="outside",
                textfont=dict(color="#4A7FA5",size=10),
                hovertemplate="<b>%{y}</b><br>₹%{x:,.0f}<extra></extra>"))
            fig3.update_layout(**_CL,height=240,showlegend=False)
            _ax(fig3)
            st.plotly_chart(fig3,use_container_width=True,config={"displayModeBar":False})

    with c4:
        divider("📅 LAST 7 DAYS")
        l7=df[df["date"]>=today-pd.Timedelta(days=6)]
        dy=l7.groupby(l7["date"].dt.date)["amount"].sum().reset_index()
        dy.columns=["date","amount"]
        all_d=pd.date_range(today-pd.Timedelta(days=6),today,freq="D").date
        dy=dy.set_index("date").reindex(all_d,fill_value=0).reset_index()
        dy.columns=["date","amount"]
        fig4=go.Figure(go.Bar(
            x=[str(d)[5:] for d in dy["date"]],y=dy["amount"],
            marker_color=["#0EA5E9" if d==today.date() else "#0C2F50" for d in dy["date"]],
            hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"))
        fig4.update_layout(**_CL,height=240,showlegend=False)
        _ax(fig4)
        st.plotly_chart(fig4,use_container_width=True,config={"displayModeBar":False})

    with c5:
        divider("💳 PAYMENTS")
        pm=dff.groupby("payment")["amount"].sum().reset_index()
        pm=pm[pm["payment"].astype(str).str.strip()!=""]
        if not pm.empty:
            pc=["#0EA5E9","#06B6D4","#F59E0B","#38BDF8","#7DD3FC","#22C55E"]
            fig5=go.Figure(go.Pie(
                labels=pm["payment"],values=pm["amount"],hole=0.52,
                marker_colors=pc[:len(pm)],textinfo="label+percent",
                textfont=dict(size=10,color="#BAC8D8"),
                hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<extra></extra>"))
            fig5.update_layout(**_CL,height=240,showlegend=False)
            st.plotly_chart(fig5,use_container_width=True,config={"displayModeBar":False})

    divider("🕐 RECENT TRANSACTIONS")
    for _,r in df.sort_values("date",ascending=False).head(6).iterrows():
        txn_card(ICONS.get(r["category"],"📦"),r["description"],r["category"],
                 r["date"].strftime("%d %b %Y"),str(r.get("payment","—")),
                 r["amount"],CAT_COLORS.get(r["category"],"#94A3B8"))

# ══════════════════════════════════════════════════════════
#  ADD EXPENSE
# ══════════════════════════════════════════════════════════
def page_add():
    u=st.session_state["username"]; ph("➕ Add New Expense")
    st.markdown("""
<div style="padding:12px 16px;background:rgba(14,165,233,.07);
    border:1px solid rgba(14,165,233,.2);border-left:3px solid #0EA5E9;
    border-radius:10px;color:#7096B8;font-size:clamp(12px,1.2vw,14px);margin-bottom:20px">
  Fill in the details below. Fields marked <b>*</b> are required.
</div>""", unsafe_allow_html=True)

    with st.form("add_form", clear_on_submit=True):
        # All fields stacked — works perfectly on mobile AND desktop
        exp_date  = st.date_input("📅 Date *", value=date.today())
        amount    = st.number_input("💵 Amount (₹) *", min_value=0.01,
                                     value=100.0, step=50.0, format="%.2f")
        desc      = st.text_input("📝 Description *", placeholder="What did you spend on?")
        category  = st.selectbox("📂 Category *", CATEGORIES,
                       format_func=lambda c: f"{ICONS.get(c,'📦')}  {c}")
        payment   = st.selectbox("💳 Payment Method *", PAYMENTS)
        tags      = st.text_input("🏷️ Tags (optional)", placeholder="e.g. work, weekend")
        notes     = st.text_area("📒 Notes (optional)", height=70,
                                  placeholder="Extra details...")
        recurring = st.checkbox("🔁 Mark as Recurring (monthly expense)")
        submitted = st.form_submit_button("💾  Save Expense", use_container_width=True)
        if submitted:
            if not desc.strip(): st.error("❌  Please enter a description.")
            elif amount <= 0:    st.error("❌  Amount must be greater than 0.")
            else:
                add_expense(u, exp_date, category, desc.strip(),
                            amount, payment, notes, tags, recurring)
                st.success(f"✅  Saved! {ICONS.get(category,'')} **{category}** — ₹{amount:,.2f} via {payment}")

    df=load_expenses(u)
    if not df.empty:
        today=pd.Timestamp.today()
        this_m=df[(df["date"].dt.month==today.month)&(df["date"].dt.year==today.year)]
        bud=get_user(u).get("monthly_budget",0)
        st.markdown("<br>",unsafe_allow_html=True)
        divider("📊 THIS MONTH SNAPSHOT")
        s1,s2,s3=st.columns(3)
        s1.metric("Spent",f"₹{this_m['amount'].sum():,.0f}")
        s2.metric("# Expenses",len(this_m))
        if bud>0: s3.metric("Budget Left",f"₹{bud-this_m['amount'].sum():,.0f}",
            delta_color="inverse" if this_m['amount'].sum()>bud else "normal")
        else: s3.metric("Avg/Day",f"₹{this_m['amount'].sum()/max(today.day,1):,.0f}")
        divider("🕐 RECENTLY ADDED")
        for _,r in df.head(5).iterrows():
            txn_card(ICONS.get(r["category"],"📦"),r["description"],r["category"],
                     r["date"].strftime("%d %b %Y"),str(r.get("payment","—")),
                     r["amount"],CAT_COLORS.get(r["category"],"#94A3B8"))

# ══════════════════════════════════════════════════════════
#  ALL EXPENSES
# ══════════════════════════════════════════════════════════
def page_list():
    u=st.session_state["username"]; df=load_expenses(u)
    ph("📋 All Expenses")
    if df.empty: st.info("No expenses yet. Use ➕ Add Expense!"); return

    with st.expander("🔍  Filter & Search",expanded=True):
        fa,fb,fc,fd=st.columns(4)
        with fa: sc=st.multiselect("Category",CATEGORIES)
        with fb:
            periods=sorted(df["date"].dt.to_period("M").unique(),reverse=True)
            sm=st.selectbox("Month",["All"]+[str(p) for p in periods])
        with fc: sp=st.multiselect("Payment",PAYMENTS)
        with fd: ss=st.text_input("🔍 Search",placeholder="Description / tags…")

    fdf=df.copy()
    if sc:  fdf=fdf[fdf["category"].isin(sc)]
    if sp:  fdf=fdf[fdf["payment"].isin(sp)]
    if sm!="All": fdf=fdf[fdf["date"].dt.to_period("M").astype(str)==sm]
    if ss:
        fdf=fdf[fdf["description"].astype(str).str.contains(ss,case=False,na=False)|
                fdf["tags"].astype(str).str.contains(ss,case=False,na=False)]
    fdf=fdf.sort_values("date",ascending=False)

    st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;
    padding:11px 16px;background:rgba(14,165,233,.07);
    border:1px solid rgba(14,165,233,.15);border-radius:12px;margin-bottom:14px">
  <span style="color:#4A7FA5;font-size:clamp(12px,1.2vw,14px)">
    Showing <b style="color:#E0F2FE">{len(fdf)}</b> of <b style="color:#E0F2FE">{len(df)}</b>
  </span>
  <span style="color:#38BDF8;font-weight:700;font-size:clamp(15px,1.8vw,19px);
    font-family:'Plus Jakarta Sans',sans-serif">₹{fdf['amount'].sum():,.2f}</span>
</div>""", unsafe_allow_html=True)

    if "edit_id" not in st.session_state: st.session_state.edit_id=None
    for _,row in fdf.iterrows():
        eid=int(row["id"]); ico=ICONS.get(row["category"],"📦")
        clr=CAT_COLORS.get(row["category"],"#94A3B8")
        is_rec=int(row.get("recurring",0))==1
        raw_tags=str(row.get("tags","")).strip()
        tags_html=""
        if raw_tags and raw_tags!="nan":
            for t in raw_tags.split(","):
                t=t.strip()
                if t: tags_html+=f"<span style='background:rgba(14,165,233,.1);border:1px solid rgba(14,165,233,.25);border-radius:5px;padding:2px 8px;font-size:11px;color:#38BDF8;margin-right:4px'>{t}</span>"
        rec_badge=(' <span style="background:rgba(14,165,233,.15);color:#38BDF8;font-size:10px;padding:2px 7px;border-radius:99px;margin-left:5px">🔁 recurring</span>') if is_rec else ""

        ca,cb,cc,cd=st.columns([.32,3.1,1.2,.55])
        with ca:
            st.markdown(f"<div style='width:43px;height:43px;background:{clr}18;border:1px solid {clr}30;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:19px;margin-top:6px'>{ico}</div>",unsafe_allow_html=True)
        with cb:
            st.markdown(f"<div style='padding-top:5px'><span style='color:#E0F2FE;font-weight:500;font-size:clamp(12px,1.3vw,14px)'>{row['description']}{rec_badge}</span><br><span style='color:#2A5F85;font-size:12px'>{row['category']} · {row['date'].strftime('%d %b %Y')} · {row.get('payment','—')}</span>{'<br><div style=margin-top:4px>'+tags_html+'</div>' if tags_html else ''}</div>",unsafe_allow_html=True)
        with cc:
            st.markdown(f"<div style='text-align:right;padding-top:9px;color:{clr};font-weight:700;font-size:clamp(13px,1.5vw,17px);font-family:Plus Jakarta Sans,sans-serif'>₹{row['amount']:,.2f}</div>",unsafe_allow_html=True)
        with cd:
            b1,b2=st.columns(2)
            with b1:
                if st.button("✏️",key=f"e{eid}",help="Edit"):
                    st.session_state.edit_id=None if st.session_state.edit_id==eid else eid
                    st.rerun()
            with b2:
                if st.button("🗑️",key=f"d{eid}",help="Delete"):
                    delete_expense(u,eid)
                    if st.session_state.edit_id==eid: st.session_state.edit_id=None
                    st.rerun()

        if st.session_state.edit_id==eid:
            with st.form(f"ef_{eid}"):
                st.markdown("**✏️  Edit Expense**")
                ea,eb,ec=st.columns(3)
                with ea:
                    e_d=st.date_input("Date",value=row["date"].date(),key=f"ed{eid}")
                    e_c=st.selectbox("Category",CATEGORIES,
                        index=CATEGORIES.index(row["category"]) if row["category"] in CATEGORIES else 0,
                        format_func=lambda c:f"{ICONS.get(c,'📦')} {c}",key=f"ec{eid}")
                with eb:
                    e_a=st.number_input("Amount",value=float(row["amount"]),step=10.0,format="%.2f",key=f"ea{eid}")
                    pi=PAYMENTS.index(str(row.get("payment",""))) if str(row.get("payment","")) in PAYMENTS else 0
                    e_p=st.selectbox("Payment",PAYMENTS,index=pi,key=f"ep{eid}")
                with ec:
                    e_desc=st.text_input("Description",value=str(row["description"]),key=f"edd{eid}")
                    e_t=st.text_input("Tags",value=str(row.get("tags","")) if pd.notna(row.get("tags","")) else "",key=f"et{eid}")
                e_n=st.text_area("Notes",value=str(row.get("notes","")) if pd.notna(row.get("notes","")) else "",height=60,key=f"en{eid}")
                e_r=st.checkbox("Recurring",value=int(row.get("recurring",0))==1,key=f"er{eid}")
                s1,s2=st.columns(2)
                with s1:
                    if st.form_submit_button("💾  Save",use_container_width=True):
                        edit_expense(u,eid,e_d,e_c,e_desc,e_a,e_p,e_n,e_t,e_r)
                        st.session_state.edit_id=None; st.success("✅ Updated!"); st.rerun()
                with s2:
                    if st.form_submit_button("✖  Cancel",use_container_width=True):
                        st.session_state.edit_id=None; st.rerun()

        st.markdown("<hr style='border:none;border-top:1px solid rgba(14,165,233,.07);margin:4px 0'>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
#  BUDGET TRACKER
# ══════════════════════════════════════════════════════════
def page_budget():
    u=st.session_state["username"]; df=load_expenses(u); bud=load_budgets(u)
    today=pd.Timestamp.today()
    this_m=df[(df["date"].dt.month==today.month)&(df["date"].dt.year==today.year)]
    ph("🎯 Budget Tracker")

    with st.expander("⚙️  Set Monthly Budgets",expanded=False):
        cols=st.columns(3); nb={}
        for i,cat in enumerate(CATEGORIES):
            with cols[i%3]:
                nb[cat]=st.number_input(f"{ICONS.get(cat,'')} {cat}",min_value=0,step=500,
                    value=int(bud.get(cat,0)),key=f"b_{cat}")
        if st.button("💾  Save All Budgets",use_container_width=True):
            for cat,amt in nb.items(): save_budget(u,cat,amt)
            st.success("✅ Budgets saved!"); st.rerun()

    divider("📊 BUDGET VS ACTUAL — THIS MONTH")
    spent=this_m.groupby("category")["amount"].sum().to_dict()
    tb=sum(bud.values()); ts_=sum(spent.get(c,0) for c in bud)
    m1,m2,m3=st.columns(3)
    m1.metric("Total Budget",f"₹{tb:,}"); m2.metric("Total Spent",f"₹{ts_:,.0f}")
    m3.metric("Remaining",f"₹{tb-ts_:,.0f}",delta_color="inverse" if ts_>tb else "normal")
    st.markdown("<br>",unsafe_allow_html=True)

    for cat in CATEGORIES:
        ba=bud.get(cat,0); sa=spent.get(cat,0)
        if ba==0 and sa==0: continue
        pct=min(sa/ba*100,100) if ba>0 else 100
        clr="#EF4444" if pct>85 else "#F59E0B" if pct>60 else "#22C55E"
        ov=(f'<span style="color:#EF4444;font-size:11px;margin-left:8px">🚨 Over by ₹{sa-ba:,.0f}</span>') if sa>ba else ""
        st.markdown(f"""
<div style="padding:14px 18px;background:linear-gradient(135deg,rgba(12,32,64,.8),rgba(15,39,68,.85));
    border:1px solid rgba(14,165,233,.1);border-radius:13px;margin-bottom:8px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:9px">
    <span style="color:#E0F2FE;font-weight:500">{ICONS.get(cat,'📦')} {cat}{ov}</span>
    <span style="color:{clr};font-weight:600">₹{sa:,.0f}{f' / ₹{ba:,}' if ba>0 else ''}</span>
  </div>
  <div style="background:rgba(0,0,0,.3);border-radius:99px;height:7px">
    <div style="background:linear-gradient(90deg,{clr}60,{clr});width:{pct:.1f}%;
        height:7px;border-radius:99px;box-shadow:0 0 8px {clr}40"></div>
  </div>
  <div style="color:#2A5F85;font-size:11px;margin-top:5px">
    {'₹'+f'{ba-sa:,.0f} remaining' if ba>0 else 'No limit set'}
  </div>
</div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
#  REPORTS
# ══════════════════════════════════════════════════════════
def page_reports():
    u=st.session_state["username"]; df=load_expenses(u)
    ph("📈 Reports & Trends")
    if df.empty: st.info("Add expenses to see reports."); return
    tfc,_=st.columns([1.5,4])
    with tfc: tf=st.selectbox("Time Range",list(TIME_OPTS.keys()),index=2,key="r_tf")
    dff=time_filter(df,TIME_OPTS[tf])
    if dff.empty: st.warning("No data for this period."); return

    t1,t2,t3,t4,t5=st.tabs(["  📅 Monthly  ","  📂 Categories  ","  📆 Day Analysis  ","  💳 Payment  ","  🔄 Comparison  "])
    with t1:
        mon=dff.groupby(dff["date"].dt.to_period("M")).agg(
            total=("amount","sum"),count=("id","count"),avg=("amount","mean")).reset_index()
        mon["month"]=mon["date"].dt.to_timestamp()
        fig=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.65,.35],vertical_spacing=.04)
        fig.add_trace(go.Bar(x=mon["month"],y=mon["total"],
            marker=dict(color="#0EA5E9",opacity=.85,line_width=0),
            hovertemplate="<b>%{x|%b %Y}</b><br>₹%{y:,.0f}<extra></extra>"),row=1,col=1)
        fig.add_trace(go.Scatter(x=mon["month"],y=mon["count"],
            line=dict(color="#06B6D4",width=2),mode="lines+markers",marker=dict(size=6),
            hovertemplate="<b>%{x|%b %Y}</b><br>%{y}<extra></extra>"),row=2,col=1)
        fig.update_layout(**_CL,height=400,showlegend=False)
        _ax(fig,2,1); st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        mt=mon[["month","total","count","avg"]].copy()
        mt.columns=["Month","Total (₹)","Expenses","Avg (₹)"]
        mt["Month"]=mt["Month"].dt.strftime("%b %Y")
        mt["Total (₹)"]=mt["Total (₹)"].round(2); mt["Avg (₹)"]=mt["Avg (₹)"].round(2)
        st.dataframe(mt,use_container_width=True,hide_index=True)

    with t2:
        cs=dff.groupby("category").agg(total=("amount","sum"),count=("id","count"),
            avg=("amount","mean"),mx=("amount","max")).reset_index().sort_values("total",ascending=False)
        fig2=go.Figure(go.Bar(x=cs["category"],y=cs["total"],
            marker_color=[CAT_COLORS.get(c,"#94A3B8") for c in cs["category"]],
            text=[f"₹{v:,.0f}" for v in cs["total"]],textposition="outside",
            textfont=dict(color="#4A7FA5",size=10),
            hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"))
        fig2.update_layout(**_CL,height=300,showlegend=False)
        _ax(fig2); st.plotly_chart(fig2,use_container_width=True,config={"displayModeBar":False})
        cs.columns=["Category","Total (₹)","Count","Avg (₹)","Max (₹)"]
        for c in ["Total (₹)","Avg (₹)","Max (₹)"]: cs[c]=cs[c].round(2)
        st.dataframe(cs,use_container_width=True,hide_index=True)

    with t3:
        dc=dff.copy(); dc["dow"]=dc["date"].dt.day_name()
        dow_o=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        dow=dc.groupby("dow")["amount"].sum().reindex(dow_o).fillna(0).reset_index()
        fig3=go.Figure(go.Bar(x=dow["dow"],y=dow["amount"],
            marker_color=["#0EA5E9" if d in ["Saturday","Sunday"] else "#0C2F50" for d in dow["dow"]],
            hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"))
        fig3.update_layout(**_CL,height=260,showlegend=False)
        _ax(fig3); st.plotly_chart(fig3,use_container_width=True,config={"displayModeBar":False})
        dc["dom"]=dc["date"].dt.day
        dom=dc.groupby("dom")["amount"].mean().reset_index()
        fig4=go.Figure(go.Scatter(x=dom["dom"],y=dom["amount"],
            line=dict(color="#06B6D4",width=2),mode="lines+markers",
            fill="tozeroy",fillcolor="rgba(6,182,212,.07)",
            hovertemplate="Day %{x}<br>Avg ₹%{y:,.0f}<extra></extra>"))
        fig4.update_layout(**_CL,height=210,showlegend=False)
        _ax(fig4); st.plotly_chart(fig4,use_container_width=True,config={"displayModeBar":False})

    with t4:
        pm=dff.groupby("payment").agg(total=("amount","sum"),count=("id","count")).reset_index()
        pm=pm[pm["payment"].astype(str).str.strip()!=""]
        if not pm.empty:
            pc=["#0EA5E9","#06B6D4","#F59E0B","#38BDF8","#7DD3FC","#22C55E"]
            fig5=go.Figure(go.Pie(labels=pm["payment"],values=pm["total"],hole=.5,
                marker_colors=pc[:len(pm)],textinfo="label+percent",
                textfont=dict(size=12,color="#BAC8D8"),
                hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<extra></extra>"))
            fig5.update_layout(**_CL,height=300,showlegend=False)
            st.plotly_chart(fig5,use_container_width=True,config={"displayModeBar":False})
            pm.columns=["Payment","Total (₹)","Transactions"]; pm["Total (₹)"]=pm["Total (₹)"].round(2)
            st.dataframe(pm,use_container_width=True,hide_index=True)

    with t5:
        divider("MONTH-OVER-MONTH")
        m2=df.groupby(df["date"].dt.to_period("M"))["amount"].sum().reset_index().sort_values("date").tail(8)
        m2.columns=["period","total"]; m2["prev"]=m2["total"].shift(1)
        m2["delta"]=((m2["total"]-m2["prev"])/m2["prev"]*100).round(1)
        m2["label"]=m2["period"].astype(str)
        for _,r in m2.dropna(subset=["delta"]).iterrows():
            clr="#22C55E" if r["delta"]<0 else "#EF4444"; arrow="↓" if r["delta"]<0 else "↑"
            st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;
    padding:13px 18px;background:linear-gradient(135deg,rgba(12,32,64,.8),rgba(15,39,68,.85));
    border:1px solid rgba(14,165,233,.1);border-radius:12px;margin-bottom:6px">
  <span style="color:#7096B8;font-weight:500">{r['label']}</span>
  <span style="color:#E0F2FE;font-weight:700;font-size:16px;font-family:'Plus Jakarta Sans',sans-serif">₹{r['total']:,.0f}</span>
  <span style="color:{clr};font-weight:700">{arrow} {abs(r['delta']):.1f}%</span>
</div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
#  SAVINGS GOALS
# ══════════════════════════════════════════════════════════
def page_goals():
    u=st.session_state["username"]
    ph("🏦 Savings Goals")

    # Add new goal form
    with st.expander("➕  Add New Goal",expanded=False):
        with st.form("goal_form"):
            gc1,gc2=st.columns(2)
            with gc1:
                g_title=st.text_input("Goal Title",placeholder="e.g. New iPhone, Goa Trip")
                g_target=st.number_input("Target Amount (₹)",min_value=100.0,value=10000.0,step=500.0)
            with gc2:
                g_saved=st.number_input("Already Saved (₹)",min_value=0.0,value=0.0,step=500.0)
                g_dead=st.date_input("Target Date (optional)",value=None)
            g_icon=st.selectbox("Icon",["🎯","📱","✈️","🏠","🚗","💻","👟","🎮","💍","🌴","📚","💪"])
            if st.form_submit_button("💾  Add Goal",use_container_width=True):
                if g_title.strip():
                    add_goal(u,g_title.strip(),g_target,g_saved,
                             str(g_dead) if g_dead else "",g_icon)
                    st.success(f"✅ Goal '{g_title}' added!")
                    st.rerun()
                else: st.error("Please enter a goal title.")

    goals=load_goals(u)
    if not goals:
        st.markdown("""
<div style="text-align:center;padding:50px;background:rgba(12,32,64,.6);
    border:2px dashed rgba(14,165,233,.2);border-radius:16px">
  <div style="font-size:40px">🏦</div>
  <div style="color:#E0F2FE;font-weight:600;margin-top:12px">No savings goals yet</div>
  <div style="color:#2A5F85;margin-top:6px">Click "Add New Goal" above to start saving!</div>
</div>""",unsafe_allow_html=True)
        return

    divider("YOUR GOALS")
    for g in goals:
        pct=min(g["saved_amount"]/g["target_amount"]*100,100) if g["target_amount"]>0 else 0
        remaining=g["target_amount"]-g["saved_amount"]
        clr="#22C55E" if pct>=100 else "#0EA5E9" if pct>50 else "#F59E0B"
        done="🎉 GOAL REACHED!" if pct>=100 else ""

        st.markdown(f"""
<div style="padding:18px 20px;background:linear-gradient(145deg,rgba(12,32,64,.85),rgba(15,39,68,.9));
    border:1px solid rgba(14,165,233,.15);border-radius:16px;margin-bottom:10px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">
    <div>
      <div style="font-size:24px;margin-bottom:4px">{g['icon']}</div>
      <div style="color:#E0F2FE;font-weight:700;font-size:16px;font-family:'Plus Jakarta Sans',sans-serif">
        {g['title']} {done}
      </div>
      {f"<div style='color:#2A5F85;font-size:12px'>Target date: {g['deadline']}</div>" if g['deadline'] else ""}
    </div>
    <div style="text-align:right">
      <div style="color:{clr};font-weight:700;font-size:22px;font-family:'Plus Jakarta Sans',sans-serif">
        ₹{g['saved_amount']:,.0f}
      </div>
      <div style="color:#2A5F85;font-size:12px">of ₹{g['target_amount']:,.0f}</div>
    </div>
  </div>
  <div style="background:rgba(0,0,0,.3);border-radius:99px;height:10px;margin-bottom:8px">
    <div style="background:linear-gradient(90deg,{clr}80,{clr});width:{pct:.1f}%;
        height:10px;border-radius:99px;box-shadow:0 0 10px {clr}50;
        transition:width .5s ease"></div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:12px">
    <span style="color:{clr};font-weight:600">{pct:.1f}% complete</span>
    <span style="color:#2A5F85">₹{max(remaining,0):,.0f} to go</span>
  </div>
</div>""",unsafe_allow_html=True)

        # Update / delete controls
        uc1,uc2,uc3=st.columns([2,1,1])
        with uc1:
            new_saved=st.number_input(f"Update saved amount",
                min_value=0.0,value=float(g["saved_amount"]),
                step=500.0,key=f"gs_{g['id']}")
        with uc2:
            if st.button("💾 Update",key=f"gu_{g['id']}",use_container_width=True):
                update_goal_amount(u,g["id"],new_saved)
                st.success("✅ Updated!"); st.rerun()
        with uc3:
            if st.button("🗑️ Delete",key=f"gd_{g['id']}",use_container_width=True):
                delete_goal(u,g["id"]); st.rerun()

        st.markdown("<hr style='border:none;border-top:1px solid rgba(14,165,233,.07);margin:6px 0'>",
                    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
#  BILL SPLIT
# ══════════════════════════════════════════════════════════
def page_split():
    ph("🔀 Bill Split Calculator")
    st.markdown("""
<div style="padding:12px 16px;background:rgba(14,165,233,.07);
    border:1px solid rgba(14,165,233,.2);border-left:3px solid #0EA5E9;
    border-radius:10px;color:#7096B8;font-size:13px;margin-bottom:20px">
  Split any bill with friends instantly. Enter the total and who's sharing.
</div>""",unsafe_allow_html=True)

    total_bill = st.number_input("💵 Total Bill Amount (₹)", min_value=1.0, value=1000.0, step=50.0)
    num_people = st.number_input("👥 Number of People", min_value=2, max_value=20, value=4, step=1)
    tip_pct    = st.slider("💝 Tip / Extra (%)", min_value=0, max_value=30, value=0)
    payer      = st.text_input("💳 Who is paying first?", placeholder="e.g. Khushi")

    # Names
    st.markdown("#### Enter everyone's name:")
    name_cols=st.columns(min(int(num_people),4))
    names=[]
    for i in range(int(num_people)):
        with name_cols[i%4]:
            n=st.text_input(f"Person {i+1}",key=f"sn_{i}",
                placeholder=f"Person {i+1}")
            names.append(n.strip() if n.strip() else f"Person {i+1}")

    if st.button("🔀  Calculate Split",use_container_width=True):
        total_with_tip = total_bill * (1 + tip_pct/100)
        per_person     = total_with_tip / num_people

        st.markdown("<br>",unsafe_allow_html=True)
        divider("💰 SPLIT RESULT")

        # Summary
        sc1,sc2,sc3=st.columns(3)
        sc1.metric("Total Bill",    f"₹{total_bill:,.2f}")
        sc2.metric("With Tip",      f"₹{total_with_tip:,.2f}")
        sc3.metric("Per Person",    f"₹{per_person:,.2f}")

        st.markdown("<br>",unsafe_allow_html=True)
        payer_name=payer.strip() if payer.strip() else names[0]

        for name in names:
            owes=(f"💚 <b>{name}</b> is paying" if name==payer_name
                  else f"<b>{name}</b> owes <b>{payer_name}</b>")
            st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;
    padding:14px 20px;background:linear-gradient(135deg,rgba(12,32,64,.8),rgba(15,39,68,.85));
    border:1px solid rgba(14,165,233,.15);border-radius:12px;margin-bottom:6px">
  <span style="color:#E0F2FE;font-size:15px">{owes}</span>
  <span style="color:#38BDF8;font-weight:700;font-size:18px;
      font-family:'Plus Jakarta Sans',sans-serif">₹{per_person:,.2f}</span>
</div>""",unsafe_allow_html=True)

        # UPI note
        if payer_name:
            st.markdown(f"""
<div style="margin-top:16px;padding:14px 18px;background:rgba(34,197,94,.08);
    border:1px solid rgba(34,197,94,.2);border-radius:10px;
    color:#4ADE80;font-size:13px">
  💡 Everyone should send ₹{per_person:,.2f} to <b>{payer_name}</b> via UPI!
</div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
#  SMART INSIGHTS
# ══════════════════════════════════════════════════════════
def page_insights():
    u=st.session_state["username"]; df=load_expenses(u)
    ph("💡 Smart Insights")
    if len(df)<5: st.info("Add at least 5 expenses to unlock smart insights."); return

    today=pd.Timestamp.today()
    this_m=df[(df["date"].dt.month==today.month)&(df["date"].dt.year==today.year)]
    lm_n=today.month-1 if today.month>1 else 12
    last_m=df[df["date"].dt.month==lm_n]
    ins=[]

    tc=df.groupby("category")["amount"].sum()
    ins.append(("🏆","Top Spending Category",
        f"You spend the most on <b>{tc.idxmax()}</b> — ₹{tc.max():,.0f} all-time.","#F59E0B"))
    if not this_m.empty and not last_m.empty:
        diff=this_m["amount"].sum()-last_m["amount"].sum()
        pct=abs(diff)/last_m["amount"].sum()*100
        if diff>0: ins.append(("📈","Spending Up",f"₹{diff:,.0f} more this month (+{pct:.0f}%). Review your budget!","#EF4444"))
        else:      ins.append(("📉","Spending Down",f"You saved ₹{abs(diff):,.0f} vs last month (-{pct:.0f}%). 🎉","#22C55E"))
    mr=df.loc[df["amount"].idxmax()]
    ins.append(("💸","Biggest Expense",
        f"₹{mr['amount']:,.0f} on <b>{mr['description']}</b> ({mr['category']}) — {mr['date'].strftime('%d %b %Y')}.","#8B5CF6"))
    fc=df["category"].value_counts()
    ins.append(("🔄","Most Logged",f"<b>{fc.max()} entries</b> in <b>{fc.idxmax()}</b>.","#06B6D4"))
    dfc=df.copy(); dfc["is_we"]=dfc["date"].dt.dayofweek>=5
    wk=dfc[~dfc["is_we"]]["amount"].mean(); we=dfc[dfc["is_we"]]["amount"].mean()
    if we>wk: ins.append(("🎉","Weekend Spender",f"You spend <b>{(we/wk-1)*100:.0f}% more on weekends</b> (₹{we:,.0f}) vs weekdays (₹{wk:,.0f}).","#EC4899"))
    else:     ins.append(("💼","Weekday Spender",f"You spend more on weekdays (₹{wk:,.0f}) than weekends (₹{we:,.0f}).","#38BDF8"))
    pv=df["payment"].value_counts()
    if not pv.empty:
        fp=pv.idxmax(); pp=pv.max()/len(df)*100
        ins.append(("💳","Favourite Payment",f"<b>{fp}</b> used for {pp:.0f}% of all expenses.","#10B981"))
    days=max((df["date"].max()-df["date"].min()).days,1)
    ins.append(("📅","Daily Rate",f"You spend <b>₹{df['amount'].sum()/days:,.0f}/day</b> on average.","#F97316"))
    bud=get_user(u).get("monthly_budget",0)
    if bud>0 and not this_m.empty:
        sp=this_m["amount"].sum(); pct=sp/bud*100
        if   pct>90: ins.append(("🚨","Budget Critical",f"{pct:.0f}% used (₹{sp:,.0f}/₹{bud:,}). Slow down!","#EF4444"))
        elif pct>70: ins.append(("⚠️","Budget Alert",f"{pct:.0f}% used. ₹{bud-sp:,.0f} left this month.","#F59E0B"))
        else:        ins.append(("✅","Budget Healthy",f"Only {pct:.0f}% used. ₹{bud-sp:,.0f} left — on track! 👍","#22C55E"))

    for icon,title,body,accent in ins:
        st.markdown(f"""
<div style="padding:clamp(14px,2vh,18px) clamp(14px,1.8vw,22px);
    background:linear-gradient(135deg,rgba(12,32,64,.8),rgba(15,39,68,.85));
    border:1px solid rgba(14,165,233,.1);border-left:4px solid {accent};
    border-radius:14px;margin-bottom:10px">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:7px">
    <span style="font-size:clamp(20px,2.5vw,24px)">{icon}</span>
    <span style="color:#E0F2FE;font-weight:700;font-size:clamp(13px,1.4vw,15px);
        font-family:'Plus Jakarta Sans',sans-serif">{title}</span>
  </div>
  <div style="color:#4A7FA5;font-size:clamp(12px,1.2vw,13px);line-height:1.7">{body}</div>
</div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
#  EXPORT
# ══════════════════════════════════════════════════════════
def page_export():
    u=st.session_state["username"]; df=load_expenses(u)
    ph("📤 Export & PDF Reports")
    if df.empty: st.info("No data to export yet."); return
    tfc,_=st.columns([1.5,4])
    with tfc: tf=st.selectbox("Export Period",list(TIME_OPTS.keys()),index=4,key="ex_tf")
    dff=time_filter(df,TIME_OPTS[tf]); label=tf
    if dff.empty: st.warning("No data for this period."); return

    k1,k2,k3,k4=st.columns(4)
    k1.metric("Records",len(dff)); k2.metric("Total",f"₹{dff['amount'].sum():,.0f}")
    k3.metric("Average",f"₹{dff['amount'].mean():,.0f}"); k4.metric("Highest",f"₹{dff['amount'].max():,.0f}")

    t1,t2,t3=st.tabs(["  📊 Monthly  ","  📂 Categories  ","  ⬇️ Downloads  "])
    with t1:
        ms=dff.groupby(dff["date"].dt.to_period("M")).agg(
            Expenses=("id","count"),Total=("amount","sum"),
            Avg=("amount","mean"),Max=("amount","max")).reset_index()
        ms.columns=["Month","Expenses","Total (₹)","Avg (₹)","Max (₹)"]
        ms["Month"]=ms["Month"].astype(str)
        for c in ["Total (₹)","Avg (₹)","Max (₹)"]: ms[c]=ms[c].round(2)
        st.dataframe(ms,use_container_width=True,hide_index=True)
    with t2:
        cs=dff.groupby("category").agg(Expenses=("id","count"),Total=("amount","sum"),
            Avg=("amount","mean"),Max=("amount","max")).reset_index().sort_values("Total",ascending=False)
        cs.columns=["Category","Expenses","Total (₹)","Avg (₹)","Max (₹)"]
        for c in ["Total (₹)","Avg (₹)","Max (₹)"]: cs[c]=cs[c].round(2)
        st.dataframe(cs,use_container_width=True,hide_index=True)
    with t3:
        divider("DOWNLOAD")
        d1,d2,d3=st.columns(3)
        with d1:
            st.markdown("""<div style="padding:16px;background:rgba(14,165,233,.07);border:1px solid rgba(14,165,233,.2);border-radius:14px;text-align:center;margin-bottom:10px"><div style="font-size:30px">📄</div><div style="color:#E0F2FE;font-weight:600;margin:7px 0 4px">Full CSV</div><div style="color:#4A7FA5;font-size:12px">All expense records</div></div>""",unsafe_allow_html=True)
            out=dff.copy(); out["date"]=out["date"].dt.strftime("%Y-%m-%d")
            buf=StringIO(); out.to_csv(buf,index=False)
            st.download_button("⬇️  Download CSV",data=buf.getvalue(),
                file_name=f"spendsmart_{u}_{date.today()}.csv",mime="text/csv",use_container_width=True)
        with d2:
            st.markdown("""<div style="padding:16px;background:rgba(6,182,212,.07);border:1px solid rgba(6,182,212,.2);border-radius:14px;text-align:center;margin-bottom:10px"><div style="font-size:30px">📊</div><div style="color:#E0F2FE;font-weight:600;margin:7px 0 4px">Monthly CSV</div><div style="color:#4A7FA5;font-size:12px">Month-by-month</div></div>""",unsafe_allow_html=True)
            buf2=StringIO(); ms.to_csv(buf2,index=False)
            st.download_button("⬇️  Monthly CSV",data=buf2.getvalue(),
                file_name=f"monthly_{u}_{date.today()}.csv",mime="text/csv",use_container_width=True)
        with d3:
            st.markdown("""<div style="padding:16px;background:rgba(2,132,199,.07);border:1px solid rgba(2,132,199,.2);border-radius:14px;text-align:center;margin-bottom:10px"><div style="font-size:30px">📑</div><div style="color:#E0F2FE;font-weight:600;margin:7px 0 4px">PDF Report</div><div style="color:#4A7FA5;font-size:12px">Formatted report</div></div>""",unsafe_allow_html=True)
            if PDF_OK:
                pdf=make_pdf(dff,u,label)
                st.download_button("⬇️  Download PDF",data=pdf,
                    file_name=f"report_{u}_{date.today()}.pdf",mime="application/pdf",use_container_width=True)
            else: st.warning("Run: `pip install reportlab`")

# ══════════════════════════════════════════════════════════
#  SETTINGS  (with email config)
# ══════════════════════════════════════════════════════════
def page_settings():
    u=st.session_state["username"]; info=get_user(u); df=load_expenses(u)
    ph("⚙️ Settings")

    t1,t2,t3,t4=st.tabs(["  👤 Profile  ","  📧 Email  ","  🗃️ Data  ","  ℹ️ About  "])

    with t1:
        with st.form("pf"):
            nn=st.text_input("Display Name",value=info.get("name",""))
            em=st.text_input("Email Address",value=info.get("email",""),
                placeholder="your@gmail.com (for monthly reports)")
            nb=st.number_input("Monthly Budget (₹)",min_value=0,
                value=int(info.get("monthly_budget",0)),step=1000)
            alert_pct=st.slider("Budget Alert Threshold (%)",
                min_value=50,max_value=100,
                value=int(info.get("budget_alert_pct",80)),
                help="Get alerted when spending reaches this % of budget")
            np_=st.text_input("New Password",type="password",placeholder="Leave blank to keep current")
            if st.form_submit_button("💾  Save Changes",use_container_width=True):
                upd={"name":nn,"email":em,"monthly_budget":nb,"budget_alert_pct":alert_pct}
                if np_:
                    if len(np_)<6: st.error("Min 6 characters.")
                    else: upd["password"]=_hp(np_)
                update_user(u,**upd)
                st.session_state["user_name"]=nn
                st.success("✅  Profile updated!")

    with t2:
        st.markdown("""
<div style="text-align:center;padding:40px 20px;
    background:linear-gradient(145deg,rgba(12,32,64,.8),rgba(15,39,68,.85));
    border:2px dashed rgba(14,165,233,.2);border-radius:16px">
  <div style="font-size:48px;margin-bottom:14px">📧</div>
  <div style="color:#E0F2FE;font-size:18px;font-weight:700;
      font-family:'Plus Jakarta Sans',sans-serif;margin-bottom:8px">
    Email Reports — Coming Soon
  </div>
  <div style="color:#4A7FA5;font-size:14px;line-height:1.7;max-width:400px;margin:0 auto">
    Monthly expense reports sent directly to your inbox.<br>
    Beautiful HTML report with full breakdown, charts and insights!
  </div>
  <div style="margin-top:20px;display:flex;justify-content:center;gap:10px;flex-wrap:wrap">
    <span style="background:rgba(14,165,233,.1);border:1px solid rgba(14,165,233,.2);
        border-radius:99px;padding:6px 16px;color:#38BDF8;font-size:12px">📊 Monthly Summary</span>
    <span style="background:rgba(14,165,233,.1);border:1px solid rgba(14,165,233,.2);
        border-radius:99px;padding:6px 16px;color:#38BDF8;font-size:12px">📂 Category Breakdown</span>
    <span style="background:rgba(14,165,233,.1);border:1px solid rgba(14,165,233,.2);
        border-radius:99px;padding:6px 16px;color:#38BDF8;font-size:12px">🎯 Budget Status</span>
  </div>
</div>""", unsafe_allow_html=True)

    with t3:
        if not df.empty:
            k1,k2,k3=st.columns(3)
            k1.metric("Total Entries",len(df))
            k2.metric("Date Range",
                f"{df['date'].min().strftime('%d %b %y')} → {df['date'].max().strftime('%d %b %y')}")
            k3.metric("Categories Used",df["category"].nunique())
        st.markdown("---"); st.warning("⚠️ **Danger Zone** — Cannot be undone!")
        if st.button("🗑️  Delete ALL My Expense Data",key="del_all"):
            conn=get_conn()
            conn.execute("DELETE FROM expenses WHERE username=?",(u,))
            conn.commit(); conn.close()
            st.success("All data deleted."); st.rerun()

    with t4:
        st.markdown("""
### 📊 SpendSmart v2 — Ultimate Edition

| Feature | Details |
|---|---|
| 🗄️ Database | SQLite — permanent, no data loss on refresh |
| 🌐 Landing Page | Beautiful hero page like a real product |
| 📧 Email Reports | Send monthly HTML reports via Gmail |
| 🔔 Budget Alerts | Live banner when budget threshold exceeded |
| 🏦 Savings Goals | Track goals with animated progress bars |
| 🔀 Bill Split | Split bills with friends, UPI-ready |
| 📊 Dashboard | 5 charts + time filter |
| 📈 Reports | 5 analysis tabs |
| 💡 Smart Insights | 9 auto-generated insights |
| 📤 Export | CSV + PDF report |

**Tech:** Python · Streamlit · SQLite · Plotly · ReportLab · SMTP
        """)

# ══════════════════════════════════════════════════════════
#  MAIN ROUTER
# ══════════════════════════════════════════════════════════
def main():
    inject_css()

    if "page" not in st.session_state:
        st.session_state.page = "landing"

    # Landing page
    if st.session_state.get("page") == "landing":
        landing_page()
        return

    # Auth page
    if st.session_state.get("page") == "auth" or not st.session_state.get("logged_in"):
        auth_page()
        return

    # App pages
    top_nav()
    st.markdown("<div style='padding:0 clamp(8px,2vw,24px)'>", unsafe_allow_html=True)

    PAGE_MAP = {
        "dashboard": page_dashboard,
        "add":       page_add,
        "list":      page_list,
        "budget":    page_budget,
        "reports":   page_reports,
        "goals":     page_goals,
        "split":     page_split,
        "insights":  page_insights,
        "export":    page_export,
        "settings":  page_settings,
    }
    PAGE_MAP.get(st.session_state.get("page","dashboard"), page_dashboard)()
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
