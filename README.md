# Syntec Internship — Week 1 Projects

A collection of nine projects built during Week 1, ranging from Python CLI tools
and Streamlit web apps to a Node.js backend service and a full Android application.

---

## Quick-start index

| # | Project | Stack | Type |
|---|---------|-------|------|
| 1 | [house_price_predictor](#1-house_price_predictor) | Python · Streamlit · scikit-learn · SHAP | ML web app |
| 2 | [port_scanner](#2-port_scanner) | Python · asyncio · Rich TUI | Security tool |
| 3 | [data_analyst](#3-data_analyst) | Python · Streamlit · Pandas · Plotly | Analytics web app |
| 4 | [expert_system](#4-expert_system) | Python · Streamlit · MYCIN rules | AI web app |
| 5 | [file_upload_system](#5-file_upload_system) | Node.js · Express · MongoDB · Sharp | REST API + frontend |
| 6 | [clock_app](#6-clock_app) | Kotlin · Android · Canvas | Mobile app |
| 7 | [student_dashboard](#7-student_dashboard) | Python · Streamlit | Analytics web app |
| 8 | [billing_system](#8-billing_system) | Python · CLI | CLI tool |
| 9 | [calculator](#9-calculator) | Python · CLI | CLI tool |
| 10 | [todo](#10-todo) | Python · SQLite · CLI | CLI tool |
| 11 | [number_guessing](#11-number_guessing) | Python · CLI | CLI game |
| 12 | [notes_app](#12-notes_app) | HTML · CSS · JS | Static web app |
| 13 | [landing_page / portfolio](#13-landing_page--portfolio) | HTML · CSS · JS | Static web pages |

---

## 1. house_price_predictor

**What it does:**
A full-featured machine-learning web app for housing price prediction.
Upload any housing dataset (CSV, JSON, or Excel), map columns to roles,
and instantly get automated EDA, a five-model comparison (Linear Regression,
Ridge, Lasso, Random Forest, Gradient Boosting), SHAP-based explainability
(per-prediction waterfall charts), an interactive what-if predictor with sliders,
geographic map visualisation (if lat/lon columns exist), and a one-click
auto-generated plain-language report you can download.

**Install & run:**
```bash
cd house_price_predictor
pip install -r requirements.txt
pip install shap          # required for the Explainability tab
streamlit run app.py
```

**requirements.txt includes:**
- `streamlit` — web UI framework
- `pandas`, `numpy` — data manipulation
- `scikit-learn` — all five ML models + preprocessing pipelines
- `plotly` — interactive charts (histograms, heatmaps, maps, residual plots)
- `joblib` — saving and loading trained models to disk
- `scipy` — statistical utilities
- `openpyxl`, `xlrd` — Excel file support
- `shap` (separate install) — SHAP explainability values for all model types

---

## 2. port_scanner

**What it does:**
A defensive network vulnerability assessment tool with a Rich terminal UI.
Scan a single host, comma-separated list, or CIDR range (e.g. 192.168.1.0/24)
for open ports using a fully async engine (asyncio + Semaphore for concurrency).
For each open port, grabs the service banner, looks up risk information from a
local 48-port vulnerability database, and optionally queries the NVD (National
Vulnerability Database) API for live CVE data with CVSS scores.
Results are displayed in an interactive drill-down menu (host → port → full detail
with risks and remediation steps). Scan history is stored in SQLite, and any
two past scans can be diffed to track newly opened or closed ports over time.
Reports export as JSON, CSV, and Markdown.

**Run interactively (recommended):**
```bash
cd port_scanner
pip install -r requirements.txt
python main.py               # launches the interactive menu
```

**Or use CLI mode for scripting:**
```bash
python main.py scan 192.168.1.1                            # quick scan (top 100 ports)
python main.py scan 10.0.0.0/24 --profile full --format all  # full scan with reports
python main.py scan example.com --profile stealth          # slow, randomised, IDS-aware
python main.py history                                     # list past scans
python main.py diff 1 2                                    # compare scan #1 vs #2
python main.py profiles                                    # show all scan profiles
```

**Available profiles:** `quick` · `full` · `stealth` · `security` · `web` · `db`

**requirements.txt includes:**
- `rich` — coloured tables, progress bars, and the interactive TUI dashboard
- `requests` — NVD API HTTP calls (optional; scanner degrades gracefully without network)

> **Important:** Only scan systems you own or have explicit written permission to scan.

---

## 3. data_analyst

**What it does:**
A self-service data analysis web app — upload any CSV or Excel file and
immediately get an interactive exploration experience with no code required.
Features: auto column profiling (types, missing %, unique counts, distributions),
an AND/OR filter builder with live before/after comparison, an auto-suggested
chart gallery (histogram, scatter, box, heatmap, parallel coordinates, etc.),
a natural-language query engine ("average price by category", "top 10 by revenue",
"filter where age > 30"), a two-file side-by-side comparison tab,
and full export with a timestamped audit log of every operation.

**Install & run:**
```bash
cd data_analyst
pip install -r requirements.txt
streamlit run app.py
```

**requirements.txt includes:**
- `streamlit` — web UI framework
- `pandas`, `numpy` — data loading and transformation
- `plotly` — all interactive charts
- `openpyxl`, `xlrd` — Excel file reading/writing

---

## 4. expert_system

**What it does:**
A MYCIN-style cybersecurity expert system that diagnoses threats and
vulnerabilities from observable symptoms. Enter symptoms manually or as
plain English (e.g. "slow network and unusual outbound traffic") and the
engine runs forward and backward chaining over 26 rules with certainty
factors (CF algebra). The six-tab Streamlit UI shows diagnosed threats
with confidence scores, a reasoning graph (Plotly + networkx showing
which facts triggered which rules), a natural-language explanation of
the reasoning chain, a browsable knowledge base, and a self-learning
tab where user feedback incrementally adjusts rule certainty weights.

**Install & run:**
```bash
cd expert_system
pip install -r requirements.txt
streamlit run app.py
```

**requirements.txt includes:**
- `streamlit` — web UI
- `plotly`, `networkx` — interactive reasoning graph visualisation
- `pandas`, `numpy` — data handling

---

## 5. file_upload_system

**What it does:**
A production-grade image upload service built with Node.js, Express, and MongoDB.
Key features: chunked upload protocol (1 MB chunks: /init → /chunk → /complete)
so large files never time out; magic-byte file validation (rejects files that lie
about their extension); SHA-256 content deduplication (identical images are stored
once); a Sharp image processing pipeline that produces thumbnail (200 px),
medium (800 px), and full-size WebP variants; HMAC-SHA256 time-limited signed URLs
(like AWS S3 presigned URLs); WebSocket real-time progress events per upload;
zero-API colour analysis (48×48 pixel sampling for dominant colour and brightness
tags); soft delete and restore; and per-user rate limiting and storage quotas.
The frontend is a single vanilla HTML/JS page with drag-and-drop, a live progress
bar, a gallery with lightbox, and a trash/restore tab.

**Prerequisites:** Node.js ≥ 18, MongoDB running locally on port 27017

**Install & run:**
```bash
cd file_upload_system
npm install               # installs Express, Mongoose, Sharp, multer, ws, etc.
npm start                 # production:  node server/index.js
# or
npm run dev               # development: nodemon server/index.js (auto-restarts)
```

Then open `http://localhost:3000` in your browser.

**Key npm packages:**
- `express` — HTTP server and routing
- `mongoose` — MongoDB ODM for storing file metadata
- `sharp` — high-performance image resizing and WebP conversion
- `multer` — multipart/form-data parsing for chunk uploads
- `ws` — WebSocket server for real-time progress events
- `express-rate-limit` — per-IP rate limiting

---

## 6. clock_app

**What it does:**
A full-featured Android clock app written in Kotlin with five screens:
flip-digit clock (slot-machine scroll animation), smooth analog clock
(Canvas with sub-millisecond second-hand interpolation), world clock
(10 cities, per-second updates, day-offset indicator), Pomodoro timer
(drift-free with SystemClock.elapsedRealtime, progress ring, TextToSpeech),
and stopwatch with lap tracking. Additional features: time-of-day adaptive
theming (4 phases: morning/afternoon/evening/night with 3-second ArgbEvaluator
crossfade), home screen widget (AlarmManager exact-alarm updates every minute),
and astronomical sunrise/sunset calculation (pure NOAA math, no library).

**Requirements:** Android Studio, Android SDK 24+, Kotlin

**Open & run:**
```
1. Open Android Studio
2. File → Open → select the clock_app/ folder
3. Let Gradle sync complete
4. Run on an emulator or physical device (API 24+)
```

**No additional dependencies to install** — all dependencies are declared in
`app/build.gradle` and downloaded automatically by Gradle on first sync.

---

## 7. student_dashboard

**What it does:**
A Streamlit dashboard for visualising and analysing student performance data.
Upload a student dataset and get instant charts for grade distributions,
attendance trends, subject comparisons, and performance correlations.

**Install & run:**
```bash
cd student_dashboard
pip install -r requirements.txt
streamlit run app.py
```

---

## 8. billing_system

**What it does:**
A Python CLI billing and invoice management tool. Create clients, add line items,
generate invoices with totals and tax, and track payment status — all from the
terminal. Data is stored as JSON files in the `data/` directory.

**Install & run:**
```bash
cd billing_system
python billing.py --help          # show all commands
python billing.py add-client      # add a new client
python billing.py new-invoice     # create an invoice
python billing.py list-invoices   # list all invoices
```

**No external dependencies** — uses Python standard library only.

---

## 9. calculator

**What it does:**
A scientific calculator with a safe AST-based expression evaluator (no `eval()`),
operator precedence, scientific functions (sin/cos/tan/sqrt/log/factorial),
constants (π, e, τ), memory (MS/MR/M+/M-/MC), calculation history with
JSON/CSV export, and an `ans` keyword for chaining results.

**Install & run:**
```bash
cd calculator

# Interactive REPL mode
python calculator.py

# Single expression (CLI)
python calculator.py "sin(pi/2) + sqrt(16)"

# Run built-in tests
python calculator.py --test
```

**No external dependencies** — uses Python standard library only.

---

## 10. todo

**What it does:**
A terminal to-do manager backed by SQLite. Supports priorities (high/medium/low)
with colour-coded output, due dates, tags, recurring tasks (auto-creates the next
occurrence on completion), and overdue tracking.

**Install & run:**
```bash
cd todo
python todo.py add "Buy groceries" --due tomorrow --priority high --tags shopping
python todo.py list
python todo.py done 1
python todo.py overdue
python todo.py --help        # full command reference
```

**No external dependencies** — uses Python standard library + sqlite3 only.

---

## 11. number_guessing

**What it does:**
A terminal number-guessing game with four difficulty levels (Easy 1–50 / Medium 1–100
/ Hard 1–200 / Extreme 1–500 with limited guesses), a persistent JSON leaderboard
tracking best scores and win rates per player, and a computer-guesses mode that
demonstrates binary search (O(log n) strategy).

**Install & run:**
```bash
cd number_guessing
python game.py                               # default: medium difficulty
python game.py --difficulty hard --name Umut
python game.py --computer-guess             # watch binary search in action
python game.py --leaderboard                # show all-time scores
```

**No external dependencies** — uses Python standard library only.

---

## 12. notes_app

**What it does:**
A browser-based notes app — a single HTML file with no backend required.
Create, edit, delete, and search notes that are saved to the browser's
localStorage, so they persist across sessions without any server.

**Install & run:**
```bash
cd notes_app
open index.html          # macOS
# or simply double-click index.html in Finder
```

**No installation needed** — runs entirely in the browser.

---

## 13. landing_page / portfolio

**What it does:**
Static HTML/CSS/JS pages. `landing_page/` is a product landing page with a
design system (`design-system.html`, `tokens.css`). `portfolio/` is a personal
portfolio site with project cards, skills section, and contact links.

**Install & run:**
```bash
# landing_page
cd landing_page
open index.html

# portfolio
cd portfolio
open index.html
```

**No installation needed** — runs entirely in the browser.

---

## Python version

All Python projects were built and tested with **Python 3.11+**.
Verify your version with:
```bash
python3 --version
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` inside the project folder |
| Streamlit app won't start | Make sure you're inside the project folder before running `streamlit run app.py` |
| `shap` install fails | Try `pip install shap --no-build-isolation` or install via conda |
| MongoDB connection refused | Start MongoDB: `brew services start mongodb-community` (macOS) |
| Android Gradle sync fails | Check Android Studio SDK path and ensure SDK 24+ is installed |
| Port scanner permission error | The scanner uses standard TCP connect scans — no root required |
