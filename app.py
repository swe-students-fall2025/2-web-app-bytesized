import os
import datetime
from flask import Flask, render_template, request, redirect, url_for
import pymongo
from bson.objectid import ObjectId
from dotenv import load_dotenv, dotenv_values

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

    cxn = pymongo.MongoClient(os.getenv("MONGO_URI"))
    db = cxn[os.getenv("MONGO_DBNAME")]


    try:
        cxn.admin.command("ping")
        print(" *", "Connected to MongoDB!")
    except Exception as e:
        print(" * MongoDB connection error:", e)


    ##############
    # PLANS (existing routes updated for auth & per-user ownership)
    ##############
    @login_required
    def home():
        """
        Route for the home page. 
        Returns: rendered template (str): The rendered HTML template.
        """
        # show only current user's plans
        plans_cursor = db.plans.find({"user_id": _user_id()}).sort("created_at", -1)
        plans = list(plans_cursor)
        # also fetch budgets for quick display (optionally)
        budgets_cursor = db.monthly_budgets.find({"user_id": _user_id()}).sort([("year", -1), ("month", -1)])
        budgets = list(budgets_cursor)
        return render_template("index.html", plans=plans, budgets=budgets)


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
        try:
            planned_expense = float(request.form["planned_expense"])
            if planned_expense < 0:
                raise ValueError
        except Exception:
            flash("Invalid planned_expense", "danger")
            return redirect(url_for("home"))

        actual_expense_str = request.form.get("actual_expense", "").strip()
        actual_expense = float(actual_expense_str) if actual_expense_str else 0.0

        day = request.form.get("day")
        month = request.form.get("month")
        year = request.form.get("year")
        category = request.form.get("category", "")
        notes = request.form.get("notes", "")

        doc = {
            "user_id": _user_id(),
            "title": title,
            "planned_expense": planned_expense,
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
        doc = db.plans.find_one(_ensure_owner({"_id": _safe_objectid(plan_id)}))
        if not doc:
            flash("Plan not found or not authorized", "danger")
            return redirect(url_for("home"))
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
        oid = _safe_objectid(plan_id)
        if not oid:
            flash("Invalid plan id", "danger")
            return redirect(url_for("home"))

        title = request.form["title"]
        try:
            planned_expense = float(request.form["planned_expense"])
            if planned_expense < 0:
                raise ValueError
        except Exception:
            flash("Invalid planned_expense", "danger")
            return redirect(url_for("edit", plan_id=plan_id))

        actual_expense_str = request.form.get("actual_expense", "").strip()
        actual_expense = float(actual_expense_str) if actual_expense_str else 0.0

        day = request.form.get("day")
        month = request.form.get("month")
        year = request.form.get("year")
        category = request.form.get("category", "")
        notes = request.form.get("notes", "")

        doc = {
            "title": title,
            "planned_expense": planned_expense,
            "actual_expense": actual_expense,
            "day": int(day) if day else None,
            "month": int(month) if month else None,
            "year": int(year) if year else None,
            "category": category,
            "notes": notes,
            "modified_at": datetime.datetime.utcnow(),
        }

        res = db.plans.update_one(_ensure_owner({"_id": oid}), {"$set": doc})
        if res.matched_count == 0:
            flash("Plan not found or not authorized", "danger")
        else:
            flash("Plan updated", "success")

        return redirect(url_for("home"))



    @app.route("/delete/<plan_id>", methods=["POST"])
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
        oid = _safe_objectid(plan_id)
        if not oid:
            flash("Invalid plan id", "danger")
            return redirect(url_for("home"))
        res = db.plans.delete_one(_ensure_owner({"_id": oid}))
        if res.deleted_count:
            flash("Plan deleted", "info")
        else:
            flash("Plan not found or not authorized", "danger")
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
            plans = db.plans.find(_ensure_owner({"category": {"$regex": category, "$options": "i"}})).sort("created_at", -1)
        else:
            plans = db.plans.find(_ensure_owner({})).sort("created_at", -1)

        return render_template("index.html", plans=plans, search_category=category)


    ##############
    # FINDER API endpoints (generalized)
    ##############

    def _parse_int_or_none(s):
        try:
            return int(s)
        except Exception:
            return None
        
    @app.route("/plans/find_by_date", methods=["GET"])
    @login_required
    def find_by_date():
        """
        Query params supported:
          - day, month, year
        Returns matching plans for the user.
        Examples:
          /plans/find_by_date?day=5&month=3&year=2025
          /plans/find_by_date?month=3&year=2025
          /plans/find_by_date?year=2025
        """
        day = _parse_int_or_none(request.args.get("day"))
        month = _parse_int_or_none(request.args.get("month"))
        year = _parse_int_or_none(request.args.get("year"))

        filter_q = {"user_id": _user_id()}
        if day is not None:
            filter_q["day"] = day
        if month is not None:
            filter_q["month"] = month
        if year is not None:
            filter_q["year"] = year

        plans_cursor = db.plans.find(filter_q).sort("created_at", -1)
        plans = []
        for p in plans_cursor:
            p["_id"] = str(p["_id"])
            p["user_id"] = str(p["user_id"])
            plans.append(p)
        return jsonify(plans)

    @app.route("/plans/find_by_category", methods=["GET"])
    @login_required
    def find_by_category():
        """
        Query param:
          - category (string)
        Example: /plans/find_by_category?category=food
        """
        category = request.args.get("category", "").strip()
        if not category:
            return jsonify([])

        plans_cursor = db.plans.find(_ensure_owner({"category": {"$regex": category, "$options": "i"}})).sort("created_at", -1)
        plans = []
        for p in plans_cursor:
            p["_id"] = str(p["_id"])
            p["user_id"] = str(p["user_id"])
            plans.append(p)
        return jsonify(plans)
    
    ##############
    # MONTHLY BUDGET CRUD
    ##############

    @app.route("/monthly_budget/add", methods=["GET", "POST"])
    @login_required
    def add_monthly_budget():
        if request.method == "POST":
            # required: budget, month (1-12), year
            try:
                budget = float(request.form["budget"])
                if budget <= 0:
                    flash("Budget must be a positive number", "danger")
                    return redirect(url_for("add_monthly_budget"))
            except Exception:
                flash("Invalid budget value", "danger")
                return redirect(url_for("add_monthly_budget"))

            month = int(request.form.get("month", 0))
            year = int(request.form.get("year", 0))
            if month < 1 or month > 12 or year <= 0:
                flash("Invalid month or year", "danger")
                return redirect(url_for("add_monthly_budget"))

            notes = request.form.get("notes", "")

            doc = {
                "user_id": _user_id(),
                "budget": budget,
                "month": month,
                "year": year,
                "notes": notes,
                "created_at": datetime.datetime.utcnow(),
            }

            # Upsert: replace existing budget for same user/month/year (optional business choice)
            existing = db.monthly_budgets.find_one({"user_id": doc["user_id"], "month": month, "year": year})
            if existing:
                db.monthly_budgets.replace_one({"_id": existing["_id"]}, doc)
                flash("Monthly budget updated (replaced existing)", "success")
            else:
                db.monthly_budgets.insert_one(doc)
                flash("Monthly budget added", "success")

            return redirect(url_for("home"))

        return render_template("add_monthly_budget.html")
    

    @app.route("/monthly_budget/edit/<budget_id>", methods=["GET", "POST"])
    @login_required
    def edit_monthly_budget(budget_id):
        oid = _safe_objectid(budget_id)
        if not oid:
            flash("Invalid budget id", "danger")
            return redirect(url_for("home"))

        doc = db.monthly_budgets.find_one(_ensure_owner({"_id": oid}))
        if not doc:
            flash("Budget not found or not authorized", "danger")
            return redirect(url_for("home"))

        if request.method == "POST":
            try:
                budget = float(request.form["budget"])
                if budget <= 0:
                    flash("Budget must be positive", "danger")
                    return redirect(url_for("edit_monthly_budget", budget_id=budget_id))
            except Exception:
                flash("Invalid budget value", "danger")
                return redirect(url_for("edit_monthly_budget", budget_id=budget_id))

            month = int(request.form.get("month", doc.get("month")))
            year = int(request.form.get("year", doc.get("year")))
            notes = request.form.get("notes", doc.get("notes", ""))

            update = {
                "budget": budget,
                "month": month,
                "year": year,
                "notes": notes,
                "modified_at": datetime.datetime.utcnow(),
            }

            db.monthly_budgets.update_one(_ensure_owner({"_id": oid}), {"$set": update})
            flash("Budget updated", "success")
            return redirect(url_for("home"))

        return render_template("edit_monthly_budget.html", budget=doc)

    
    @app.route("/monthly_budget/delete/<budget_id>", methods=["POST"])
    @login_required
    def delete_monthly_budget(budget_id):
        oid = _safe_objectid(budget_id)
        if not oid:
            return jsonify({"error": "invalid id"}), 400
        res = db.monthly_budgets.delete_one(_ensure_owner({"_id": oid}))
        if res.deleted_count:
            return redirect(url_for("home"))
        return jsonify({"error": "not found or unauthorized"}), 404
    
    @app.route("/monthly_budget/get/<int:month>/<int:year>")
    @login_required
    def get_monthly_budget(month, year):
        doc = db.monthly_budgets.find_one(_ensure_owner({"month": month, "year": year}))
        if not doc:
            return jsonify({"found": False}), 404
        # compute spent and remaining
        spent = db.plans.aggregate([
            {"$match": {"user_id": _user_id(), "month": month, "year": year}},
            {"$group": {"_id": None, "spent": {"$sum": "$actual_expense"}}}
        ])
        spent_amount = 0.0
        for row in spent:
            spent_amount = row.get("spent", 0.0) or 0.0

        remaining = doc["budget"] - spent_amount
        doc_out = {
            "budget_id": str(doc["_id"]),
            "budget": doc["budget"],
            "month": doc["month"],
            "year": doc["year"],
            "notes": doc.get("notes", ""),
            "spent": spent_amount,
            "remaining": remaining
        }
        return jsonify(doc_out)

    @app.route("/monthly_budget/get/<int:month>/<int:year>")
    @login_required
    def get_monthly_budget(month, year):
        doc = db.monthly_budgets.find_one(_ensure_owner({"month": month, "year": year}))
        if not doc:
            return jsonify({"found": False}), 404
        # compute spent and remaining
        spent = db.plans.aggregate([
            {"$match": {"user_id": _user_id(), "month": month, "year": year}},
            {"$group": {"_id": None, "spent": {"$sum": "$actual_expense"}}}
        ])
        spent_amount = 0.0
        for row in spent:
            spent_amount = row.get("spent", 0.0) or 0.0

        remaining = doc["budget"] - spent_amount
        doc_out = {
            "budget_id": str(doc["_id"]),
            "budget": doc["budget"],
            "month": doc["month"],
            "year": doc["year"],
            "notes": doc.get("notes", ""),
            "spent": spent_amount,
            "remaining": remaining
        }
        return jsonify(doc_out)
    
    ##############
    # BUDGET INSIGHT ROUTES
    ##############

    @app.route("/budget/summary/<int:month>/<int:year>")
    @login_required
    def budget_summary(month, year):
        """
        Compute spent and remaining based on user's plans and the monthly budget (if exists).
        Returns JSON summary.
        """
        # total spent for that month/year
        agg = list(db.plans.aggregate([
            {"$match": {"user_id": _user_id(), "month": month, "year": year}},
            {"$group": {"_id": None, "spent": {"$sum": "$actual_expense"}}}
        ]))
        spent_amount = agg[0]["spent"] if agg and agg[0].get("spent") else 0.0

        mb = db.monthly_budgets.find_one(_ensure_owner({"month": month, "year": year}))
        budget_value = mb["budget"] if mb else None
        remaining = (budget_value - spent_amount) if (budget_value is not None) else None

        return jsonify({
            "month": month,
            "year": year,
            "spent": spent_amount,
            "budget": budget_value,
            "remaining": remaining
        })

    ##############
    # Misc: API to list a user's budgets or plans (for front-end listing)
    ##############

    @app.route("/api/plans", methods=["GET"])
    @login_required
    def api_list_plans():
        cursor = db.plans.find(_ensure_owner({})).sort("created_at", -1)
        out = []
        for p in cursor:
            p["_id"] = str(p["_id"])
            p["user_id"] = str(p["user_id"])
            out.append(p)
        return jsonify(out)

    @app.route("/api/budgets", methods=["GET"])
    @login_required
    def api_list_budgets():
        cursor = db.monthly_budgets.find(_ensure_owner({})).sort([("year", -1), ("month", -1)])
        out = []
        for b in cursor:
            b["_id"] = str(b["_id"])
            b["user_id"] = str(b["user_id"])
            out.append(b)
        return jsonify(out)

    return app

app = create_app()

if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")

    app.run(port=FLASK_PORT)