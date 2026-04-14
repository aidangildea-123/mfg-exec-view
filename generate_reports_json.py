import os
import json
import re
from datetime import datetime

REPORTS_DIR = "reports"
OUTPUT_FILE = "reports.json"

def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

def filename_to_label(filename: str) -> str:
    name = os.path.splitext(filename)[0]

    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})$", name)
    if not match:
        return name

    month, day, year = match.groups()
    month = int(month)
    day = int(day)
    year = int(year)

    if year < 100:
        year += 2000

    dt = datetime(year, month, day)
    return dt.strftime("%A %B ") + ordinal(day) + dt.strftime(", %Y")

def main():
    if not os.path.exists(REPORTS_DIR):
        print(f"Folder not found: {REPORTS_DIR}")
        return

    files = [
        f for f in os.listdir(REPORTS_DIR)
        if f.lower().endswith(".html")
    ]

    def sort_key(filename: str):
        name = os.path.splitext(filename)[0]
        match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})$", name)
        if match:
            month, day, year = match.groups()
            month = int(month)
            day = int(day)
            year = int(year)
            if year < 100:
                year += 2000
            return datetime(year, month, day)
        return datetime.min

    files.sort(key=sort_key)

    reports = []
    for filename in files:
        reports.append({
            "label": filename_to_label(filename),
            "file": filename
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2)

    print(f"Generated {OUTPUT_FILE} with {len(reports)} report(s).")

if __name__ == "__main__":
    main()
