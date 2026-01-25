from calendar import monthrange
from decimal import Decimal
from .models import BudgetLimit
from .forms import BudgetLimitForm
from django.contrib.auth.decorators import login_required

from datetime import date
from calendar import monthrange
from datetime import date
from django.db import models
from django.db.models import Sum
from django.db.models.functions import TruncMonth


@login_required
def dashboard_view(request):
    return render(request, "dashboard.html")


@login_required
def dashboard_view(request):
    transactions = Transaction.objects.filter(user=request.user)

    total_income = transactions.filter(type=Transaction.INCOME).aggregate(Sum("amount"))["amount__sum"] or 0
    total_expense = transactions.filter(type=Transaction.EXPENSE).aggregate(Sum("amount"))["amount__sum"] or 0
    balance = total_income - total_expense

    last_transactions = transactions.order_by("-date")[:5]

    context = {
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": balance,
        "transactions": last_transactions,
        "currency": request.user.currency,
    }

    return render(request, "dashboard.html", context)



@login_required
def add_income_view(request):
    categories = Category.objects.filter(user=request.user)

    if request.method == "POST":
        Transaction.objects.create(
            user=request.user,
            type=Transaction.INCOME,
            amount=request.POST["amount"],
            date=request.POST["date"],
            note=request.POST.get("note", ""),
            category_id=request.POST["category"]
        )
        return redirect("dashboard")

    return render(request, "income_add.html", {"categories": categories})


@login_required
def add_expense_view(request):
    categories = Category.objects.filter(user=request.user)

    if request.method == "POST":
        Transaction.objects.create(
            user=request.user,
            type=Transaction.EXPENSE,
            amount=request.POST["amount"],
            date=request.POST["date"],
            note=request.POST.get("note", ""),
            category_id=request.POST["category"]
        )
        return redirect("dashboard")

    return render(request, "expense_add.html", {"categories": categories})

from django.contrib import messages

@login_required
def categories_view(request):
    cats = Category.objects.filter(user=request.user).order_by("name")
    return render(request, "categories.html", {"categories": cats})

@login_required
def category_add_view(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        icon = request.POST.get("icon", "").strip()
        color = request.POST.get("color", "").strip()

        if not name:
            messages.error(request, "Category name is required.")
            return render(request, "category_add.html")

        Category.objects.create(user=request.user, name=name, icon=icon, color=color)
        messages.success(request, "Category created!")
        return redirect("categories")

    return render(request, "category_add.html")

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TransactionForm
from .models import Category, Transaction


@login_required
def transactions_list_view(request):
    qs = Transaction.objects.filter(user=request.user).select_related("category")

    # Filters from GET
    t_type = request.GET.get("type", "").strip()         # income/expense
    cat_id = request.GET.get("category", "").strip()     # category id
    date_from = request.GET.get("from", "").strip()      # YYYY-MM-DD
    date_to = request.GET.get("to", "").strip()          # YYYY-MM-DD

    if t_type in (Transaction.INCOME, Transaction.EXPENSE):
        qs = qs.filter(type=t_type)

    if cat_id.isdigit():
        qs = qs.filter(category_id=int(cat_id))

    if date_from:
        qs = qs.filter(date__gte=date_from)

    if date_to:
        qs = qs.filter(date__lte=date_to)

    total_income = qs.filter(type=Transaction.INCOME).aggregate(Sum("amount"))["amount__sum"] or 0
    total_expense = qs.filter(type=Transaction.EXPENSE).aggregate(Sum("amount"))["amount__sum"] or 0
    balance = total_income - total_expense

    categories = Category.objects.filter(user=request.user).order_by("name")

    context = {
        "transactions": qs[:200],  # limit for now (later pagination)
        "categories": categories,
        "filters": {"type": t_type, "category": cat_id, "from": date_from, "to": date_to},
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": balance,
        "currency": request.user.currency,
    }
    return render(request, "transactions_list.html", context)


@login_required
def transaction_edit_view(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)

    if request.method == "POST":
        form = TransactionForm(request.POST, instance=tx, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Transaction updated.")
            return redirect("transactions")
    else:
        form = TransactionForm(instance=tx, user=request.user)

    return render(request, "transaction_form.html", {"form": form, "tx": tx})


@login_required
def transaction_delete_view(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)

    if request.method == "POST":
        tx.delete()
        messages.success(request, "Transaction deleted.")
        return redirect("transactions")

    return render(request, "transaction_confirm_delete.html", {"tx": tx})


def _month_start(d: date) -> date:
    return d.replace(day=1)

def _month_end(d: date) -> date:
    last_day = monthrange(d.year, d.month)[1]
    return d.replace(day=last_day)


@login_required
def budgets_view(request):
    # month picker: expects YYYY-MM-DD (we use first day)
    month_str = request.GET.get("month", "").strip()
    if month_str:
        try:
            selected = date.fromisoformat(month_str)
        except ValueError:
            selected = date.today()
    else:
        selected = date.today()

    month_start = _month_start(selected)
    month_end = _month_end(selected)

    categories = Category.objects.filter(user=request.user).order_by("name")

    # total spent per category in this month (expenses only)
    spent_map = {
        row["category_id"]: (row["total"] or Decimal("0"))
        for row in (
            Transaction.objects.filter(
                user=request.user,
                type=Transaction.EXPENSE,
                date__gte=month_start,
                date__lte=month_end,
            )
            .values("category_id")
            .annotate(total=Sum("amount"))
        )
    }

    limits = BudgetLimit.objects.filter(user=request.user, month=month_start).select_related("category")
    limit_map = {b.category_id: b for b in limits}

    rows = []
    for c in categories:
        spent = spent_map.get(c.id, Decimal("0"))
        b = limit_map.get(c.id)
        limit_val = b.limit if b else None

        if limit_val and limit_val > 0:
            pct = (spent / limit_val) * 100
            pct_int = int(min(pct, 999))  # cap for UI
        else:
            pct_int = 0

        rows.append({
            "category": c,
            "spent": spent,
            "limit": limit_val,
            "pct": pct_int,
            "budget": b,
            "is_over": (limit_val is not None and spent > limit_val),
        })

    total_spent = sum((r["spent"] for r in rows), Decimal("0"))
    total_limit = sum((r["limit"] for r in rows if r["limit"] is not None), Decimal("0"))

    return render(request, "budgets.html", {
        "rows": rows,
        "month": month_start,
        "currency": request.user.currency,
        "total_spent": total_spent,
        "total_limit": total_limit,
    })


@login_required
def budget_add_view(request):
    if request.method == "POST":
        form = BudgetLimitForm(request.POST, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.month = _month_start(obj.month)  # normalize
            obj.save()
            messages.success(request, "Budget limit saved.")
            return redirect("budgets")
    else:
        form = BudgetLimitForm(user=request.user, initial={"month": date.today().replace(day=1)})

    return render(request, "budget_form.html", {"form": form, "mode": "add"})


@login_required
def budget_edit_view(request, pk):
    b = get_object_or_404(BudgetLimit, pk=pk, user=request.user)

    if request.method == "POST":
        form = BudgetLimitForm(request.POST, instance=b, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.month = _month_start(obj.month)
            obj.save()
            messages.success(request, "Budget limit updated.")
            return redirect("budgets")
    else:
        form = BudgetLimitForm(instance=b, user=request.user)

    return render(request, "budget_form.html", {"form": form, "mode": "edit", "budget": b})


@login_required
def budget_delete_view(request, pk):
    b = get_object_or_404(BudgetLimit, pk=pk, user=request.user)

    if request.method == "POST":
        b.delete()
        messages.success(request, "Budget limit deleted.")
        return redirect("budgets")

    return render(request, "budget_confirm_delete.html", {"budget": b})

@login_required
def charts_view(request):
    # PIE: current month expenses by category
    today = date.today()
    month_start = today.replace(day=1)
    last_day = monthrange(today.year, today.month)[1]
    month_end = today.replace(day=last_day)

    pie_rows = (
        Transaction.objects.filter(
            user=request.user,
            type=Transaction.EXPENSE,
            date__gte=month_start,
            date__lte=month_end,
        )
        .values("category__name", "category__color", "category__icon")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    pie_labels, pie_values, pie_colors = [], [], []
    for r in pie_rows:
        icon = r["category__icon"] or "🏷️"
        name = r["category__name"] or "Other"
        pie_labels.append(f"{icon} {name}".strip())
        pie_values.append(float(r["total"] or 0))
        pie_colors.append(r["category__color"] or "#6366f1")

    # LINE: income vs expense by month
    monthly = (
        Transaction.objects.filter(user=request.user)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(
            income=Sum("amount", filter=models.Q(type=Transaction.INCOME)),
            expense=Sum("amount", filter=models.Q(type=Transaction.EXPENSE)),
        )
        .order_by("month")
    )

    chart_labels, chart_income, chart_expense = [], [], []
    for m in monthly:
        if m["month"]:
            chart_labels.append(m["month"].strftime("%b %Y"))
            chart_income.append(float(m["income"] or 0))
            chart_expense.append(float(m["expense"] or 0))

    return render(request, "charts.html", {
        "currency": request.user.currency,
        "month_label": month_start.strftime("%b %Y"),
        "pie_labels": pie_labels,
        "pie_values": pie_values,
        "pie_colors": pie_colors,
        "chart_labels": chart_labels,
        "chart_income": chart_income,
        "chart_expense": chart_expense,
    })
