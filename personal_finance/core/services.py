# core/services.py
"""
Модуль бизнес-логики приложения управления финансами.
Содержит функции для агрегации данных, экспорта и анализа бюджета.
"""

import csv
from decimal import Decimal
from datetime import date
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
from .models import Transaction, Category, Budget


def get_monthly_summary(user, year, month):
    """
    Возвращает сводку по доходам и расходам за указанный месяц.
    
    Args:
        user (User): Пользователь
        year (int): Год
        month (int): Месяц (1–12)
    
    Returns:
        dict: {'income': Decimal, 'expense': Decimal, 'balance': Decimal}
    """
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    end_date -= date.resolution  # последний день месяца

    income = Transaction.objects.filter(
        user=user,
        category__type=Category.INCOME,
        date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or 0

    expense = Transaction.objects.filter(
        user=user,
        category__type=Category.EXPENSE,
        date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or 0

    return {
        'income': income,
        'expense': expense,
        'balance': income - expense,
    }


def get_expense_breakdown_by_category(user, year, month):
    """
    Возвращает детализацию расходов по категориям за месяц.
    
    Args:
        user (User): Пользователь
        year (int): Год
        month (int): Месяц
    
    Returns:
        QuerySet: [{'category__name': str, 'total': Decimal}, ...]
    """
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    end_date -= date.resolution

    return (
        Transaction.objects.filter(
            user=user,
            category__type=Category.EXPENSE,
            date__range=[start_date, end_date]
        )
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )


def export_transactions_to_csv(response, user):
    """
    Экспортирует все транзакции пользователя в CSV-файл.
    
    Args:
        response (HttpResponse): HTTP-ответ с content_type='text/csv'
        user (User): Пользователь, чьи данные экспортируются
    
    Writes:
        CSV-данные в response.
    """
    writer = csv.writer(response)
    writer.writerow(['Дата', 'Тип', 'Категория', 'Сумма', 'Описание'])

    transactions = Transaction.objects.filter(user=user).select_related('category').order_by('-date')

    for t in transactions:
        writer.writerow([
            t.date.strftime('%Y-%m-%d'),
            'Доход' if t.category.type == Category.INCOME else 'Расход',
            t.category.name,
            t.amount,
            t.description or ''
        ])


def get_budget_vs_actual(user, year, month):
    """
    Сравнивает установленные бюджеты с фактическими расходами за месяц.
    
    Args:
        user (User): Пользователь
        year (int): Год
        month (int): Месяц
    
    Returns:
        list[dict]: Список словарей с ключами:
            - category_name
            - budget_amount
            - actual_amount
            - difference (budget - actual)
            - is_over_budget (bool)
    """
    from dateutil.relativedelta import relativedelta
    start_date = date(year, month, 1)
    end_date = start_date + relativedelta(months=1) - relativedelta(days=1)

    # Получаем все бюджеты на этот месяц
    budgets = Budget.objects.filter(
        user=user,
        month=start_date
    ).select_related('category')

    result = []
    for budget in budgets:
        actual = Transaction.objects.filter(
            user=user,
            category=budget.category,
            date__range=[start_date, end_date]
        ).aggregate(total=Sum('amount'))['total'] or 0

        diff = budget.amount - actual
        result.append({
            'category_name': budget.category.name,
            'budget_amount': budget.amount,
            'actual_amount': actual,
            'difference': diff,
            'is_over_budget': actual > budget.amount,
        })

    return result

def import_transactions_from_csv(file, user):
    """
    Импортирует транзакции из CSV-файла.
    Ожидаемый формат: Дата,Тип,Категория,Сумма,Описание
    """
    import csv
    from io import StringIO
    from decimal import Decimal
    from datetime import date

    # Декодируем файл
    content = file.read().decode('utf-8')
    reader = csv.reader(StringIO(content))
    
    # Пропускаем заголовок
    try:
        next(reader)
    except StopIteration:
        raise ValidationError("Пустой CSV-файл")

    count = 0
    for row in reader:
        # Пропускаем пустые строки
        if not row or all(cell.strip() == '' for cell in row):
            continue
            
        # Убедимся, что есть минимум 4 поля
        if len(row) < 4:
            continue

        date_str = row[0].strip()
        type_str = row[1].strip()
        category_name = row[2].strip()
        amount_str = row[3].strip()
        description = row[4].strip() if len(row) > 4 else ''

        if not date_str or not type_str or not category_name or not amount_str:
            continue

        # Определяем тип
        if type_str == 'Доход':
            cat_type = Category.INCOME
        elif type_str == 'Расход':
            cat_type = Category.EXPENSE
        else:
            raise ValidationError(f'Неизвестный тип операции: {type_str}')

        # Создаём/получаем категорию
        category, created = Category.objects.get_or_create(
            name=category_name,
            type=cat_type,
            user=user
        )

        # Создаём транзакцию
        Transaction.objects.create(
            user=user,
            category=category,
            amount=Decimal(amount_str),
            description=description,
            date=date.fromisoformat(date_str)
        )
        count += 1

    return count