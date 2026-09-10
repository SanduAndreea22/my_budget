# MyBudget

Know exactly where your money went, without opening a spreadsheet. MyBudget tracks income and expenses across multiple wallets, flags category budgets before you blow past them, and logs recurring bills automatically — built with Django, with a modern dark glass-style UI.

**Live demo:** https://my-budget-or3r.onrender.com
*(hosted on Render's free tier — the first request after inactivity can take 30-50s to wake up)*

---

## Key Features

**Money tracking**
- Multiple wallets (e.g. cash, bank, savings), each with its own balance
- Custom categories with icons and colors, for income and expenses separately
- Full transaction history — filter, edit, delete
- **Recurring transactions**: set up a transaction once (rent, salary, a subscription) and it repeats automatically
- **Savings goals**: set a target amount, add funds toward it over time, track progress

**Budgeting & insight**
- Monthly budget limits per category, with visual on-track/over-budget indicators
- Interactive charts (Chart.js) for spending breakdown and trends
- Month-to-month comparison view
- Multi-currency support

**Exports & accountability**
- Export transactions as **CSV, Excel (.xlsx), or PDF** (PDF rendered server-side with WeasyPrint)
- Activity log — an audit trail of account actions

**Account**
- Registration with a welcome/activation email (Resend API, best-effort — accounts are usable immediately regardless of email delivery)
- Rate-limited login/register (best-effort, per-IP, via cache) against scripted abuse
- Profile with a custom avatar upload

## Tech stack

- **Backend:** Django 6
- **Database:** PostgreSQL (production), SQLite (local dev)
- **Charts:** Chart.js
- **Exports:** openpyxl (Excel), WeasyPrint (PDF)
- **Email:** Resend API
- **Static files:** WhiteNoise
- **Testing:** 86 tests across `accounts`/`budget`
- **Containerization:** Dockerfile; GitHub Actions builds and publishes the image to GHCR (`ghcr.io/sanduandreea22/my-budget`) on every push to `main`
- **Hosting:** Render

## Architecture

Three apps, split by responsibility:

| App | Responsibility |
|---|---|
| `accounts` | Custom user model (email-unique, avatar upload), registration/login, rate limiting |
| `budget` | Wallets, categories, transactions, recurring transactions, budget limits, savings goals, exports, activity log |
| `pages` | Public/marketing pages |

Core models: `Wallet`, `Category`, `Transaction`, `RecurringTransaction`, `BudgetLimit`, `SavingsGoal`, `ActivityLog`.

## Running locally

```bash
git clone https://github.com/SanduAndreea22/my_budget.git
cd my_budget
python -m venv venv
venv\Scripts\activate        # or: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # fill in your own values
python manage.py migrate
python manage.py runserver
```

`RESEND_API_KEY` is optional for local dev — without it, registration still works, the email attempt just logs an error to the console instead of sending.

Run the test suite with:

```bash
python manage.py test
```

### Docker

```bash
docker build -t my-budget .
docker run -p 8000:8000 --env-file .env my-budget
```

## Security notice

This application is a portfolio/educational project. Avoid using real banking or sensitive financial data with it.

## 👩‍💻 Author

**Andreea Sandu**
LinkedIn: [linkedin.com/in/andreealuizasandu](https://linkedin.com/in/andreealuizasandu)
GitHub: [@SanduAndreea22](https://github.com/SanduAndreea22)
