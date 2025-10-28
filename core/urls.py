# core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.transaction_list, name='transaction_list'),
    path('transaction/add/', views.transaction_create, name='transaction_create'),
    path('category/add/', views.category_create, name='category_create'),
    path('budgets/', views.budget_list, name='budget_list'),
    path('reports/', views.reports_view, name='reports'),
    path('export/csv/', views.export_csv, name='export_csv'),
]