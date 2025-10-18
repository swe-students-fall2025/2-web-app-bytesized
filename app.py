import os
import datetime
import pymongo
from bson.objectid import ObjectId
from dotenv import load_dotenv, dotenv_values
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

# load environment variables from .env file
load_dotenv()

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
    def expenses_list():
        """
        List expenses with optional filters: search (q), category, year+month (ym), and pagination (page).
        """
        q = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()
        ym = request.args.get("ym", "").strip()
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

        # Handle year-month (ym) filter
        if ym:
           
                y, m = ym.split("-")
                year = int(y)
                month = int(m)
                query["year"] = year
                query["month"] = month
                """
            except ValueError:
                flash("Invalid date format for ym. Use YYYY-MM.", "warning")
                """

        # Get total count
        total_expenses = db.expenses.count_documents(query)
        total_pages = (total_expenses + per_page - 1) // per_page

        # Fetch expenses (paged)
        expenses = db.expenses.find(query)\
            .sort("date", -1)\
            .skip((page - 1) * per_page)\
            .limit(per_page)

        return render_template(
            "expenses.html",
            expenses=expenses,
            q=q,
            category=category,
            ym=ym,
            page=page,
            total_pages=total_pages
        )
    @app.route("/expense_new", methods=["GET"])
    def expense_new():
        """
        Display the form to add a new expense.
        """
        return render_template("expense_new.html")   
    
      

    @app.route("/expense_create", methods=["POST"])
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



    # -----------------------
    # Finder endpoints (return JSON arrays)
    # -----------------------
    @app.route("/plans/find_by_date", methods=["GET"])
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
    def budget_summary(month, year):
        """
        Returns JSON: {month, year, spent, budget(optional if exists), 
                      remaining_budget(optional if budget exists), 
                      unallocated_budget(optional if budget exists)}
        If a monthly_budget exists for the month/year, include budget and calculations. 
        Otherwise budget/remaining_budget/unallocated_budget = null.
        """
        # Calculate total spent for month/year
        agg = list(db.plans.aggregate([
            {"$match": {"month": month, "year": year}},
            {"$group": {
                "_id": None, 
                "spent": {"$sum": "$actual_expense"},
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
            "remaining_budget": remaining_budget,      # Money left after actual spending
        })

    # -----------------------
    # Additional APIs to list all plans
    # -----------------------
    @app.route("/api/plans", methods=["GET"])
    def api_get_plans():
        cursor = db.plans.find({}).sort("created_at", -1)
        out = []
        for p in cursor:
            p["_id"] = str(p["_id"])
            out.append(p)
        return jsonify(out)

    @app.route("/api/budgets", methods=["GET"])
    def api_get_budgets():
        cursor = db.monthly_budgets.find({}).sort([("year", -1), ("month", -1)])
        out = []
        for b in cursor:
            b["_id"] = str(b["_id"])
            out.append(b)
        return jsonify(out)


    @app.route("/budget/category-breakdown/<int:month>/<int:year>")
    def category_breakdown(month, year):
        """
        Returns JSON: {month, year, categories: [{category, spent, count}]}
        Groups by unique categories that users actually used that month
        """
        # Aggregate to get spent amounts by category
        agg = list(db.plans.aggregate([
            {"$match": {"month": month, "year": year}},
            {"$group": {
                "_id": "$category",
                "spent": {"$sum": "$actual_expense"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"spent": -1}}  # Sort by spent amount descending
        ]))
    
        # Format the results
        categories = []
        for item in agg:
            categories.append({
                "category": item["_id"] if item["_id"] else "Uncategorized",
                "spent": float(item["spent"]),
                "count": item["count"]
            })
    
        return jsonify({
            "month": month,
            "year": year,
            "categories": categories
        })


    @app.route('/settings')
    def settings():
        """
        Render a simple settings page (placeholder).
        """
        return render_template('settings.html')


    return app

app = create_app()

if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")

    app.run(port=FLASK_PORT)