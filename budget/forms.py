from django import forms
from django.core.exceptions import ValidationError
from .models import BudgetLimit, Category, RecurringTransaction, SavingsGoal, Transaction, Wallet

class CategoryForm(forms.ModelForm):
    icon = forms.CharField(
        required=False,
        max_length=32,
        widget=forms.TextInput(attrs={"placeholder": "Icon (emoji) e.g. 💼 🍔 (optional)"}),
        error_messages={"max_length": "That icon is too long — try a single emoji instead."},
    )

    class Meta:
        model = Category
        fields = ["name", "icon", "color"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Category name (e.g. Salary, Food)"}),
            "color": forms.TextInput(attrs={"type": "color"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if not self.instance.pk and not self.initial.get("color"):
            self.initial["color"] = "#6366f1"

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise ValidationError("Category name is required.")
        return name

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        if name and self.user is not None:
            qs = Category.objects.filter(user=self.user, name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("name", "You already have a category with this name.")
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.user = self.user
        if commit:
            obj.save()
        return obj

class WalletForm(forms.ModelForm):
    icon = forms.CharField(
        required=False,
        max_length=32,
        widget=forms.TextInput(attrs={"placeholder": "Icon (emoji) e.g. 💳 💵 (optional)"}),
        error_messages={"max_length": "That icon is too long — try a single emoji instead."},
    )

    class Meta:
        model = Wallet
        fields = ["name", "icon"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Wallet name (e.g. Card, Cash, Savings)"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise ValidationError("Wallet name is required.")
        return name

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        if name and self.user is not None:
            qs = Wallet.objects.filter(user=self.user, name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("name", "You already have a wallet with this name.")
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.user = self.user
        if commit:
            obj.save()
        return obj


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["type", "amount", "date", "category", "wallet", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(user=user).order_by("name")
            self.fields["wallet"].queryset = Wallet.objects.filter(user=user).order_by("name")

class BudgetLimitForm(forms.ModelForm):
    month = forms.DateField(
        input_formats=["%Y-%m"],
        widget=forms.DateInput(attrs={"type": "month"}, format="%Y-%m"),
    )

    class Meta:
        model = BudgetLimit
        fields = ["category", "month", "limit"]
        widgets = {
            "limit": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(user=user).order_by("name")


class SavingsGoalForm(forms.ModelForm):
    class Meta:
        model = SavingsGoal
        fields = ["name", "target_amount", "target_date"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Emergency fund, New laptop"}),
            "target_date": forms.DateInput(attrs={"type": "date"}),
            "target_amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def clean_target_amount(self):
        target_amount = self.cleaned_data["target_amount"]
        if target_amount <= 0:
            raise ValidationError("Target amount must be greater than zero.")
        return target_amount


class RecurringTransactionForm(forms.ModelForm):
    class Meta:
        model = RecurringTransaction
        fields = ["type", "amount", "category", "wallet", "day_of_month", "start_date", "note", "is_active"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "day_of_month": forms.NumberInput(attrs={"min": 1, "max": 28}),
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(user=user).order_by("name")
            self.fields["wallet"].queryset = Wallet.objects.filter(user=user).order_by("name")

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        return amount
