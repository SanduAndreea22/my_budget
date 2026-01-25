from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),

    path("income/add/", views.add_income_view, name="add_income"),
    path("expense/add/", views.add_expense_view, name="add_expense"),

    # ✅ categories
    path("categories/", views.categories_view, name="categories"),
    path("categories/add/", views.category_add_view, name="category_add"),

    path("transactions/", views.transactions_list_view, name="transactions"),
    path("transactions/<int:pk>/edit/", views.transaction_edit_view, name="transaction_edit"),
    path("transactions/<int:pk>/delete/", views.transaction_delete_view, name="transaction_delete"),
    path("budgets/", views.budgets_view, name="budgets"),
    path("budgets/add/", views.budget_add_view, name="budget_add"),
path("budgets/<int:pk>/edit/", views.budget_edit_view, name="budget_edit"),
path("budgets/<int:pk>/delete/", views.budget_delete_view, name="budget_delete"),
path("charts/", views.charts_view, name="charts"),


]
