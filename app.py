import os
import datetime
import pymongo
from bson.objectid import ObjectId
from dotenv import load_dotenv, dotenv_values
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from functools import wraps


# load environment variables from .env file
load_dotenv()

# -------------------
# AUTH CONFIG
# -------------------
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DBNAME")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

MAIL_FROM = os.getenv("MAIL_FROM")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

serializer = URLSafeTimedSerializer(SECRET_KEY, salt="password-reset-salt")


def create_app():
    """
    Create and configure the Flask application.
    returns: app: the Flask application object
    """

    app = Flask(__name__)
    # load flask config from env variables
    config = dotenv_values()
    app.config.from_mapping(config)
    
    # Ensure SECRET_KEY is set (required for sessions and flash messages)
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    cxn = pymongo.MongoClient(os.getenv("MONGO_URI"))
    db = cxn[os.getenv("MONGO_DBNAME")]
    users = db.users
db.plans.create_index("created_at")
try:
    users.create_index("email", unique=True)
except Exception:
    pass


    try:
        cxn.admin.command("ping")
        print(" *", "Connected to MongoDB!")
    except Exception as e:
        print(" * MongoDB connection error:", e)







    # -----------------------
    # Helper utilities
    # -----------------------
    def _safe_objectid(oid):
        try:
            return ObjectId(oid)
        except Exception:
            return None

    def _parse_int_or_none(s):
        try:
            return int(s)
        except Exception:
            return None

    def current_user():
        if "user_email" in session:
            return users.find_one({"email": session["user_email"]})
        return None

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user():
                flash("Please sign in first.", "warning")
                return redirect(url_for("signin"))
            return view(*args, **kwargs)
        return wrapped

    def _parse_float_positive(s):
        try:
            v = float(s)
            if v <= 0:
                return None
            return v
        except Exception:
            return None
        
    # -----------------------
    # HOME
    # -----------------------
    @app.route("/")
    @login_required
    def home():
        """
        Route for the home page.
        Returns:
            rendered template (str): The rendered HTML template.
        """
        plans = db.plans.find({}).sort("created_at", -1)
        return render_template("index.html", plans=plans)

    # -----------------------
    # PLAN
    # -----------------------
    @app.route("/create", methods=["POST"])
    @login_required
    def create_plan():
        """
        Route for POST requests to the create page.
        Accepts the form submission data for a new plan and saves the document to the database.
        Returns:
            redirect (Response): A redirect response to the home page.
        """
        title = request.form["title"]  
         
        actual_expense_str = request.form.get("actual_expense", "").strip()
        actual_expense = float(actual_expense_str) if actual_expense_str else 0.0

        day = request.form.get("day")
        month = request.form.get("month")
        year = request.form.get("year")
        category = request.form.get("category", "")
        notes = request.form.get("notes", "")

        doc = {
            "title": title,  
            "actual_expense": actual_expense,
            "day": int(day) if day else None,  
            "month": int(month) if month else None,
            "year": int(year) if year else None,
            "category": category,
            "notes": notes,
            "created_at": datetime.datetime.utcnow(),
        }
        db.plans.insert_one(doc)

        return redirect(url_for("home"))

    @app.route("/edit/<plan_id>")
    @login_required
    def edit(plan_id):
        """
        Route for GET requests to the edit page.
        Displays a form users can fill out to edit an existing plan.
        Args:
            plan_id (str): The ID of the plan to edit.
        Returns:
            rendered template (str): The rendered HTML template.
        """
        doc = db.plans.find_one({"_id": ObjectId(plan_id)})
        return render_template("edit_plan.html", doc=doc)

    @app.route("/edit/<plan_id>", methods=["POST"])
    @login_required
    def edit_plan(plan_id):
        """
        Route for POST requests to the edit page.
        Accepts the form submission data for the specified plan and updates the document in the database.
        Args:
            plan_id (str): The ID of the plan to edit.
        Returns:
            redirect (Response): A redirect response to the home page.
        """
        title = request.form["title"]

        actual_expense_str = request.form.get("actual_expense", "").strip()
        actual_expense = float(actual_expense_str) if actual_expense_str else 0.0

        day = request.form.get("day")
        month = request.form.get("month")
        year = request.form.get("year")
        category = request.form.get("category", "")
        notes = request.form.get("notes", "")

        doc = {
            "title": title,
            "actual_expense": actual_expense,
            "day": int(day) if day else None,
            "month": int(month) if month else None,
            "year": int(year) if year else None,
            "category": category,
            "notes": notes,
            "created_at": datetime.datetime.utcnow(),
        }

        db.plans.update_one({"_id": ObjectId(plan_id)}, {"$set": doc})

        return redirect(url_for("home"))

    @app.route("/delete/<plan_id>")
    @login_required
    def delete(plan_id):
        """
        Route for GET requests to the delete page.
        Deletes the specified plan from the database, and then redirects the browser to the home page.
        Args:
            plan_id (str): The ID of the plan to delete.
        Returns:
            redirect (Response): A redirect response to the home page.
        """
        db.plans.delete_one({"_id": ObjectId(plan_id)})
        return redirect(url_for("home"))

    @app.route("/search")
    @login_required
    def search():
        """
        Route for GET requests to the search page.
        Allows users to search plans by category.
        Returns:
            rendered template (str): The rendered HTML template.
        """
        category = request.args.get("category", "")
        if category:
            plans = db.plans.find({"category": {"$regex": category, "$options": "i"}}).sort("created_at", -1)
        else:
            plans = db.plans.find({}).sort("created_at", -1)
        
        return render_template("index.html", plans=plans, search_category=category)
    

    @app.route("/expenses_list")
    @login_required
    def expenses_list():
        """
        List expenses with optional filters: search (q), category, year+month (ym), and pagination (page).
        """
        q = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()
        ym = request.args.get("ym", "").strip()
        date_str = request.args.get("date", "").strip()
        year_q = request.args.get("year", "").strip()
        month_q = request.args.get("month", "").strip()
        page = _parse_int_or_none(request.args.get("page")) or 1
        per_page = 10  # Customize how many expenses per page

        query = {}

        # Handle search by note/title
        if q:
            query["$or"] = [
                {"note": {"$regex": q, "$options": "i"}},
                {"title": {"$regex": q, "$options": "i"}}
            ]

        # Handle category filter
        if category:
            query["category"] = {"$regex": category, "$options": "i"}

        # Handle exact date filter (YYYY-MM-DD)
        if date_str:
            try:
                dparts = date_str.split("-")
                if len(dparts) == 3:
                    y = int(dparts[0])
                    m = int(dparts[1])
                    day = int(dparts[2])
                    query["year"] = y
                    query["month"] = m
                    query["day"] = day
            except Exception:
                flash("Invalid date format for date. Use YYYY-MM-DD.", "warning")
        # Handle separate year/month query params (year only or year+month)
        elif year_q:
            y = _parse_int_or_none(year_q)
            m = _parse_int_or_none(month_q)
            if y:
                query["year"] = int(y)
                if m:
                    query["month"] = int(m)
        # Fallback: handle year-month (ym) filter for backward compatibility
        elif ym:
            try:
                y, m = ym.split("-")
                year = int(y)
                month = int(m)
                query["year"] = year
                query["month"] = month
            except ValueError:
                flash("Invalid date format for ym. Use YYYY-MM.", "warning")

        # Get total count
        total_expenses = db.expenses.count_documents(query)
        total_pages = (total_expenses + per_page - 1) // per_page

        # Fetch expenses (paged)
        expenses = db.expenses.find(query)\
            .sort("date", -1)\
            .skip((page - 1) * per_page)\
            .limit(per_page)

        # pass back parsed query params so the template can prefill controls
        import datetime as _dt
        current_year = _dt.datetime.utcnow().year
        return render_template(
            "expenses.html",
            expenses=expenses,
            q=q,
            category=category,
            ym=ym,
            date=date_str,
            year=year_q,
            month=month_q,
            page=page,
            total_pages=total_pages,
            current_year=current_year
        )
    @app.route("/expense_new", methods=["GET"])
    @login_required
    def expense_new():
        """
        Display the form to add a new expense.
        """
        return render_template("expense_new.html")   
    
      

    @app.route("/expense_create", methods=["POST"])
    @login_required
    def expense_create():
        """
        Handle the form submission to create a new expense.
        """
       
            # Get form data
        date_str = request.form.get("date")
        amount = float(request.form.get("amount"))
        category = request.form.get("category", "").strip()
        note = request.form.get("note", "").strip()
            
        # Parse the date
        from datetime import datetime
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            
        # Create expense document
        expense_doc = {
                "date": date_obj,
                "year": date_obj.year,
                "month": date_obj.month,
                "amount": amount,
                "category": category,
                "note": note,
                "title": category  # You can customize this
            }
            
        # Insert into database
        db.expenses.insert_one(expense_doc)
       
        return redirect(url_for("expenses_list"))
        """
        except ValueError as e:
            flash(f"Invalid input: {str(e)}", "error")
            return redirect(url_for("expense_new"))
        except Exception as e:
            flash(f"Error creating expense: {str(e)}", "error")
            return redirect(url_for("expense_new"))
        """

    @app.route("/expense/edit/<expense_id>", methods=["GET", "POST"])
    @login_required
    def expense_edit(expense_id):
        from bson.objectid import ObjectId
        
        if request.method == "POST":
            # Handle update
            from datetime import datetime
            date_str = request.form.get("date")
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            
            db.expenses.update_one(
                {"_id": ObjectId(expense_id)},
                {"$set": {
                    "date": date_obj,
                    "year": date_obj.year,
                    "month": date_obj.month,
                    "amount": float(request.form.get("amount")),
                    "category": request.form.get("category", "").strip(),
                    "note": request.form.get("note", "").strip(),
                }}
            )
            return redirect(url_for("expenses_list"))
    
         # GET: show edit form
        expense = db.expenses.find_one({"_id": ObjectId(expense_id)})
        return render_template("expense_edit.html", expense=expense)
    @app.route("/expense/update/<expense_id>", methods=["POST"])
    @login_required
    def expense_update(expense_id):
        from bson.objectid import ObjectId
        from datetime import datetime
        
        date_str = request.form.get("date")
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        
        db.expenses.update_one(
            {"_id": ObjectId(expense_id)},
            {"$set": {
                "date": date_obj,
                "year": date_obj.year,
                "month": date_obj.month,
                "amount": float(request.form.get("amount")),
                "category": request.form.get("category", "").strip(),
                "note": request.form.get("note", "").strip(),
                "title": request.form.get("category", "").strip() or "Expense"
            }}
        )
        return redirect(url_for("expenses_list"))
    @app.route("/expense/delete/<expense_id>",methods=["GET", "POST"])
    @login_required
    def expense_delete(expense_id):
        """
        Delete an expense and redirect to expenses list.
        """
        from bson.objectid import ObjectId
        db.expenses.delete_one({"_id": ObjectId(expense_id)})
        return redirect(url_for("expenses_list"))


    # -----------------------
    # Monthly Budget
    # -----------------------
    @app.route("/monthly_budget/add", methods=["GET", "POST"])
    @login_required
    def add_monthly_budget():
        """
        GET: show form (if template exists)
        POST: create monthly budget. Required: budget (positive), month(1-12), year.
        Behavior: If a budget for same month+year exists, we insert a new document (not upsert) to preserve history.
        (If you prefer upsert/replace, it's easy to change.)
        """
        if request.method == "GET":
            # allow prefilling month/year via query params (e.g. ?month=3&year=2025)
            month_q = _parse_int_or_none(request.args.get('month'))
            year_q = _parse_int_or_none(request.args.get('year'))
            return render_template("add_monthly_budget.html", prefill_month=month_q, prefill_year=year_q)

        # POST
        budget_raw = request.form.get("budget", "").strip()
        try:
            budget_v = float(budget_raw)
            if budget_v <= 0:
                raise ValueError
        except Exception:
            flash("budget is required and must be a positive number", "danger")
            return redirect(url_for("add_monthly_budget"))

        month = _parse_int_or_none(request.form.get("month"))
        year = _parse_int_or_none(request.form.get("year"))
        if month is None or year is None or month < 1 or month > 12:
            flash("month (1-12) and year are required", "danger")
            return redirect(url_for("add_monthly_budget"))

        notes = request.form.get("notes", "").strip()

        doc = {
            "budget": budget_v,
            "month": int(month),
            "year": int(year),
            "notes": notes,
            "created_at": datetime.datetime.utcnow(),
        }
        db.monthly_budgets.insert_one(doc)
        flash("Monthly budget added", "success")
        return redirect(url_for("home"))


    @app.route("/monthly_budget/edit/<budget_id>", methods=["GET", "POST"])
    @login_required
    def edit_monthly_budget(budget_id):
        """
        GET: render edit form
        POST: update budget
        """
        oid = _safe_objectid(budget_id)
        if not oid:
            flash("Invalid budget id", "danger")
            return redirect(url_for("home"))

        existing = db.monthly_budgets.find_one({"_id": oid})
        if not existing:
            flash("Budget not found", "danger")
            return redirect(url_for("home"))

        if request.method == "GET":
            return render_template("edit_monthly_budget.html", budget=existing)

        # POST update
        try:
            budget_v = float(request.form.get("budget"))
            if budget_v <= 0:
                raise ValueError
        except Exception:
            flash("budget must be a positive number", "danger")
            return redirect(url_for("edit_monthly_budget", budget_id=budget_id))

        month = _parse_int_or_none(request.form.get("month")) or existing.get("month")
        year = _parse_int_or_none(request.form.get("year")) or existing.get("year")
        notes = request.form.get("notes", existing.get("notes", "")).strip()

        update = {
            "budget": budget_v,
            "month": int(month),
            "year": int(year),
            "notes": notes,
            "modified_at": datetime.datetime.utcnow(),
        }
        db.monthly_budgets.update_one({"_id": oid}, {"$set": update})
        flash("Monthly budget updated", "success")
        return redirect(url_for("home"))


    @app.route("/monthly_budget/delete/<budget_id>")
    @login_required
    def delete_monthly_budget(budget_id):
        """
        Delete a monthly budget (kept GET for parity).
        """
        oid = _safe_objectid(budget_id)
        if not oid:
            flash("Invalid budget id", "danger")
            return redirect(url_for("home"))
        db.monthly_budgets.delete_one({"_id": oid})
        flash("Budget deleted", "info")
        return redirect(url_for("home"))

    @app.route("/monthly_budget/get/<int:month>/<int:year>")
    @login_required
    def get_monthly_budget(month, year):
        """
        Return JSON: details of the monthly budget (latest one found) + computed spent & remaining.
        If multiple budgets exist for same month/year, returns the latest by created_at.
        """
        doc = db.monthly_budgets.find({"month": month, "year": year}).sort("created_at", -1).limit(1)
        doc = list(doc)
        if not doc:
            return jsonify({"found": False}), 404
        mb = doc[0]

        # compute spent amount over plans in that month/year (sum actual_expense)
        agg = list(db.plans.aggregate([
            {"$match": {"month": month, "year": year}},
            {"$group": {"_id": None, "spent": {"$sum": "$actual_expense"}}}
        ]))
        spent_amount = float(agg[0]["spent"]) if agg and agg[0].get("spent") is not None else 0.0
        remaining = float(mb["budget"]) - spent_amount

        out = {
            "budget_id": str(mb["_id"]),
            "budget": mb["budget"],
            "month": mb["month"],
            "year": mb["year"],
            "notes": mb.get("notes", ""),
            "spent": spent_amount,
            "remaining": remaining
        }
        return jsonify(out)


    @app.route('/settings/clear_history', methods=['POST'])
    @login_required
    def clear_history():
        """
        Clear all monthly budgets and expenses from the database.
        This route only accepts POST requests and requires a form confirmation.
        The form should include a field named `confirm` with the value 'DELETE' to proceed.
        """
        confirm = request.form.get('confirm', '')
        # require an explicit typed confirmation to reduce accidental deletes
        if confirm != 'DELETE':
            flash('Clear history aborted: confirmation text did not match.', 'warning')
            return redirect(url_for('settings'))

        try:
            # delete all monthly budgets and expenses
            db.monthly_budgets.delete_many({})
            db.expenses.delete_many({})
            flash('All monthly budgets and expenses have been cleared.', 'success')
        except Exception as e:
            flash(f'Failed to clear history: {str(e)}', 'danger')

        return redirect(url_for('settings'))



    # -----------------------
    # Finder endpoints (return JSON arrays)
    # -----------------------
    @app.route("/plans/find_by_date", methods=["GET"])
    @login_required
    def find_by_date():
        """
        Query params supported:
          - day, month, year (any combination)
        Examples:
          /plans/find_by_date?day=5&month=3&year=2025
          /plans/find_by_date?month=3&year=2025
          /plans/find_by_date?year=2025
        Returns JSON list of matching plans.
        """
        day = _parse_int_or_none(request.args.get("day"))
        month = _parse_int_or_none(request.args.get("month"))
        year = _parse_int_or_none(request.args.get("year"))

        if day is None and month is None and year is None:
            return jsonify({"error": "provide at least one of day/month/year as query params"}), 400

        q = {}
        if day is not None:
            q["day"] = int(day)
        if month is not None:
            q["month"] = int(month)
        if year is not None:
            q["year"] = int(year)

        cursor = db.plans.find(q).sort("created_at", -1)
        out = []
        for p in cursor:
            p["_id"] = str(p["_id"])
            out.append(p)
        return jsonify(out)
    
    @app.route("/plans/find_by_month_year", methods=["GET"])
    @login_required
    def find_by_month_year():
        """
        /plans/find_by_month_year?month=3&year=2025
        """
        month = _parse_int_or_none(request.args.get("month"))
        year = _parse_int_or_none(request.args.get("year"))
        if month is None or year is None:
            return jsonify({"error": "month and year are required"}), 400
        cursor = db.plans.find({"month": int(month), "year": int(year)}).sort("created_at", -1)
        out = []
        for p in cursor:
            p["_id"] = str(p["_id"])
            out.append(p)
        return jsonify(out)
    
    @app.route("/plans/find_by_year", methods=["GET"])
    @login_required
    def find_by_year():
        """
        /plans/find_by_year?year=2025
        """
        year = _parse_int_or_none(request.args.get("year"))
        if year is None:
            return jsonify({"error": "year is required"}), 400
        cursor = db.plans.find({"year": int(year)}).sort("created_at", -1)
        out = []
        for p in cursor:
            p["_id"] = str(p["_id"])
            out.append(p)
        return jsonify(out)
    
    @app.route("/plans/find_by_category", methods=["GET"])
    @login_required
    def find_by_category():
        """
        /plans/find_by_category?category=food
        Case-insensitive partial matching.
        """
        category = request.args.get("category", "").strip()
        if not category:
            return jsonify({"error": "category query param required"}), 400
        cursor = db.plans.find({"category": {"$regex": category, "$options": "i"}}).sort("created_at", -1)
        out = []
        for p in cursor:
            p["_id"] = str(p["_id"])
            out.append(p)
        return jsonify(out)

    
    # -----------------------
    # Budget summary
    # -----------------------
    @app.route("/budget/summary/<int:month>/<int:year>")
    @login_required
    def budget_summary(month, year):
        """
        Returns JSON: {month, year, spent, budget(optional if exists), 
                      remaining_budget(optional if budget exists), 
                      unallocated_budget(optional if budget exists)}
        If a monthly_budget exists for the month/year, include budget and calculations. 
        Otherwise budget/remaining_budget/unallocated_budget = null.
        """
        # Calculate total spent for month/year from EXPENSES collection
        agg = list(db.expenses.aggregate([
            {"$match": {"month": month, "year": year}},
            {"$group": {
                "_id": None, 
                "spent": {"$sum": "$amount"},  #  amount
            }}
        ]))
        
        spent_amount = float(agg[0]["spent"]) if agg and agg[0].get("spent") is not None else 0.0

        # Get monthly budget
        mb_doc = db.monthly_budgets.find_one({"month": month, "year": year})
        
        if mb_doc:
            budget_value = float(mb_doc["budget"])
            remaining_budget = budget_value - spent_amount
        else:
            budget_value = None
            remaining_budget = None

        return jsonify({
            "month": month,
            "year": year,
            "spent": spent_amount,
            "budget": budget_value,
            "remaining_budget": remaining_budget,
        })

    # -----------------------
    # Additional APIs to list all plans
    # -----------------------
    @app.route("/api/plans", methods=["GET"])
    @login_required
    def api_get_plans():
        cursor = db.plans.find({}).sort("created_at", -1)
        out = []
        for p in cursor:
            p["_id"] = str(p["_id"])
            out.append(p)
        return jsonify(out)

    @app.route("/api/budgets", methods=["GET"])
    @login_required
    def api_get_budgets():
        cursor = db.monthly_budgets.find({}).sort([("year", -1), ("month", -1)])
        out = []
        for b in cursor:
            b["_id"] = str(b["_id"])
            out.append(b)
        return jsonify(out)


    @app.route("/budget/category-breakdown/<int:month>/<int:year>")
    @login_required
    def category_breakdown(month, year):
        """
        Returns JSON: {month, year, categories: [{category, spent, count}]}
        Groups by unique categories that users actually used that month
        """
        # Aggregate to get spent amounts by category from EXPENSES
        agg = list(db.expenses.aggregate([
            {"$match": {"month": month, "year": year}},
            {"$group": {
                "_id": {"$toLower": "$category"},  # toLower
                "spent": {"$sum": "$amount"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"spent": -1}}
        ]))
        
        # Format the results
        categories = []
        for item in agg:
            categories.append({
                "category": item["_id"].title(),  # capitalize for display
                "spent": float(item["spent"]),
                "count": item["count"]
            })
        
        return jsonify({
            "month": month,
            "year": year,
            "categories": categories
        })


    @app.route("/budget/daily_totals/<int:month>/<int:year>")
    @login_required
    def budget_daily_totals(month, year):
        """
        Returns JSON: {month, year, days: [{date: 'YYYY-MM-DD', total: float}, ...]}
        The period returned starts at the first day of the given month and includes 30 consecutive days.
        Days with no expenses are returned with total 0.0.
        """
        # compute start and end (30-day window starting at the 1st of the month)
        start = datetime.datetime(year, month, 1)
        end = start + datetime.timedelta(days=30)

        # aggregate totals by year/month/day within the window
        agg = list(db.expenses.aggregate([
            {"$match": {"date": {"$gte": start, "$lt": end}}},
            {"$group": {
                "_id": {"y": {"$year": "$date"}, "m": {"$month": "$date"}, "d": {"$dayOfMonth": "$date"}},
                "total": {"$sum": "$amount"}
            }},
            {"$project": {"_id": 0, "year": "$_id.y", "month": "$_id.m", "day": "$_id.d", "total": 1}},
            {"$sort": {"year": 1, "month": 1, "day": 1}}
        ]))

        # map results by date
        totals = {}
        for it in agg:
            try:
                d = datetime.date(int(it["year"]), int(it["month"]), int(it["day"]))
                totals[d] = float(it.get("total", 0.0))
            except Exception:
                continue

        days = []
        for i in range(30):
            dt = (start + datetime.timedelta(days=i)).date()
            days.append({"date": dt.isoformat(), "total": float(totals.get(dt, 0.0))})

        return jsonify({"month": month, "year": year, "days": days})


    @app.route('/settings')
    @login_required
    def settings():
        """
        Render a simple settings page (placeholder).
        """
        return render_template('settings.html')

    @app.route("/signin", methods=["GET", "POST"])
    def signin():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = users.find_one({"email": email})
            if user and check_password_hash(user["password_hash"], password):
                session["user_email"] = email
                flash("Logged in successfully.", "success")
                return redirect(url_for("home"))
            flash("Invalid email or password.", "danger")
        return render_template("signin.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")
            if not email or not password:
                flash("Email and password are required.", "danger")
            elif password != confirm:
                flash("Passwords do not match.", "danger")
            elif len(password) < 6:
                flash("Password must be at least 6 characters.", "danger")
            else:
                try:
                    users.insert_one({
                        "email": email,
                        "password_hash": generate_password_hash(password),
                        "created_at": datetime.datetime.utcnow(),
                    })
                    flash("Account created! Please sign in.", "success")
                    return redirect(url_for("signin"))
                except Exception:
                    flash("Email already registered.", "warning")
                    return redirect(url_for("signin"))
        return render_template("signup.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You are logged out.", "info")
        return redirect(url_for("signin"))


    return app

app = create_app()

if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")

    app.run(port=FLASK_PORT)
