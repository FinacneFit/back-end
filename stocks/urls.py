from django.urls import path
from . import views

urlpatterns = [
    path('stats/',       views.StockStatsView.as_view()),
    path('recommended/', views.RecommendedStocksView.as_view()),
    path('search/',      views.StockSearchView.as_view()),
]
