# Web Application Exercise

A little exercise to build a web application following an agile development process. See the [instructions](instructions.md) for more detail.

## Product vision statement

Our app empowers users to plan and track spending on mobile quickly and clearly by showing **planned vs. actual** amounts per category, so they can make smarter day-to-day money decisions.

## User stories
- [Full Project Backlog (Issues)](https://github.com/nyu-software-engineering/flask-pymongo-web-app-example.git)

1. **View planned spending**
   - As a user, I want to see my **planned spending list** so that I can review my budget.
   - **Acceptance Criteria**
     - [ ] List reads from the `plans` collection
     - [ ] Shows category, amount, date, note
     - [ ] Sorted by date (newest first)

2. **View actual spending**
   - As a user, I want to see my **actual spending list** so that I can track expenses vs. plan.
   - **Acceptance Criteria**
     - [ ] List reads from the `expenses` collection
     - [ ] Shows category, amount, date, note
     - [ ] Each item has links to **Edit** and **Delete**

3. **Add a planned item**
   - As a user, I want to **add a planned expense** so that I can record my future budget items.
   - **Acceptance Criteria**
     - [ ] Form: category, amount, date, note
     - [ ] On submit, record is saved to `plans`
     - [ ] Redirect to planned list with success message

4. **Add an actual expense**
   - As a user, I want to **add an actual expense** so that I can log real spending.
   - **Acceptance Criteria**
     - [ ] Form: category, amount, date, note
     - [ ] Amount must be a non-negative number
     - [ ] On submit, record is saved to `expenses`

5. **Edit an actual expense**
   - As a user, I want to **edit an actual expense** so that I can correct mistakes.
   - **Acceptance Criteria**
     - [ ] Edit page pre-fills existing values
     - [ ] Saves changes to `expenses` and updates timestamp
     - [ ] Returns to the actual list

6. **Delete a record**
   - As a user, I want to **delete a wrong record** so that my data stays accurate.
   - **Acceptance Criteria**
     - [ ] Delete confirmation screen
     - [ ] After confirm, item is removed (plan or expense)
     - [ ] Redirect back to the corresponding list

7. **Search actual by category**
   - As a user, I want to **search my actual expenses by category** so that I can analyze spending patterns.
   - **Acceptance Criteria**
     - [ ] Search input for category (case-insensitive)
     - [ ] Results show only matching items from `expenses`
     - [ ] Empty search shows all items

8. **Mobile-first UI**
   - As a user, I want the app to be **easy to use on my phone** so that I can add/see expenses on the go.
   - **Acceptance Criteria**
     - [ ] Single-column card layout
     - [ ] Forms use large touch-friendly inputs/buttons
     - [ ] No horizontal scrolling required

9. **Run locally with .env**
   - As a teammate, I want **clear setup steps** so that anyone can run the app locally.
   - **Acceptance Criteria**
     - [ ] `README.md` includes clone, venv, install, run steps
     - [ ] `env.example` shows required variables (`MONGO_URI`, `SECRET_KEY`)
     - [ ] `.env` is ignored by git

### Sprint 2 (Nice-to-have / Extensions)
10. **Filter by month**
    - As a user, I want to **filter by month** so that I can focus on one period at a time.
    - **Acceptance Criteria**
      - [ ] Month selector filters both lists
      - [ ] Default = current month

11. **Category totals (summary)**
    - As a user, I want to see **totals per category** so that I can compare planned vs. actual quickly.
    - **Acceptance Criteria**
      - [ ] Aggregation over `plans` and `expenses`
      - [ ] Show planned, actual, and difference per category

12. **Basic input validation**
    - As a user, I want **safe inputs** so that invalid entries are prevented.
    - **Acceptance Criteria**
      - [ ] Amount must be numeric and ≥ 0
      - [ ] Date must be valid ISO date
      - [ ] Category must be from the allowed list (e.g., Food, Rent, Transit, Entertainment, Utilities, Other)


## Steps necessary to run the software

See instructions. Delete this line and place instructions to download, configure, and run the software here.

## Task boards

- [Sprint 1 Board](https://github.com/orgs/swe-students-fall2025/projects/7/views/1)
- [Sprint 2 Board](https://github.com/orgs/swe-students-fall2025/projects/20/views/1)
