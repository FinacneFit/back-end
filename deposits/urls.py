from django.urls import path
from .views import DepositListView, DepositRefreshView

urlpatterns = [
    path('',         DepositListView.as_view()),
    path('refresh/', DepositRefreshView.as_view()),
]
