from django.urls import path
from . import views

urlpatterns = [
    path('recommended/', views.RecommendedStocksView.as_view()),
    path('search/', views.StockSearchView.as_view()),
]
