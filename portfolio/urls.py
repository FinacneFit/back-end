from django.urls import path
from . import views

urlpatterns = [
    path('', views.PortfolioView.as_view()),
    path('holdings/', views.HoldingListCreateView.as_view()),
    path('holdings/<int:holding_id>/', views.HoldingDetailView.as_view()),
]
