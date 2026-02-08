# MyBudget

A modern personal finance and budgeting web application built with Django.  
MyBudget helps users track income and expenses, manage categories, set monthly budget limits, and visualize spending trends through interactive charts.

**Live demo:** https://my-budget-or3r.onrender.com/ 

---

## Overview

MyBudget is designed as a clean, user-friendly budgeting tool with a modern dark UI.  
It focuses on clarity, usability, and essential personal finance features without unnecessary complexity.

---

## Key Features

- Secure user authentication (register, login, logout)
- Dashboard with income, expenses, and balance overview
- Income and expense transaction management
- Category management with icons and colors
- Monthly budget limits per category
- Visual budget progress indicators (on track / over budget)
- Interactive charts for spending analysis
- Responsive design with a modern glass-style interface
- Multi-currency support

---

## Technology Stack

- **Backend:** Django
- **Database:** PostgreSQL (production), SQLite (development)
- **Frontend:** Django Templates, HTML5, CSS3
- **Charts:** Chart.js
- **Deployment:** Render

---

## Local Installation

### Prerequisites
- Python 3.10+
- pip
- virtualenv (recommended)

### Setup Steps

1. Clone the repository
```bash
git clone https://github.com/your-username/mybudget.git
cd mybudget
```

2. Create and activate a virtual environment
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Apply database migrations
```bash
python manage.py migrate
```

5. (Optional) Create an admin user
```bash
python manage.py createsuperuser
```

6. Run the development server
```bash
python manage.py runserver
```

Open your browser at: http://127.0.0.1:8000/

---

## Usage

1. Create an account or log in
2. Define categories for income and expenses
3. Add transactions
4. Set monthly budget limits per category
5. Monitor progress and review charts

---

## Deployment

The application is deployed on **Render** and configured for production use with PostgreSQL.

---

## Security Notice

This application is intended for educational and personal projects.  
Avoid using real banking or sensitive financial data.

---

