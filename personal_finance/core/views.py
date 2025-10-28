# core/views.py
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from datetime import date
from dateutil.relativedelta import relativedelta
from django.http import HttpResponse

import csv
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib import messages
from django.http import HttpResponseRedirect
from .services import import_transactions_from_csv

from .models import Transaction, Category, Budget
from .forms import TransactionForm, CategoryForm, BudgetForm
from .services import (
    get_monthly_summary,
    get_expense_breakdown_by_category,
    get_budget_vs_actual,
    export_transactions_to_csv,
    import_transactions_from_csv
)


@login_required
def transaction_list(request):
    transactions = Transaction.objects.filter(user=request.user)
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    category_id = request.GET.get('category')

    if start_date:
        transactions = transactions.filter(date__gte=start_date)
    if end_date:
        transactions = transactions.filter(date__lte=end_date)
    if category_id:
        transactions = transactions.filter(category_id=category_id)

    transactions = transactions.select_related('category')
    categories = Category.objects.filter(user=request.user)

    return render(request, 'core/transaction_list.html', {
        'transactions': transactions,
        'categories': categories,
        'start_date': start_date,
        'end_date': end_date,
        'selected_category': category_id,
    })


@login_required
def transaction_create(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()
            messages.success(request, 'Транзакция добавлена.')
            return redirect('transaction_list')
    else:
        form = TransactionForm(user=request.user)
    return render(request, 'core/transaction_form.html', {'form': form, 'title': 'Добавить транзакцию'})


@login_required
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, 'Категория создана.')
            return redirect('transaction_create')
    else:
        form = CategoryForm()
    return render(request, 'core/transaction_form.html', {'form': form, 'title': 'Создать категорию'})


@login_required
def budget_list(request):
    if request.method == 'POST':
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            existing = Budget.objects.filter(
                user=request.user,
                category=budget.category,
                month=budget.month
            ).first()
            if existing:
                existing.amount = budget.amount
                existing.save()
                messages.success(request, 'Бюджет обновлён.')
            else:
                budget.save()
                messages.success(request, 'Бюджет установлен.')
            return redirect('budget_list')
    else:
        form = BudgetForm(user=request.user)

    today = date.today()
    current_month = today.replace(day=1)
    last_month = current_month - relativedelta(months=1)

    budgets = Budget.objects.filter(
        user=request.user,
        month__in=[last_month, current_month]
    ).select_related('category')

    return render(request, 'core/budget_list.html', {
        'form': form,
        'budgets': budgets,
        'current_month': current_month,
        'last_month': last_month,
    })


@login_required
def reports_view(request):
    today = date.today()
    year, month = today.year, today.month

    summary = get_monthly_summary(request.user, year, month)
    expense_data = get_expense_breakdown_by_category(request.user, year, month)
    budget_comparison = get_budget_vs_actual(request.user, year, month)

    labels = [item['category__name'] for item in expense_data]
    values = [float(item['total']) for item in expense_data]

    return render(request, 'core/reports.html', {
        'labels': labels,
        'values': values,
        'summary': summary,
        'budget_comparison': budget_comparison,
        'current_month': f"{today.strftime('%B')} {year}",
    })


# === ЭКСПОРТ CSV — ОБЯЗАТЕЛЬНАЯ ФУНКЦИЯ ===
@login_required
def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
    export_transactions_to_csv(response, request.user)
    return response

@login_required
def import_csv(request):
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, 'Файл не выбран.')
            return render(request, 'core/import_csv.html')
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Только CSV-файлы разрешены.')
            return render(request, 'core/import_csv.html')
        try:
            count = import_transactions_from_csv(csv_file, request.user)
            messages.success(request, f'Успешно импортировано {count} транзакций.')
            return redirect('transaction_list')
        except Exception as e:
            messages.error(request, f'Ошибка при импорте: {str(e)}')
            return render(request, 'core/import_csv.html')
    return render(request, 'core/import_csv.html')

@login_required
def transaction_delete(request, pk):
    """Удаление транзакции с подтверждением."""
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
    
    if request.method == 'POST':
        transaction.delete()
        messages.success(request, 'Транзакция удалена.')
        return redirect('transaction_list')
    
    # Если GET — показать страницу подтверждения
    return render(request, 'core/transaction_confirm_delete.html', {'transaction': transaction})