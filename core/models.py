from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Category(models.Model):
    """Категория дохода или расхода. Привязана к пользователю."""
    INCOME = 'income'
    EXPENSE = 'expense'
    TYPE_CHOICES = [
        (INCOME, 'Доход'),
        (EXPENSE, 'Расход'),
    ]

    name = models.CharField('Название', max_length=100)
    type = models.CharField('Тип', max_length=10, choices=TYPE_CHOICES, default=EXPENSE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        unique_together = ('name', 'user', 'type')

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"


class Transaction(models.Model):
    """Финансовая транзакция: доход или расход."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField('Сумма', max_digits=12, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name='Категория')
    description = models.CharField('Описание', max_length=255, blank=True)
    date = models.DateField('Дата', default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.category} — {self.amount} ({self.date})"


class Budget(models.Model):
    """Ежемесячный бюджет по категории."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    amount = models.DecimalField('Лимит', max_digits=12, decimal_places=2)
    month = models.DateField('Месяц', help_text='Укажите первый день месяца (напр., 2025-10-01)')

    class Meta:
        verbose_name = 'Бюджет'
        verbose_name_plural = 'Бюджеты'
        unique_together = ('user', 'category', 'month')

    def __str__(self):
        return f"{self.category} — {self.amount} ({self.month.strftime('%Y-%m')})"