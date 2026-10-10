# CATCH — Lost It? CATCH It.

An AI-powered Lost & Found portal built for college campuses. Students report lost or
found items, and an AI matching engine (image histogram similarity + TF-IDF text
similarity + attribute matching) ranks the most likely matches automatically. Owners
verify a unique detail about the item before contact info is revealed.

**Database: SQLite** — no server install required. The database is a single file
(`catch.db`) created automatically the first time you run the app.

## Features in this build

- Student registration & login (Flask-Login, hashed passwords)
- Report Lost Item / Report Found Item, with photo upload
- AI matching engine: image similarity (OpenCV), text similarity (TF-IDF/cosine),
  attribute matching (category/brand/color) → blended into one match score
- Match results page with per-item breakdown (image %, text %, overall %)
- Owner verification flow — contact info is hidden until the "unique mark" answer
  matches what the owner originally entered
- Catch Points + leaderboard (finders earn points automatically)
- Notifications
- Admin panel (dashboard, manage users, manage/delete item reports)
- Responsive Bootstrap 5 UI

## Setup (VS Code / local machine)

### 1. Prerequisites
Just Python 3.10+. That's it — no database server to install.

### 2. Open in VS Code
Unzip the project, then in VS Code: File > Open Folder > select the `CATCH` folder.
Open a terminal: Terminal > New Terminal.

### 3. Create a virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```
You should see `(venv)` appear at the start of your terminal prompt.

### 4. Install dependencies
```bash
pip install -r requirements.txt
```
This takes 2-4 minutes (opencv and scikit-learn are the largest packages).

### 5. Configure environment variables (optional but recommended)
```bash
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env
```
Open `.env` and set `SECRET_KEY` to any random string. You can leave
`ALLOWED_EMAIL_DOMAIN` blank to allow any email to register (fine for a hackathon demo),
or set it to e.g. `college.edu` to restrict registration to your college's domain.

If you skip this step entirely, the app still runs fine with built-in defaults.

### 6. Run the app
```bash
python app.py
```
The first run automatically creates `catch.db` in the project folder with all tables
already set up — no manual database step needed.

Visit **http://localhost:5000** in your browser.

### 7. Create an admin account (optional, for the admin panel)
In a **new terminal** (keep the app running in the first one), with `(venv)` active:
```bash
flask create-admin
```
Follow the prompts (name, email, ID, password). Log in with those credentials to see
`/admin`.

## Project structure
```
CATCH/
├── app.py                 # Main Flask app & routes
├── config.py               # App configuration (SQLite by default)
├── models.py                # SQLAlchemy models
├── ai_matching.py            # AI matching engine
├── database.sql               # Schema reference (auto-created by the app — no need to run manually)
├── requirements.txt
├── catch.db                  # Created automatically on first run
├── static/
│   ├── css/style.css
│   ├── js/main.js
│   └── images/
├── templates/
│   ├── base.html, index.html, login.html, register.html, ...
│   ├── admin/               # Admin panel templates
│   └── errors/               # 404 / 403 / 500 pages
└── uploads/                  # User-uploaded images (created at runtime)
```

## How the AI matching works

For every lost item report, `ai_matching.find_best_matches()` compares it against all
open found-item reports using three weighted signals:

| Signal | Method | Weight |
|---|---|---|
| Image similarity | OpenCV HSV color-histogram correlation | 35% |
| Text similarity | TF-IDF vectorization + cosine similarity on name/description/unique marks | 35% |
| Attribute similarity | Exact-match scoring on category/brand/color | 30% |

The top 5 matches above a minimum threshold (30%) are shown, ranked highest first.

## Quick demo script (for your hackathon walkthrough)

1. Register two accounts — "Student A" (loses something) and "Student B" (finds it)
2. As Student A: Report Lost Item — e.g. "Black JanSport Backpack", add a photo,
   fill in "Unique Marks" with something specific like `small keychain shaped like a cat`
3. Log out, log in as Student B: Report Found Item with a similar description/photo
4. Log back in as Student A → go to Dashboard → click "View Matches" next to your
   lost item → you'll see the AI-ranked match with image/text/overall scores
5. Click "Verify & Claim" → type the exact unique mark you entered in step 2 →
   watch it verify and reveal Student B's contact info, plus award both users points
6. Check `/leaderboard` to see points update

## Switching to MySQL later (optional)

If you want a "real" production database before final submission, install
`pymysql` and `mysql-connector-python`, then in `config.py` change:
```python
SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "mysql+pymysql://user:pass@localhost/catch_db")
```
No other code changes are needed — SQLAlchemy abstracts the database layer.

## Scope notes (for hackathon judges / future work)

This build intentionally uses lightweight ML (OpenCV histograms + TF-IDF) instead of
deep embeddings (Sentence-Transformers/FAISS) so it installs and runs fast on any
machine without a GPU. Swapping in `sentence-transformers` for text embeddings and a
CNN feature extractor for images is a natural upgrade path — `ai_matching.py` is
structured so those functions can be swapped in without touching the rest of the app.

Not yet implemented in this build (documented as future scope):
- Real-time private chat between finder/owner
- Email notifications
- QR-code item pickup
- PDF/CSV export of admin reports
- Full analytics charts / heatmaps
