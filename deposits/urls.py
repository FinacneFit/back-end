from django.urls import path

from .views import (
    DepositListView,
    DepositRefreshView,
    DepositSaveView,
    SavedDepositListView,
    SavedDepositDeleteView,
)

urlpatterns = [
    path('', DepositListView.as_view()),
    path('refresh/', DepositRefreshView.as_view()),
    path('save/', DepositSaveView.as_view()),
    path('saved/', SavedDepositListView.as_view()),
    path('saved/<int:product_id>/', SavedDepositDeleteView.as_view()),
]