from django.conf import settings
from django.db import models

class Category(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=50)
    icon = models.CharField(max_length=10, blank=True, default="")
    color = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        unique_together = ("user", "name")
        ordering = ["name"]

    def __str__(self):
        return self.name

class Transaction(models.Model):
    INCOME = "income"
    EXPENSE = "expense"
    TYPE_CHOICES = [(INCOME, "Income"), (EXPENSE, "Expense")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    note = models.CharField(max_length=120, blank=True, default="")

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.user} - {self.type} - {self.amount}"

from django.conf import settings
from django.db import models

class BudgetLimit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budget_limits")
    category = models.ForeignKey("Category", on_delete=models.CASCADE, related_name="budget_limits")

    month = models.DateField()
    limit = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "category", "month")
        ordering = ["-month", "category__name"]

    def __str__(self):
        return f"{self.user} {self.category} {self.month} {self.limit}"
