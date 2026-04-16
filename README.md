# MFG Daily Sales Report

Automatically generates a daily HTML sales dashboard from NetSuite data via GitHub Actions.

## How it works

1. GitHub Actions runs every morning at 8am ET
2. `generate_report.py` calls the Anthropic API, which queries NetSuite via MCP
3. The HTML report is written to `docs/index.html`
4. The file is committed and pushed, updating the GitHub Pages site

## Setup (one-time)

### 1. Create the repository
Create a new GitHub repo (e.g. `mfg-daily-sales`). Upload these files maintaining the folder structure:
```
.github/workflows/daily-report.yml
generate_report.py
docs/           ← create this empty folder (add a .gitkeep file inside)
README.md
```

### 2. Add your NetSuite credentials as secrets
1. Go to your repo on GitHub
2. Click **Settings → Secrets and variables → Actions**
3. Add these 4 secrets one at a time using **New repository secret**:

| Name | Value |
|---|---|
| `NS_ACCOUNT_ID` | Your NetSuite account ID (e.g. `8781746`) |
| `NS_CONSUMER_KEY` | Consumer key from your NetSuite Integration record |
| `NS_CERTIFICATE_ID` | Certificate ID from your NetSuite Integration |
| `NS_PRIVATE_KEY` | Full PEM private key (include the `-----BEGIN...` and `-----END...` lines) |

> **Note on the private key**: When pasting a multi-line PEM key into a GitHub Secret, paste it exactly as-is including all line breaks. GitHub handles multi-line secrets correctly.

### 3. Enable GitHub Pages
1. Go to **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main`, Folder: `/docs`
4. Click **Save**

Your dashboard will be live at:
`https://YOUR-USERNAME.github.io/REPO-NAME/`

### 4. Test it manually
1. Go to **Actions** tab in your repo
2. Click **Daily MFG Sales Report**
3. Click **Run workflow → Run workflow**
4. Watch it run — should take ~2 minutes
5. Check your Pages URL when it completes

## Schedule
Runs daily at **8:00 AM ET** (13:00 UTC). To change the time, edit the cron line in `.github/workflows/daily-report.yml`:
```yaml
- cron: '0 13 * * *'   # 13:00 UTC = 8am ET (9am ET during daylight saving)
```
Use https://crontab.guru to calculate the right UTC time for your timezone.

## Notes
- **London** is converted at spot GBP rate from NetSuite's currency table
- **YoY** compares to the same day of week 52 weeks prior
- **Pending approval** journal entries are excluded (matches NetSuite income statement)
- The report always shows **yesterday's** data
