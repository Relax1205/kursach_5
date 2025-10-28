# core/views.py
from .services import get_monthly_summary, get_expense_breakdown_by_category, get_budget_vs_actual
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import date
from dateutil.relativedelta import relativedelta
from .models import Transaction, Category, Budget
from .forms import TransactionForm, CategoryForm, BudgetForm
from .services import export_transactions_to_csv
from django.http import HttpResponse



@login_required
def transaction_list(request):
    """Список транзакций с фильтрацией по дате и категории."""
    transactions = Transaction.objects.filter(user=request.user)

    # Фильтрация
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

    # Для фильтра — категории пользователя
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
    """Создание новой транзакции."""
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
    """Создание новой категории."""
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
    """Список бюджетов и форма добавления."""
    if request.method == 'POST':
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            # Проверим, не существует ли уже бюджет на этот месяц/категорию
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

    # Текущий и прошлый месяцы
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
    """Отчёты: диаграммы расходов по категориям за текущий месяц."""
    today = date.today()
    start_of_month = today.replace(day=1)
    end_of_month = (start_of_month + relativedelta(months=1)) - relativedelta(days=1)

    # Агрегация расходов по категориям
    expense_data = (
        Transaction.objects.filter(
            user=request.user,
            category__type=Category.EXPENSE,
            date__range=[start_of_month, end_of_month]
        )
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    # Общий доход и расход
    total_income = Transaction.objects.filter(
        user=request.user,
        category__type=Category.INCOME,
        date__range=[start_of_month, end_of_month]
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_expense = Transaction.objects.filter(
        user=request.user,
        category__type=Category.EXPENSE,
        date__range=[start_of_month, end_of_month]
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Подготовка данных для Chart.js
    labels = [item['category__name'] for item in expense_data]
    values = [float(item['total']) for item in expense_data]

    return render(request, 'core/reports.html', {
        'labels': labels,
        'values': values,
        'total_income': total_income,
        'total_expense': total_expense,
        'month': start_of_month.strftime('%B %Y'),
    })


@login_required
def reports_view(request):
    """Отчёты: диаграммы и сводка за текущий месяц."""
    today = date.today()
    year, month = today.year, today.month

    # Используем сервисы
    summary = get_monthly_summary(request.user, year, month)
    expense_data = get_expense_breakdown_by_category(request.user, year, month)
    budget_comparison = get_budget_vs_actual(request.user, year, month)

    # Подготовка для Chart.js
    labels = [item['category__name'] for item in expense_data]
    values = [float(item['total']) for item in expense_data]

    return render(request, 'core/reports.html', {
        'labels': labels,
        'values': values,
        'summary': summary,
        'budget_comparison': budget_comparison,
        'current_month': f"{today.strftime('%B')} {year}",
    })