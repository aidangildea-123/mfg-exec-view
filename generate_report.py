#!/usr/bin/env python3
"""
MFG Daily Sales Report Generator
CLI wrapper for generating either:
- static HTML reports in docs/
- JSON payload output for future API use
"""

import os
import sys
import json
from datetime import date, timedelta

from report_core import (
    OUTPUT_DIR,
    REGION_ORDER,
    REGION_ACCENT,
    REGION_BG,
    REGION_BORDER,
    get_access_token,
    build_report_payload,
    fmt,
    fmtC,
    pct,
    fmtP,
    pc,
    badge,
)


# ── HTML generation ────────────────────────────────────────────────────────────
def data_row(label, cur, lw, ly, name, accent, is_first):
    p1, p2 = pct(cur, lw), pct(cur, ly)
    fv = fmt if is_first else fmtC
    nm = (
        f'<div style="font-size:13px;font-weight:600;color:#111827;line-height:1.3;margin-bottom:2px">{name}</div>'
        if (is_first and name) else ""
    )
    lc = accent if is_first else "#9ca3af"
    cs = "font-size:13px;font-weight:700;color:#111827" if is_first else "font-size:12px;font-weight:600;color:#374151"
    bt = "border-top:1px solid #f3f4f6;" if is_first else ""
    pad = "padding:8px 16px 3px" if is_first else "padding:3px 16px 8px"
    return (
        f'<div style="display:flex;align-items:center;{pad};{bt}background:#fff">'
        f'<div style="width:40%;padding-right:8px">{nm}<div style="font-size:9px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:{lc}">{label}</div></div>'
        f'<div style="flex:2;text-align:right;font-variant-numeric:tabular-nums;{cs}">{fv(cur)}</div>'
        f'<div style="flex:1;text-align:right;font-size:11px;font-weight:600;color:{pc(p1)}">{fmtP(p1)}</div>'
        f'<div style="flex:1;text-align:right;font-size:11px;font-weight:600;color:{pc(p2)}">{fmtP(p2)}</div></div>'
    )


def region_block(region, rrows):
    ac = REGION_ACCENT[region]
    bg = REGION_BG[region]
    bd = REGION_BORDER[region]
    is_parm = (region == "Parm")

    tSC = sum(r["sCur"] or 0 for r in rrows)
    tSW = sum(r["sLw"] or 0 for r in rrows)
    tSY = sum(r["sLy"] or 0 for r in rrows)
    tCC = sum(r["cCur"] or 0 for r in rrows)
    tCW = sum(r["cLw"] or 0 for r in rrows)
    tCY = sum(r["cLy"] or 0 for r in rrows)
    p1, p2, p3, p4 = pct(tSC, tSW), pct(tSC, tSY), pct(tCC, tCW), pct(tCC, tCY)

    locs = ""
    for i, r in enumerate(rrows):
        sep = ' style="border-top:1px solid #f3f4f6"' if i > 0 else ""
        safe = r["name"].replace(" ", "-").replace("/", "-").replace("'", "")
        covers_row = "" if is_parm else data_row("Covers", r["cCur"], r["cLw"], r["cLy"], r["name"], ac, False)
        locs += f'<div id="loc-{safe}"{sep}>{data_row("Sales", r["sCur"], r["sLw"], r["sLy"], r["name"], ac, True)}{covers_row}</div>'

    covers_header = "" if is_parm else (
        f'<div style="display:flex;align-items:center;padding:3px 16px 8px 0">'
        f'<div style="width:40%"><div style="font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#9ca3af">Covers</div></div>'
        f'<div style="flex:2;text-align:right;font-size:12px;font-weight:600;color:#374151;font-variant-numeric:tabular-nums">{fmtC(tCC)}</div>'
        f'<div style="flex:1;text-align:right;font-size:11px;font-weight:600;color:{pc(p3)}">{fmtP(p3)}</div>'
        f'<div style="flex:1;text-align:right;font-size:11px;font-weight:600;color:{pc(p4)}">{fmtP(p4)}</div></div>'
    )

    return (
        f'<div style="margin:16px 12px 0;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06)">'
        f'<div style="background:{bg};border-bottom:1px solid {bd};padding:10px 0 10px 16px">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px"><div style="width:3px;height:14px;border-radius:2px;background:{ac}"></div>'
        f'<span style="font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:{ac}">{region}</span></div>'
        f'<div style="display:flex;align-items:center;padding:8px 16px 3px 0">'
        f'<div style="width:40%"><div style="font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{ac}">Sales</div></div>'
        f'<div style="flex:2;text-align:right;font-size:13px;font-weight:700;color:#111827;font-variant-numeric:tabular-nums">{fmt(tSC)}</div>'
        f'<div style="flex:1;text-align:right;font-size:11px;font-weight:600;color:{pc(p1)}">{fmtP(p1)}</div>'
        f'<div style="flex:1;text-align:right;font-size:11px;font-weight:600;color:{pc(p2)}">{fmtP(p2)}</div></div>'
        f'{covers_header}</div>'
        f'<div style="display:flex;padding:5px 16px;background:#f9fafb;border-bottom:1px solid #e5e7eb;border-top:1px solid #e5e7eb">'
        f'<div style="width:40%;font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#9ca3af">Location</div>'
        f'<div style="flex:2;text-align:right;font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#9ca3af">Current</div>'
        f'<div style="flex:1;text-align:right;font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#9ca3af">WoW</div>'
        f'<div style="flex:1;text-align:right;font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#9ca3af">YoY</div></div>'
        f'<div style="background:#fff">{locs}</div></div>'
    )


def make_html(dc, dlw, dly, rows):
    mSC = sum(r["sCur"] or 0 for r in rows)
    mSW = sum(r["sLw"] or 0 for r in rows)
    mSY = sum(r["sLy"] or 0 for r in rows)
    mCC = sum(r["cCur"] or 0 for r in rows)
    mCW = sum(r["cLw"] or 0 for r in rows)
    mCY = sum(r["cLy"] or 0 for r in rows)

    jump = ""
    for reg in REGION_ORDER:
        rrows = [r for r in rows if r["region"] == reg]
        if not rrows:
            continue
        opts = "".join(
            f'<option value="loc-{r["name"].replace(" ","-").replace("/","-").replace(chr(39),"")}"> {r["name"]}</option>'
            for r in rrows
        )
        jump += f'<optgroup label="{reg}">{opts}</optgroup>'

    regions = "".join(
        region_block(reg, [r for r in rows if r["region"] == reg])
        for reg in REGION_ORDER if any(r["region"] == reg for r in rows)
    )

    return (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">'
        f'<title>MFG Daily Snapshot — {dc}</title>'
        f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,600;9..40,700&display=swap">'
        f'<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:"DM Sans","Helvetica Neue",Helvetica,sans-serif;background:#f4f5f7;padding-bottom:48px;color:#111827}}</style>'
        f'</head><body>'
        f'<div style="background:#fff;border-bottom:1px solid #e5e7eb;padding:14px 16px 12px">'
        f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:4px">'
        f'<div style="font-size:22px;font-weight:700;color:#111827;letter-spacing:-.03em">Daily Snapshot</div>'
        f'<span style="font-size:12px;font-weight:600;padding:3px 10px;border-radius:20px;background:#f3f4f6;color:#374151;letter-spacing:0.02em">{dc}</span>'
        f'</div>'
        f'<div style="font-size:11px;color:#9ca3af">WoW vs {dlw} &nbsp;&middot;&nbsp; YoY vs {dly}</div>'
        f'<div style="margin-top:10px">'
        f'<a href="index.html" style="display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:600;color:#374151;text-decoration:none;padding:5px 12px;border:1px solid #e5e7eb;border-radius:6px;background:#fff">'
        f'&larr; All Reports</a>'
        f'</div></div>'
        f'<div style="background:#fff;border-bottom:1px solid #e5e7eb;padding:10px 16px">'
        f'<select onchange="document.getElementById(this.value)?.scrollIntoView({{behavior:\'smooth\',block:\'center\'}})" style="padding:7px 10px;font-size:12px;border:1px solid #d1d5db;border-radius:6px;background:#fff;color:#374151;font-family:inherit;width:100%">'
        f'<option value="">Jump to location…</option>{jump}</select></div>'
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
        f'</body></html>'
    )


# ── Index builder ──────────────────────────────────────────────────────────────
def build_index():
    """Scan docs/ for dated HTML files and build a grouped collapsible index page."""
    from collections import defaultdict

    files = sorted(
        [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".html") and f != "index.html"],
        reverse=True
    )
    if not files:
        return

    months = defaultdict(list)
    latest_date, latest_file = None, None
    for f in files:
        d = f.replace(".html", "")
        try:
            parsed = date.fromisoformat(d)
        except Exception:
            continue
        months[parsed.strftime("%Y-%m")].append((parsed, f))
        if latest_date is None or parsed > latest_date:
            latest_date = parsed
            latest_file = f

    latest_label = latest_date.strftime("%A, %B %-d, %Y") if latest_date else ""
    latest_card = (
        f'<a href="{latest_file}" style="display:flex;align-items:center;justify-content:space-between;'
        f'padding:16px 20px;background:#111827;border-radius:10px;margin-bottom:20px;'
        f'text-decoration:none;color:#fff;">'
        f'<div>'
        f'<div style="font-size:10px;letter-spacing:0.14em;text-transform:uppercase;color:#9ca3af;margin-bottom:3px">Latest Report</div>'
        f'<div style="font-size:16px;font-weight:700">{latest_label}</div>'
        f'</div>'
        f'<span style="font-size:20px;color:#9ca3af">&rsaquo;</span>'
        f'</a>'
    )

    sorted_months = sorted(months.keys(), reverse=True)
    sections = ""
    for i, mk in enumerate(sorted_months):
        month_label = date.fromisoformat(mk + "-01").strftime("%B %Y")
        entries = sorted(months[mk], reverse=True)
        open_attr = "open" if i == 0 else ""
        rows = ""
        for parsed, f in entries:
            day_label = parsed.strftime("%A, %-d %B %Y")
            rows += (
                f'<a href="{f}" style="display:flex;align-items:center;justify-content:space-between;'
                f'padding:12px 16px;background:#fff;border-radius:6px;margin-bottom:6px;'
                f'text-decoration:none;color:#111827;box-shadow:0 1px 2px rgba(0,0,0,0.05);">'
                f'<span style="font-size:13px;font-weight:500">{day_label}</span>'
                f'<span style="font-size:12px;color:#9ca3af">&rsaquo;</span>'
                f'</a>'
            )
        sections += (
            f'<details {open_attr} style="margin-bottom:10px;">'
            f'<summary style="cursor:pointer;list-style:none;padding:12px 16px;background:#fff;'
            f'border-radius:8px;font-size:13px;font-weight:700;color:#374151;'
            f'box-shadow:0 1px 3px rgba(0,0,0,0.06);display:flex;align-items:center;justify-content:space-between;">'
            f'<span>{month_label}</span>'
            f'<span style="font-size:11px;color:#9ca3af;font-weight:400">{len(entries)} report{"s" if len(entries)!=1 else ""}</span>'
            f'</summary>'
            f'<div style="padding:8px 0 4px">{rows}</div>'
            f'</details>'
        )

    total = sum(len(v) for v in months.values())
    index_html = (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        f'<title>MFG Daily Snapshot</title>'
        f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&display=swap">'
        f'<style>'
        f'*{{box-sizing:border-box;margin:0;padding:0}}'
        f'body{{font-family:"DM Sans","Helvetica Neue",sans-serif;background:#f4f5f7;min-height:100vh;padding-bottom:48px;color:#111827}}'
        f'details summary::-webkit-details-marker{{display:none}}'
        f'details[open] summary{{border-radius:8px 8px 0 0}}'
        f'details[open]>div{{background:#f9fafb;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px;padding:10px 10px 6px}}'
        f'a:hover{{opacity:0.85}}'
        f'</style></head><body>'
        f'<div style="background:#fff;border-bottom:1px solid #e5e7eb;padding:20px 16px 16px">'
        f'<div style="font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:#9ca3af;margin-bottom:3px">Major Food Group</div>'
        f'<div style="font-size:24px;font-weight:700;letter-spacing:-0.02em">Daily Snapshot</div>'
        f'<div style="font-size:11px;color:#9ca3af;margin-top:3px">{total} report{"s" if total!=1 else ""} available</div>'
        f'</div>'
        f'<div style="padding:16px">{latest_card}{sections}</div>'
        f'</body></html>'
    )

    with open(os.path.join(OUTPUT_DIR, "index.html"), "w") as f:
        f.write(index_html)
    print(f"Index updated — {total} reports across {len(sorted_months)} month(s)")


def render_report_html(payload: dict) -> str:
    return make_html(
        payload["report_date"],
        payload["wow_date"],
        payload["yoy_date"],
        payload["rows"],
    )


# ── Main ───────────────────────────────────────────────────────────────────────
def build_data_index():
    data_dir = os.path.join(OUTPUT_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)

    dates = []
    for f in os.listdir(data_dir):
        if not f.endswith(".json") or f == "index.json":
            continue

        d = f[:-5]  # strip ".json"
        try:
            date.fromisoformat(d)
            dates.append(d)
        except ValueError:
            continue

    dates = sorted(dates, reverse=True)

    manifest = {
        "latest": dates[0] if dates else None,
        "dates": dates,
    }

    index_path = os.path.join(data_dir, "index.json")
    with open(index_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Data index updated with {len(dates)} date(s)")



if __name__ == "__main__":
    args = [a.strip() for a in sys.argv[1:] if a.strip()]

    target = date.today() - timedelta(days=1)
    output_format = "html"

    for arg in args:
        if arg == "--json":
            output_format = "json"
        else:
            target = date.fromisoformat(arg)

    print(f"Mode: {output_format.upper()} | Date: {target}")
    print(
        f"Generating report for {target.isoformat()} "
        f"(WoW: {(target - timedelta(weeks=1)).isoformat()}, "
        f"YoY: {(target - timedelta(weeks=52)).isoformat()})"
    )

    print("Authenticating with NetSuite...")
    token = get_access_token()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    payload = build_report_payload(target, token)

if output_format == "json":
    data_dir = os.path.join(OUTPUT_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)

    json_path = os.path.join(data_dir, f"{payload['report_date']}.json")
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"JSON written to {json_path}")
    build_data_index()

else:
    html = render_report_html(payload)

    report_path = os.path.join(OUTPUT_DIR, f"{payload['report_date']}.html")
    with open(report_path, "w") as f:
        f.write(html)
    print(f"Report written to {report_path}")

    build_index()
    print(f"Done. MFG Sales: {fmt(payload['summary']['sales_current'])}")
    print(
        f"Restaurants with data: "
        f"{payload['summary']['restaurants_with_sales']}/"
        f"{payload['summary']['restaurant_count']}"
    )