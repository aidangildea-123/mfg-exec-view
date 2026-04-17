from datetime import date
from fastapi import FastAPI, HTTPException
from report_core import get_access_token, build_report_payload

app = FastAPI()


@app.get("/api/report")
def get_report(report_date: str):
    try:
        target = date.fromisoformat(report_date)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD."
        )

    token = get_access_token()
    payload = build_report_payload(target, token)
    return payload