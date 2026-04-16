#!/usr/bin/env python3
"""
MFG Daily Sales Report Generator
Authenticates directly with NetSuite via OAuth 2.0 JWT (PS256),
runs SuiteQL queries, and writes a static HTML report to docs/index.html.
No Anthropic API required — completely free to run.
"""

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

    # GitHub Secrets sometimes stores newlines as literal \n — fix that here
    pem = NS_PRIVATE_KEY_PEM.replace("\\n", "\n").strip()
    if not pem.startswith("-----"):
        raise ValueError("NS_PRIVATE_KEY does not look like a valid PEM key. Check the secret value.")
    private_key = serialization.load_pem_private_key(
        pem.encode(), password=None, backend=default_backend()
    )
    sig = private_key.sign(
        signing_input,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),  # saltLen = hLen per jsrsasign default
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
    if not raw: return ""
    if len(raw) == 10 and raw[4] == "-": return raw
    m, d, y = raw.split("/")
    return f"{y}-{m.zfill(2)}-{d.zfill(2)}"

def sql_dates(*ds):
    return ", ".join(f"TO_DATE('{d}','YYYY-MM-DD')" for d in ds)


# ── Data fetching ──────────────────────────────────────────────────────────────
def fetch_all(dc, dlw, dly, token):
    d_sql = sql_dates(dc, dlw, dly)

    print("  [1/4] FX rates...")
    fx = {}
    for r in run_sql(f"SELECT cr.effectiveDate, cr.transactionCurrency AS currency, cr.exchangeRate FROM currencyrate cr WHERE cr.effectiveDate IN ({d_sql}) ORDER BY cr.effectiveDate", token):
        dk  = norm(r.get("effectivedate", ""))
        cid = int(r.get("currency", 1))
        fx[f"{dk}|{cid}"] = float(r.get("exchangerate", 1))
    def gfx(dk, cid): return 1.0 if cid == 1 else fx.get(f"{dk}|{cid}", 1.0)

    print("  [2/4] Sales...")
    sub = {}
    for r in run_sql(
        f"SELECT t.trandate, t.subsidiary, t.currency, SUM(tl.foreignamount)*-1 AS net_sales "
        f"FROM transactionline tl JOIN transaction t ON t.id=tl.transaction JOIN account a ON a.id=tl.account "
        f"WHERE t.subsidiary IN ({IN_NON_DAL}) AND t.trandate IN ({d_sql}) "
        f"AND t.type IN ('Journal','CustInvc') AND a.accttype='Income' "
        f"AND (t.approvalstatus=2 OR t.approvalstatus IS NULL) "
        f"GROUP BY t.trandate, t.subsidiary, t.currency", token):
        sid = int(r["subsidiary"]); dk = norm(r["trandate"]); cid = int(r.get("currency", 1))
        sub.setdefault(sid, {})[dk] = round(float(r.get("net_sales") or 0) * gfx(dk, cid), 2)

    print("  [3/4] Dallas class split...")
    dal = {}
    for r in run_sql(
        f"SELECT t.trandate, tl.class, SUM(tl.foreignamount)*-1 AS net_sales "
        f"FROM transactionline tl JOIN transaction t ON t.id=tl.transaction JOIN account a ON a.id=tl.account "
        f"WHERE t.subsidiary=28 AND t.trandate IN ({d_sql}) "
        f"AND t.type IN ('Journal','CustInvc') AND a.accttype='Income' "
        f"AND (t.approvalstatus=2 OR t.approvalstatus IS NULL) "
        f"GROUP BY t.trandate, tl.class", token):
        dk = norm(r["trandate"]); cls = r.get("class"); v = float(r.get("net_sales") or 0)
        dal.setdefault(dk, {"c": 0, "v": 0, "ok": False})
        if cls is not None:
            dal[dk]["ok"] = True
            if int(cls) in VINO: dal[dk]["v"] += v
            else:                dal[dk]["c"] += v

    print("  [4/4] Covers...")
    cm = {}
    for r in run_sql(
        f"SELECT sje.trandate, sje.subsidiary, sjel.class, SUM(sjel.debit) AS cover_count "
        f"FROM statisticaljournalentryline sjel JOIN statisticaljournalentry sje ON sje.id=sjel.journal "
        f"WHERE sjel.account=2671 AND sje.subsidiary IN ({IN_ALL}) AND sje.trandate IN ({d_sql}) "
        f"GROUP BY sje.trandate, sje.subsidiary, sjel.class", token):
        k = (int(r["subsidiary"]), norm(r["trandate"]), int(r.get("class", 0)))
        cm[k] = cm.get(k, 0) + float(r.get("cover_count") or 0)

    return sub, dal, cm


# ── Row builder ────────────────────────────────────────────────────────────────
def build_rows(sub, dal, cm, dc, dlw, dly):
    rows = []
    for r in RESTAURANTS:
        if r["dallas"]:
            def gs(dk, dt=r["dType"]):
                d = dal.get(dk, {}); return (d["v"] if dt == "vino" else d["c"]) if d.get("ok") else None
            sc, sw, sy = gs(dc), gs(dlw), gs(dly)
        else:
            def ss(dk, ids=r["ids"]):
                t = sum(sub.get(i, {}).get(dk, 0) for i in ids)
                return t if any(sub.get(i, {}).get(dk) is not None for i in ids) else None
            sc, sw, sy = ss(dc), ss(dlw), ss(dly)
        def gc(dk, ids=r["ids"], cc=r["cc"]):
            t = sum(cm.get((i, dk, c), 0) for i in ids for c in cc); return t or None
        rows.append({"name": r["name"], "region": r["region"], "sCur": sc, "sLw": sw, "sLy": sy,
                     "cCur": gc(dc), "cLw": gc(dlw), "cLy": gc(dly)})
    return rows


# ── Formatters ─────────────────────────────────────────────────────────────────
def fmt(n):  return "\u2014" if n is None else "$" + f"{round(abs(n)):,}"
def fmtC(n): return "\u2014" if n is None else f"{int(n):,}"
def pct(c, p):
    if c is None or p is None: return None
    if p == 0 and c == 0: return 0
    if p == 0: return None
    return (c - p) / p
def fmtP(p):
    if p is None: return "\u2014"
    if p == 0: return "0%"
    return f"+{p*100:.0f}%" if p > 0 else f"({abs(p*100):.0f}%)"
def pc(p): return "#9ca3af" if p is None else "#15803d" if p >= 0 else "#b91c1c"


# ── HTML generation ────────────────────────────────────────────────────────────
def badge(p, label):
    if p is None: return ""
    pos = p >= 0; bg = "#dcfce7" if pos else "#fee2e2"; col = "#15803d" if pos else "#b91c1c"; bdr = "#bbf7d0" if pos else "#fecaca"
    return (f'<span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;background:{bg};color:{col};border:1px solid {bdr};display:inline-block;margin-right:4px">{fmtP(p)} {label}</span>')

def data_row(label, cur, lw, ly, name, accent, is_first):
    p1, p2 = pct(cur, lw), pct(cur, ly); fv = fmt if is_first else fmtC
    nm  = f'<div style="font-size:13px;font-weight:600;color:#111827;line-height:1.3;margin-bottom:2px">{name}</div>' if (is_first and name) else ""
    lc  = accent if is_first else "#9ca3af"
    cs  = "font-size:13px;font-weight:700;color:#111827" if is_first else "font-size:12px;font-weight:600;color:#374151"
    bt  = "border-top:1px solid #f3f4f6;" if is_first else ""
    pad = "padding:8px 16px 3px" if is_first else "padding:3px 16px 8px"
    return (f'<div style="display:flex;align-items:center;{pad};{bt}background:#fff">'
            f'<div style="width:40%;padding-right:8px">{nm}<div style="font-size:9px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:{lc}">{label}</div></div>'
            f'<div style="flex:2;text-align:right;font-variant-numeric:tabular-nums;{cs}">{fv(cur)}</div>'
            f'<div style="flex:1;text-align:right;font-size:11px;font-weight:600;color:{pc(p1)}">{fmtP(p1)}</div>'
            f'<div style="flex:1;text-align:right;font-size:11px;font-weight:600;color:{pc(p2)}">{fmtP(p2)}</div></div>')

def region_block(region, rrows):
    ac = REGION_ACCENT[region]; bg = REGION_BG[region]; bd = REGION_BORDER[region]
    tSC=sum(r["sCur"]or 0 for r in rrows); tSW=sum(r["sLw"]or 0 for r in rrows); tSY=sum(r["sLy"]or 0 for r in rrows)
    tCC=sum(r["cCur"]or 0 for r in rrows); tCW=sum(r["cLw"]or 0 for r in rrows); tCY=sum(r["cLy"]or 0 for r in rrows)
    p1,p2,p3,p4 = pct(tSC,tSW),pct(tSC,tSY),pct(tCC,tCW),pct(tCC,tCY)
    locs = ""
    for i, r in enumerate(rrows):
        sep  = ' style="border-top:1px solid #f3f4f6"' if i > 0 else ""
        safe = r["name"].replace(" ","-").replace("/","-").replace("'","")
        locs += f'<div id="loc-{safe}"{sep}>{data_row("Sales",r["sCur"],r["sLw"],r["sLy"],r["name"],ac,True)}{data_row("Covers",r["cCur"],r["cLw"],r["cLy"],r["name"],ac,False)}</div>'
    return (f'<div style="margin:16px 12px 0;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06)">'
            f'<div style="background:{bg};border-bottom:1px solid {bd};padding:10px 0 10px 16px">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px"><div style="width:3px;height:14px;border-radius:2px;background:{ac}"></div>'
            f'<span style="font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:{ac}">{region}</span></div>'
            f'<div style="display:flex;align-items:center;padding:8px 16px 3px 0">'
            f'<div style="width:40%"><div style="font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{ac}">Sales</div></div>'
            f'<div style="flex:2;text-align:right;font-size:13px;font-weight:700;color:#111827;font-variant-numeric:tabular-nums">{fmt(tSC)}</div>'
            f'<div style="flex:1;text-align:right;font-size:11px;font-weight:600;color:{pc(p1)}">{fmtP(p1)}</div>'
            f'<div style="flex:1;text-align:right;font-size:11px;font-weight:600;color:{pc(p2)}">{fmtP(p2)}</div></div>'
            f'<div style="display:flex;align-items:center;padding:3px 16px 8px 0">'
            f'<div style="width:40%"><div style="font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#9ca3af">Covers</div></div>'
            f'<div style="flex:2;text-align:right;font-size:12px;font-weight:600;color:#374151;font-variant-numeric:tabular-nums">{fmtC(tCC)}</div>'
            f'<div style="flex:1;text-align:right;font-size:11px;font-weight:600;color:{pc(p3)}">{fmtP(p3)}</div>'
            f'<div style="flex:1;text-align:right;font-size:11px;font-weight:600;color:{pc(p4)}">{fmtP(p4)}</div></div></div>'
            f'<div style="display:flex;padding:5px 16px;background:#f9fafb;border-bottom:1px solid #e5e7eb;border-top:1px solid #e5e7eb">'
            f'<div style="width:40%;font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#9ca3af">Location</div>'
            f'<div style="flex:2;text-align:right;font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#9ca3af">Current</div>'
            f'<div style="flex:1;text-align:right;font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#9ca3af">WoW</div>'
            f'<div style="flex:1;text-align:right;font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#9ca3af">YoY</div></div>'
            f'<div style="background:#fff">{locs}</div></div>')

def make_html(dc, dlw, dly, rows):
    mSC=sum(r["sCur"]or 0 for r in rows); mSW=sum(r["sLw"]or 0 for r in rows); mSY=sum(r["sLy"]or 0 for r in rows)
    mCC=sum(r["cCur"]or 0 for r in rows); mCW=sum(r["cLw"]or 0 for r in rows); mCY=sum(r["cLy"]or 0 for r in rows)
    jump = ""
    for reg in REGION_ORDER:
        rrows = [r for r in rows if r["region"]==reg]
        if not rrows: continue
        opts = "".join(f'<option value="loc-{r["name"].replace(" ","-").replace("/","-").replace(chr(39),"")}"> {r["name"]}</option>' for r in rrows)
        jump += f'<optgroup label="{reg}">{opts}</optgroup>'
    regions = "".join(region_block(reg,[r for r in rows if r["region"]==reg]) for reg in REGION_ORDER if any(r["region"]==reg for r in rows))
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">'
            f'<title>MFG Daily Sales \u2014 {dc}</title>'
            f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,600;9..40,700&display=swap">'
            f'<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:"DM Sans","Helvetica Neue",Helvetica,sans-serif;background:#f4f5f7;padding-bottom:48px;color:#111827}}</style>'
            f'</head><body>'
            f'<div style="background:#fff;border-bottom:1px solid #e5e7eb;padding:14px 16px 12px">'
            f'<div style="font-size:22px;font-weight:700;color:#111827;letter-spacing:-.03em">Daily Sales</div>'
            f'<div style="font-size:11px;color:#9ca3af;margin-top:3px">{dc} &nbsp;&middot;&nbsp; WoW vs {dlw} &nbsp;&middot;&nbsp; YoY vs {dly}</div></div>'
            f'<div style="background:#fff;border-bottom:1px solid #e5e7eb;padding:10px 16px">'
            f'<select onchange="document.getElementById(this.value)?.scrollIntoView({{behavior:\'smooth\',block:\'center\'}})" style="padding:7px 10px;font-size:12px;border:1px solid #d1d5db;border-radius:6px;background:#fff;color:#374151;font-family:inherit;width:100%">'
            f'<option value="">Jump to location\u2026</option>{jump}</select></div>'
            f'<div style="background:#fff;border-bottom:1px solid #e5e7eb;padding:16px">'
            f'<div style="font-size:9px;letter-spacing:.2em;text-transform:uppercase;color:#9ca3af;margin-bottom:12px">MFG Total &nbsp;&middot;&nbsp; {dc}</div>'
            f'<div style="display:flex;gap:32px;flex-wrap:wrap">'
            f'<div><div style="font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:#9ca3af;margin-bottom:4px">Sales</div>'
            f'<div style="font-size:26px;font-weight:700;color:#111827;letter-spacing:-.03em;line-height:1;margin-bottom:8px;font-variant-numeric:tabular-nums">{fmt(mSC)}</div>'
            f'{badge(pct(mSC,mSW),"WoW")}{badge(pct(mSC,mSY),"YoY")}</div>'
            f'<div style="width:1px;background:#e5e7eb;align-self:stretch"></div>'
            f'<div><div style="font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:#9ca3af;margin-bottom:4px">Covers</div>'
            f'<div style="font-size:26px;font-weight:700;color:#111827;letter-spacing:-.03em;line-height:1;margin-bottom:8px;font-variant-numeric:tabular-nums">{fmtC(mCC)}</div>'
            f'{badge(pct(mCC,mCW),"WoW")}{badge(pct(mCC,mCY),"YoY")}</div></div></div>'
            f'{regions}'
            f'<div style="padding:16px;text-align:center;font-size:10px;color:#d1d5db">London at spot GBP rate &nbsp;&middot;&nbsp; YoY = same weekday prior year (52 wks) &nbsp;&middot;&nbsp; {dc}</div>'
            f'</body></html>')


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    target = date.today() - timedelta(days=1)
    dc  = target.isoformat()
    dlw = (target - timedelta(weeks=1)).isoformat()
    dly = (target - timedelta(weeks=52)).isoformat()

    print(f"Generating report for {dc} (WoW: {dlw}, YoY: {dly})")
    print("Authenticating with NetSuite...")
    token = get_access_token()

    sub, dal, cm = fetch_all(dc, dlw, dly, token)
    rows = build_rows(sub, dal, cm, dc, dlw, dly)
    html = make_html(dc, dlw, dly, rows)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w") as f:
        f.write(html)

    print(f"Done. MFG Sales: {fmt(sum(r['sCur'] or 0 for r in rows))}")
    print(f"Restaurants with data: {sum(1 for r in rows if r['sCur'] is not None)}/25")
