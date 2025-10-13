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

    @app.route("/")
    def home():
        """
        Route for the home page.
        Returns:
            rendered template (str): The rendered HTML template.
        """
        plans = db.plans.find({}).sort("created_at", -1)
        return render_template("index.html", plans=plans)

    @app.route("/create", methods=["POST"])
    def create_plan():
        """
        Route for POST requests to the create page.
        Accepts the form submission data for a new plan and saves the document to the database.
        Returns:
            redirect (Response): A redirect response to the home page.
        """
        planned_expense = float(request.form["planned_expense"])
        actual_expense = float(request.form.get("actual_expense", 0))
        day = int(request.form["day"])
        month = int(request.form["month"])
        year = int(request.form["year"])
        category = request.form["category"]
        notes = request.form.get("notes", "")

        doc = {
            "planned_expense": planned_expense,
            "actual_expense": actual_expense,
            "day": day,
            "month": month,
            "year": year,
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
        planned_expense = float(request.form["planned_expense"])
        actual_expense = float(request.form.get("actual_expense", 0))
        day = int(request.form["day"])
        month = int(request.form["month"])
        year = int(request.form["year"])
        category = request.form["category"]
        notes = request.form.get("notes", "")

        doc = {
            "planned_expense": planned_expense,
            "actual_expense": actual_expense,
            "day": day,
            "month": month,
            "year": year,
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

    return app



app = create_app()

if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")

    app.run(port=FLASK_PORT)