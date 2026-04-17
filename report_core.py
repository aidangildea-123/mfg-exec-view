import os
import json
import base64
import requests
from datetime import date, timedelta, timezone, datetime

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend


# ── Credentials (stored as GitHub Secrets) ────────────────────────────────────
NS_ACCOUNT_ID      = os.environ["NS_ACCOUNT_ID"].lower().replace("_", "-")
NS_CONSUMER_KEY    = os.environ["NS_CONSUMER_KEY"]
NS_CERTIFICATE_ID  = os.environ["NS_CERTIFICATE_ID"]
NS_PRIVATE_KEY_PEM = os.environ["NS_PRIVATE_KEY"]  # Full PEM string

OUTPUT_DIR = "docs"

# ── Restaurant config ──────────────────────────────────────────────────────────
VINO = {12, 15, 50, 51, 52, 53, 54, 350, 351}

RESTAURANTS = [
    {"name": "Carbone Dallas",             "region": "Southwest",     "ids": [28],    "dallas": True,  "dType": "carbone", "cc": [31, 35]},
    {"name": "Carbone London",             "region": "International", "ids": [53],    "dallas": False,                    "cc": [31, 337]},
    {"name": "Carbone Miami",              "region": "Southeast",     "ids": [39],    "dallas": False,                    "cc": [31, 35]},
    {"name": "Carbone New York",           "region": "Northeast",     "ids": [56],    "dallas": False,                    "cc": [31]},
    {"name": "Carbone Vino Coconut Grove", "region": "Southeast",     "ids": [20],    "dallas": False,                    "cc": [31]},
    {"name": "Chateau ZZ's",               "region": "Southeast",     "ids": [33],    "dallas": False,                    "cc": [31]},
    {"name": "Clam Bar",                   "region": "Northeast",     "ids": [55],    "dallas": False,                    "cc": [31]},
    {"name": "Contessa Boston",            "region": "Northeast",     "ids": [57],    "dallas": False,                    "cc": [31]},
    {"name": "Contessa Miami",             "region": "Southeast",     "ids": [34],    "dallas": False,                    "cc": [31, 156]},
    {"name": "Dirty French New York",      "region": "Northeast",     "ids": [10],    "dallas": False,                    "cc": [31, 35]},
    {"name": "Dirty French Steakhouse",    "region": "Southeast",     "ids": [36],    "dallas": False,                    "cc": [31]},
    {"name": "HaSalon",                    "region": "Southeast",     "ids": [38],    "dallas": False,                    "cc": [31]},
    {"name": "Parm Battery Park",          "region": "Parm",          "ids": [43],    "dallas": False,                    "cc": [31, 35, 2]},
    {"name": "Parm Copley",                "region": "Parm",          "ids": [45],    "dallas": False,                    "cc": [31, 35, 2, 29]},
    {"name": "Parm Mulberry",              "region": "Parm",          "ids": [47],    "dallas": False,                    "cc": [31, 35, 2]},
    {"name": "Parm Upper West",            "region": "Parm",          "ids": [49],    "dallas": False,                    "cc": [31, 35, 2]},
    {"name": "Parm Woodbury",              "region": "Parm",          "ids": [50],    "dallas": False,                    "cc": [31, 35, 2]},
    {"name": "Sadelle's Coconut Grove",    "region": "Southeast",     "ids": [37],    "dallas": False,                    "cc": [31, 35]},
    {"name": "Sadelle's Highland Park",    "region": "Southwest",     "ids": [27],    "dallas": False,                    "cc": [31, 35]},
    {"name": "Sadelle's New York",         "region": "Northeast",     "ids": [15],    "dallas": False,                    "cc": [31, 35]},
    {"name": "THE GRILL / THE POOL",       "region": "Northeast",     "ids": [7, 8],  "dallas": False,                    "cc": [31]},
    {"name": "The Lobster Club",           "region": "Northeast",     "ids": [6],     "dallas": False,                    "cc": [31]},
    {"name": "Torrisi",                    "region": "Northeast",     "ids": [12],    "dallas": False,                    "cc": [31, 2]},
    {"name": "Vino Dallas",                "region": "Southwest",     "ids": [28],    "dallas": True,  "dType": "vino",    "cc": [53, 54]},
    {"name": "ZZ's Club Miami",            "region": "Southeast",     "ids": [40],    "dallas": False,                    "cc": [31, 35, 152, 154]},
]

REGION_ORDER  = ["Northeast", "Southeast", "Southwest", "International", "Parm"]
REGION_ACCENT = {"Northeast": "#1d4ed8", "Southeast": "#059669", "Southwest": "#d97706", "International": "#7c3aed", "Parm": "#dc2626"}
REGION_BG     = {"Northeast": "#eff6ff", "Southeast": "#f0fdf4", "Southwest": "#fffbeb", "International": "#f5f3ff", "Parm": "#fef2f2"}
REGION_BORDER = {"Northeast": "#bfdbfe", "Southeast": "#a7f3d0", "Southwest": "#fde68a", "International": "#ddd6fe", "Parm": "#fecaca"}

ALL_IDS     = list({i for r in RESTAURANTS if not r["dallas"] for i in r["ids"]})
NON_DAL_IDS = [i for i in ALL_IDS if i != 28]
IN_ALL      = ", ".join(str(i) for i in ALL_IDS)
IN_NON_DAL  = ", ".join(str(i) for i in NON_DAL_IDS)


# ── OAuth 2.0 JWT (PS256) ──────────────────────────────────────────────────────
def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def get_access_token() -> str:
    token_url = f"https://{NS_ACCOUNT_ID}.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token"
    now = int(datetime.now(timezone.utc).timestamp())

    header  = {"alg": "PS256", "typ": "JWT", "kid": NS_CERTIFICATE_ID}
    payload = {
        "iss":   NS_CONSUMER_KEY,
        "scope": ["restlets", "rest_webservices"],
        "iat":   now,
        "exp":   now + 3600,
        "aud":   token_url,
    }

    h = b64url(json.dumps(header,  separators=(",", ":")).encode())
    p = b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{h}.{p}".encode()

    pem = NS_PRIVATE_KEY_PEM.replace("\\n", "\n").strip()
    if not pem.startswith("-----"):
        raise ValueError("NS_PRIVATE_KEY does not look like a valid PEM key. Check the secret value.")
    private_key = serialization.load_pem_private_key(
        pem.encode(), password=None, backend=default_backend()
    )
    sig = private_key.sign(
        signing_input,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
        hashes.SHA256(),
    )
    jwt = f"{h}.{p}.{b64url(sig)}"

    resp = requests.post(
        token_url,
        data={
            "grant_type":            "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion":      jwt,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if not resp.ok:
        print(f"  NetSuite auth error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    print("  Access token obtained")
    return resp.json()["access_token"]


# ── SuiteQL (with pagination) ──────────────────────────────────────────────────
def run_sql(sql: str, token: str) -> list:
    url     = f"https://{NS_ACCOUNT_ID}.suitetalk.api.netsuite.com/services/rest/query/v1/suiteql"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Prefer": "transient"}
    rows, offset, limit = [], 0, 500
    while True:
        resp = requests.post(f"{url}?limit={limit}&offset={offset}", json={"q": sql}, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        rows += data.get("items", [])
        if not data.get("hasMore", False):
            break
        offset += limit
    return rows


# ── Date helpers ───────────────────────────────────────────────────────────────
def norm(raw):
    if not raw:
        return ""
    if len(raw) == 10 and raw[4] == "-":
        return raw
    m, d, y = raw.split("/")
    return f"{y}-{m.zfill(2)}-{d.zfill(2)}"

def sql_dates(*ds):
    return ", ".join(f"TO_DATE('{d}','YYYY-MM-DD')" for d in ds)


# ── Data fetching ──────────────────────────────────────────────────────────────
def fetch_all(dc, dlw, dly, token):
    d_sql = sql_dates(dc, dlw, dly)

    print("  [1/4] FX rates...")
    fx = {}
    for r in run_sql(
        f"SELECT cr.effectiveDate, cr.transactionCurrency AS currency, cr.exchangeRate "
        f"FROM currencyrate cr WHERE cr.effectiveDate IN ({d_sql}) ORDER BY cr.effectiveDate",
        token
    ):
        dk  = norm(r.get("effectivedate", ""))
        cid = int(r.get("currency", 1))
        fx[f"{dk}|{cid}"] = float(r.get("exchangerate", 1))
    print(f"  FX rows: {len(list(fx.keys()))} rates loaded, sample keys: {list(fx.keys())[:3]}")

    def gfx(dk, cid):
        return 1.0 if cid == 1 else fx.get(f"{dk}|{cid}", 1.0)

    print("  [2/4] Sales...")
    sub = {}
    sales_raw = run_sql(
        f"SELECT t.trandate, t.subsidiary, t.currency, SUM(tl.foreignamount)*-1 AS net_sales "
        f"FROM transactionline tl JOIN transaction t ON t.id=tl.transaction "
        f"JOIN account a ON a.id=tl.account "
        f"WHERE t.subsidiary IN ({IN_NON_DAL}) AND t.trandate IN ({d_sql}) "
        f"AND t.type IN ('Journal','CustInvc') AND a.accttype='Income' "
        f"AND (t.approvalstatus=2 OR t.approvalstatus IS NULL) "
        f"GROUP BY t.trandate, t.subsidiary, t.currency",
        token
    )
    if sales_raw:
        print(f"  Sales sample row keys: {list(sales_raw[0].keys())} values: {sales_raw[0]}")
    for r in sales_raw:
        sid = int(r["subsidiary"])
        dk = norm(r["trandate"])
        cid = int(r.get("currency", 1))
        sub.setdefault(sid, {})[dk] = round(float(r.get("net_sales") or 0) * gfx(dk, cid), 2)
    print(f"  Sales loaded: {sum(len(v) for v in sub.values())} date-entries across {len(sub)} subsidiaries")

    print("  [3/4] Dallas class split...")
    dal = {}
    for r in run_sql(
        f"SELECT t.trandate, tl.class, SUM(tl.foreignamount)*-1 AS net_sales "
        f"FROM transactionline tl JOIN transaction t ON t.id=tl.transaction "
        f"JOIN account a ON a.id=tl.account "
        f"WHERE t.subsidiary=28 AND t.trandate IN ({d_sql}) "
        f"AND t.type IN ('Journal','CustInvc') AND a.accttype='Income' "
        f"AND (t.approvalstatus=2 OR t.approvalstatus IS NULL) "
        f"GROUP BY t.trandate, tl.class",
        token
    ):
        dk = norm(r["trandate"])
        cls = r.get("class")
        v = float(r.get("net_sales") or 0)
        dal.setdefault(dk, {"c": 0, "v": 0, "ok": False})
        if cls is not None:
            dal[dk]["ok"] = True
            if int(cls) in VINO:
                dal[dk]["v"] += v
            else:
                dal[dk]["c"] += v

    print("  [4/4] Covers...")
    cm = {}
    for r in run_sql(
        f"SELECT sje.trandate, sje.subsidiary, sjel.class, SUM(sjel.debit) AS cover_count "
        f"FROM statisticaljournalentryline sjel "
        f"JOIN statisticaljournalentry sje ON sje.id=sjel.journal "
        f"WHERE sjel.account=2671 AND sje.subsidiary IN ({IN_ALL}) AND sje.trandate IN ({d_sql}) "
        f"GROUP BY sje.trandate, sje.subsidiary, sjel.class",
        token
    ):
        k = (int(r["subsidiary"]), norm(r["trandate"]), int(r.get("class", 0)))
        cm[k] = cm.get(k, 0) + float(r.get("cover_count") or 0)

    return sub, dal, cm


# ── Row builder ────────────────────────────────────────────────────────────────
def get_sales(sub, dal, r, dk):
    if r["dallas"]:
        d = dal.get(dk, {})
        return (d["v"] if r["dType"] == "vino" else d["c"]) if d.get("ok") else None
    ids = r["ids"]
    t = sum(sub.get(i, {}).get(dk, 0) for i in ids)
    return t if any(sub.get(i, {}).get(dk) is not None for i in ids) else None

def get_covers(cm, r, dk):
    ids = r["ids"]
    cc = r["cc"]
    t = sum(cm.get((i, dk, c), 0) for i in ids for c in cc)
    return t or None

def build_rows(sub, dal, cm, dc, dlw, dly):
    rows = []
    for r in RESTAURANTS:
        rows.append({
            "name":  r["name"],
            "region": r["region"],
            "sCur": get_sales(sub, dal, r, dc),
            "sLw":  get_sales(sub, dal, r, dlw),
            "sLy":  get_sales(sub, dal, r, dly),
            "cCur": get_covers(cm, r, dc),
            "cLw":  get_covers(cm, r, dlw),
            "cLy":  get_covers(cm, r, dly),
        })
    return rows


# ── Formatters ─────────────────────────────────────────────────────────────────
def fmt(n):
    return "\u2014" if n is None else "$" + f"{round(abs(n)):,}"

def fmtC(n):
    return "\u2014" if n is None else f"{int(n):,}"

def pct(c, p):
    if c is None or p is None:
        return None
    if p == 0 and c == 0:
        return 0
    if p == 0:
        return None
    return (c - p) / p

def fmtP(p):
    if p is None:
        return "\u2014"
    if p == 0:
        return "0%"
    return f"+{p*100:.0f}%" if p > 0 else f"({abs(p*100):.0f}%)"

def pc(p):
    return "#9ca3af" if p is None else "#15803d" if p >= 0 else "#b91c1c"


# ── HTML helpers and shared payload ────────────────────────────────────────────
def badge(p, label):
    if p is None:
        return ""
    pos = p >= 0
    bg = "#dcfce7" if pos else "#fee2e2"
    col = "#15803d" if pos else "#b91c1c"
    bdr = "#bbf7d0" if pos else "#fecaca"
    return (
        f'<span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;'
        f'background:{bg};color:{col};border:1px solid {bdr};display:inline-block;margin-right:4px">'
        f'{fmtP(p)} {label}</span>'
    )

def build_report_payload(target: date, token: str) -> dict:
    dc = target.isoformat()
    dlw = (target - timedelta(weeks=1)).isoformat()
    dly = (target - timedelta(weeks=52)).isoformat()

    sub, dal, cm = fetch_all(dc, dlw, dly, token)
    rows = build_rows(sub, dal, cm, dc, dlw, dly)

    return {
        "report_date": dc,
        "wow_date": dlw,
        "yoy_date": dly,
        "rows": rows,
        "summary": {
            "sales_current": round(sum(r["sCur"] or 0 for r in rows), 2),
            "sales_last_week": round(sum(r["sLw"] or 0 for r in rows), 2),
            "sales_last_year": round(sum(r["sLy"] or 0 for r in rows), 2),
            "covers_current": sum(r["cCur"] or 0 for r in rows),
            "covers_last_week": sum(r["cLw"] or 0 for r in rows),
            "covers_last_year": sum(r["cLy"] or 0 for r in rows),
            "restaurants_with_sales": sum(1 for r in rows if r["sCur"] is not None),
            "restaurant_count": len(rows),
        },
    }