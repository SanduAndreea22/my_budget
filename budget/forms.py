from django import forms
from django.core.exceptions import ValidationError
from .models import Transaction, Category

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "icon", "color"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Category name (e.g. Salary, Food)"}),
            "icon": forms.TextInput(attrs={"placeholder": "Icon (emoji) e.g. 💼 🍔 (optional)"}),
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

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["type", "amount", "date", "category", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(user=user).order_by("name")

from .models import BudgetLimit

class BudgetLimitForm(forms.ModelForm):
    month = forms.DateField(
        input_formats=["%Y-%m"],
        widget=forms.DateInput(attrs={"type": "month"}, format="%Y-%m"),
    )

    class Meta:
        model = BudgetLimit
        fields = ["category", "month", "limit"]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(user=user).order_by("name")
