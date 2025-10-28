# core/forms.py
from django import forms
from django.contrib.auth.models import User
from .models import Transaction, Category, Budget
from django.core.exceptions import ValidationError 
from django.utils import timezone
from datetime import date


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['amount', 'category', 'description', 'date']
        widgets = { ... }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(user=user)

    # ДОБАВЬТЕ ЭТОТ МЕТОД
    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError('Сумма должна быть положительной.')
        return amount

class CategoryForm(forms.ModelForm):
    """Форма для создания категории."""
    class Meta:
        model = Category
        fields = ['name', 'type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
        }


class BudgetForm(forms.ModelForm):
    """Форма для установки месячного бюджета."""
    class Meta:
        model = Budget
        fields = ['category', 'amount', 'month']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'month': forms.DateInput(attrs={'type': 'month', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        # Только категории расходов (бюджет обычно на расходы)
        self.fields['category'].queryset = Category.objects.filter(user=user, type=Category.EXPENSE)

    def clean_month(self):
        """Приводим дату к первому числу месяца."""
        month = self.cleaned_data['month']
        if month:
            return month.replace(day=1)
        return month