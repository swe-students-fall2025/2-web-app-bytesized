Purpose
This file gives concise, actionable guidance for AI coding assistants working on this small Flask + MongoDB budget-tracker web app.

Quick facts
- Single-process Flask app in `app.py`. No package layout; templates in `templates/`, static files in `static/`.
- MongoDB used via `pymongo`. DB name and URI are read from environment (see below).
- Main runtime entry: `python app.py` (reads `.env` via python-dotenv).

Important files
- `app.py` — single-file web app: routes, DB access, helpers. Edit here for endpoints and logic.
- `templates/` — Jinja2 templates. Examples: `index.html`, `expenses.html`, `expense_new.html`, `edit_plan.html`.
- `static/` — CSS assets.
- `requirements.txt` / `Pipfile` — Python dependencies (ensure `pymongo`, `flask`, `python-dotenv`).

Environment & run
- Required env vars: `MONGO_URI`, `MONGO_DBNAME`. Optional: `SECRET_KEY`, `FLASK_PORT`, `FLASK_ENV`.
- Local run (PowerShell):
  python -m pip install -r requirements.txt; python app.py

Data shapes (Mongo documents)
- plans collection (see `app.py`): {
  title: str,
  actual_expense: float,
  day: int|null, month: int|null, year: int|null,
  category: str, notes: str,
  created_at: datetime
}
- expenses collection (see `expense_create`): {
  date: datetime, year: int, month: int, amount: float, category: str, note: str, title: str
}
- monthly_budgets collection: { budget: float, month: int, year: int, notes: str, created_at }

Patterns & conventions
- Most DB operations are in `app.py` using `db.<collection>.<method>()`; ObjectId conversion helper `_safe_objectid` is available.
- Simple form handling: routes often use GET for forms and POST for submission (e.g. `/create`, `/expense_create`). Follow existing parsing helpers: `_parse_int_or_none`, `_parse_float_positive`.
- Dates are stored as Python datetimes for `date` fields; plans use numeric year/month/day fields for filtering.

Key endpoints to reference when making changes
- Home / plan listing: `/` (renders `index.html`, uses `db.plans`)
- Create plan: POST `/create`
- Expenses list: `/expenses_list` (supports q, category, ym, page)
- Expense CRUD: `/expense_new`, `/expense_create`, `/expense/edit/<id>`, `/expense/update/<id>`, `/expense/delete/<id>`
- Monthly budget APIs: `/monthly_budget/add`, `/monthly_budget/get/<month>/<year>`, `/monthly_budget/edit/<id>`
- JSON finder APIs: `/plans/find_by_date`, `/plans/find_by_month_year`, `/plans/find_by_category`

Developer tips for agents
- Keep edits minimal and focused within `app.py` unless adding a new template or static asset.
- When adding a route that modifies DB documents, use `ObjectId()` and return redirects to existing pages to stay consistent.
- Pagination and filters in `expenses_list` implement simple skip/limit; preserve this style when adding new listing endpoints.
- Flash messages use Flask's `flash()` and are displayed in `templates/base.html`.

Testing & validation
- No test suite is present. Validate changes by running the app and exercising endpoints via browser or curl.
- Ensure `requirements.txt` is present and `pymongo` is installed; run `python app.py` and check the console for MongoDB ping success.

If you need more context
- Inspect `templates/` to match form field names when editing routes. Field names are the source of truth for POST handlers.
- Use `db.collection.find().pretty()` via a Mongo shell or a GUI to inspect actual documents.

If you change package-level behavior
- Consider adding a brief note in `README.md` documenting new env vars or run steps. Keep changes backwards compatible.

Questions for the repo owner
- Would you prefer monthly budgets to be upserted (one per month) rather than historical inserts? Current behavior preserves history.
