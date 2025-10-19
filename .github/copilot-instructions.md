# Budget Tracker - AI Agent Instructions

## Architecture Overview
**Single-file Flask app** (`app.py`) with MongoDB backend. No package structure—all routes, DB logic, and helpers live in one file. Templates use Jinja2, extending `templates/base.html` which provides navigation and flash message rendering.

### Key Design Decisions
- **Dual data model**: `plans` collection tracks *planned* spending with flexible day/month/year fields (nullable); `expenses` collection tracks *actual* spending with full datetime stamps
- **Docker-first deployment**: Primary dev workflow uses `docker-compose.yml` to spin up Flask + MongoDB together
- **Historical budget tracking**: `monthly_budgets` collection preserves history—new inserts instead of upserts allow tracking budget changes over time

---

## Critical Developer Workflows

### Local Development (Docker - RECOMMENDED)
```powershell
docker compose up --build   # Starts Flask (port 5001) + MongoDB (port 27018)
docker compose down         # Stop containers
docker compose down --volumes  # Reset MongoDB data
```
**Port mapping**: Host 5001 → Container 5000 (Flask), Host 27018 → Container 27017 (MongoDB)

### Alternative: Direct Python Run
```powershell
pipenv shell
pipenv install -r requirements.txt
python app.py  # Reads .env for MONGO_URI, MONGO_DBNAME, FLASK_PORT
```
⚠️ Requires separate MongoDB instance (Atlas or local). Check console for "Connected to MongoDB!" message.

### Environment Variables
**Required**: `MONGO_URI`, `MONGO_DBNAME`  
**Optional**: `SECRET_KEY` (defaults to dev key), `FLASK_PORT` (default 5000), `FLASK_ENV`

Copy `env.example` to `.env` and edit. For Docker, `docker-compose.yml` hardcodes credentials:
```yaml
MONGO_URI=mongodb://admin:secret@mongodb:27017/?authSource=admin
MONGO_DBNAME=bytesized
```

---

## Data Models (MongoDB Collections)

### `plans` - Planned Spending
```python
{
  "title": str,           # Display name
  "actual_expense": float,  # Amount (misnomer: actually PLANNED amount)
  "day": int|null,        # 1-31 or null
  "month": int|null,      # 1-12 or null  
  "year": int|null,       # e.g. 2025 or null
  "category": str,        # Free text (e.g. "food", "rent")
  "notes": str,
  "created_at": datetime  # UTC timestamp
}
```
**Design quirk**: `actual_expense` field name is legacy; it stores *planned* amounts. Filtering APIs use numeric year/month/day fields.

### `expenses` - Actual Spending
```python
{
  "date": datetime,       # Full datetime object
  "year": int,            # Extracted from date for fast queries
  "month": int,           # Extracted from date
  "amount": float,        # Actual spent amount
  "category": str,
  "note": str,
  "title": str            # Usually mirrors category
}
```
**Query pattern**: Use `year`/`month` fields for fast filtering (indexed), `date` for display and date range queries.

### `monthly_budgets` - Monthly Budget Caps
```python
{
  "budget": float,        # Total budget for the month
  "month": int,           # 1-12
  "year": int,
  "notes": str,
  "created_at": datetime
}
```
**Historical behavior**: Multiple budgets for same month/year are allowed. APIs return latest by `created_at`.

---

## Code Patterns & Conventions

### Helper Functions (in `app.py`)
```python
_safe_objectid(oid)         # Returns ObjectId or None if invalid
_parse_int_or_none(s)       # Safe int parsing, returns None on error
_parse_float_positive(s)    # Returns float if >0, else None
```
**Always use these** when parsing form inputs or URL params.

### Route Conventions
- **GET**: Render forms (e.g. `/expense_new`, `/edit/<id>`)
- **POST**: Process submissions (e.g. `/expense_create`, `/edit/<id>`)
- **Redirects**: Always redirect after POST to prevent duplicate submissions
  - Example: `return redirect(url_for("expenses_list"))` after expense creation
- **Flash messages**: Use `flash("Message", "category")` for user feedback
  - Categories: `"success"`, `"danger"`, `"warning"`, `"info"`
  - Rendered in `templates/base.html` via `get_flashed_messages(with_categories=true)`

### Pagination Pattern (see `expenses_list`)
```python
page = _parse_int_or_none(request.args.get("page")) or 1
per_page = 10
skip = (page - 1) * per_page
cursor = db.expenses.find(query).sort("date", -1).skip(skip).limit(per_page)
total_pages = (db.expenses.count_documents(query) + per_page - 1) // per_page
```
**When adding new list endpoints**: Preserve `q`, `category`, `ym`, `page` query params across pagination links.

### Template-Form Binding
Form field `name` attributes in templates are the source of truth. When editing routes:
1. Check template HTML for exact field names (e.g. `expense_new.html` → `<input name="amount">`)
2. Match in route: `request.form.get("amount")`
3. Parse/validate using helper functions

---

## Key Endpoints Reference

### HTML Pages
| Route | Method | Purpose | Template |
|-------|--------|---------|----------|
| `/` | GET | Home page, list all plans | `index.html` |
| `/expenses_list` | GET | List expenses (searchable, paginated) | `expenses.html` |
| `/expense_new` | GET | Show new expense form | `expense_new.html` |
| `/expense/edit/<id>` | GET/POST | Edit expense | `expense_edit.html` |
| `/edit/<plan_id>` | GET/POST | Edit plan | `edit_plan.html` |
| `/monthly_budget/add` | GET/POST | Add monthly budget | `add_monthly_budget.html` |

### Data Modification
| Route | Method | Action |
|-------|--------|--------|
| `/create` | POST | Create new plan → redirect to `/` |
| `/expense_create` | POST | Create expense → redirect to `expenses_list` |
| `/expense/update/<id>` | POST | Update expense |
| `/expense/delete/<id>` | POST/GET | Delete expense |
| `/delete/<plan_id>` | GET | Delete plan |

### JSON APIs
| Route | Query Params | Returns |
|-------|--------------|---------|
| `/plans/find_by_date` | `?day=5&month=3&year=2025` | Array of matching plans |
| `/plans/find_by_month_year` | `?month=3&year=2025` | Plans for month/year |
| `/plans/find_by_category` | `?category=food` | Case-insensitive category search |
| `/monthly_budget/get/<month>/<year>` | — | Budget + spent + remaining |
| `/budget/summary/<month>/<year>` | — | Spent vs budget summary |
| `/budget/category-breakdown/<month>/<year>` | — | Per-category spending |
| `/budget/daily_totals/<month>/<year>` | — | 30-day daily totals |

---

## Making Changes: Agent Guidelines

### Adding a New Route
1. **Add route function in `app.py`** following existing patterns:
   ```python
   @app.route("/my_endpoint", methods=["GET", "POST"])
   def my_handler():
       if request.method == "POST":
           # Process form, insert/update DB
           flash("Success!", "success")
           return redirect(url_for("home"))
       return render_template("my_template.html")
   ```
2. **Create template in `templates/`** extending `base.html`:
   ```html
   {% extends "base.html" %}
   {% block container %}
   <!-- Your content -->
   {% endblock %}
   ```
3. **Update navigation** in `templates/base.html` if needed

### Modifying Data Models
- **Plans**: If changing date fields, update both storage logic (`/create`, `/edit/<plan_id>`) and finder APIs (`/plans/find_by_*`)
- **Expenses**: Date stored as datetime but also denormalized into `year`/`month` fields—update both in `/expense_create` and `/expense/update/<id>`
- **Aggregations**: Check `/budget/summary` and `/budget/category-breakdown` when changing expense schema

### Search/Filter Features
Follow `expenses_list` pattern:
1. Parse query params with helper functions
2. Build MongoDB query dict: `query = {"field": {"$regex": value, "$options": "i"}}`
3. Pass params to template for repopulation in forms
4. Preserve filters in pagination links

---

## Testing & Validation
**No automated tests present.** Validate changes by:
1. Running `docker compose up --build` or `python app.py`
2. Check console for "Connected to MongoDB!" message
3. Test routes via browser or `curl`
4. Inspect MongoDB data with Compass (host `localhost:27018`) or shell:
   ```bash
   docker exec -it <mongodb_container> mongosh -u admin -p secret
   use bytesized
   db.expenses.find().pretty()
   ```

---

## Common Gotchas
- **`actual_expense` misnomer**: In `plans` collection, this stores *planned* amounts, not actual spending
- **Duplicate date fields**: `expenses` has both `date` (datetime) and `year`/`month` (int)—keep in sync
- **ObjectId strings**: Always convert with `_safe_objectid()` when accepting from URLs/forms
- **Port conflicts**: If 5000/27017 already in use, edit `docker-compose.yml` ports mapping
- **Flash messages**: Only shown once (session-based). Always redirect after POST to display them

---

## Dependencies (requirements.txt)
```
Flask==1.1.2, pymongo==3.11.3, python-dotenv==0.16.0
Jinja2==2.11.3, Werkzeug==1.0.1
```
⚠️ **Older versions**: Flask 1.1.2 (not 2.x), Python 3.8 target. Check compatibility when adding new packages.

---

## Questions for Maintainers
- Should `plans.actual_expense` be renamed to `planned_amount` for clarity?
- Prefer upsert for `monthly_budgets` (one budget per month) vs. current historical inserts?
- Add indexes on `expenses.year`/`expenses.month` for query performance?
