from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("income/add/", views.add_income_view, name="add_income"),
    path("expense/add/", views.add_expense_view, name="add_expense"),
    path("categories/", views.categories_view, name="categories"),
    path("categories/add/", views.category_add_view, name="category_add"),
    path("transactions/", views.transactions_list_view, name="transactions"),
    path("transactions/<int:pk>/edit/", views.transaction_edit_view, name="transaction_edit"),
    path("transactions/<int:pk>/delete/", views.transaction_delete_view, name="transaction_delete"),
    path("transactions/export/csv/", views.export_transactions_csv_view, name="export_transactions_csv"),
    path("transactions/export/xlsx/", views.export_transactions_xlsx_view, name="export_transactions_xlsx"),
    path("transactions/export/pdf/", views.export_transactions_pdf_view, name="export_transactions_pdf"),
    path("budgets/", views.budgets_view, name="budgets"),
    path("budgets/add/", views.budget_add_view, name="budget_add"),
    path("budgets/<int:pk>/edit/", views.budget_edit_view, name="budget_edit"),
    path("budgets/<int:pk>/delete/", views.budget_delete_view, name="budget_delete"),
    path("charts/", views.charts_view, name="charts"),
    path("compare/", views.compare_view, name="compare"),
    path("goals/", views.savings_goals_view, name="savings_goals"),
    path("goals/add/", views.savings_goal_add_view, name="savings_goal_add"),
    path("goals/<int:pk>/edit/", views.savings_goal_edit_view, name="savings_goal_edit"),
    path("goals/<int:pk>/add-funds/", views.savings_goal_add_funds_view, name="savings_goal_add_funds"),
    path("goals/<int:pk>/delete/", views.savings_goal_delete_view, name="savings_goal_delete"),
    path("activity/", views.activity_log_view, name="activity_log"),

]
