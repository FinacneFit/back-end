from django.urls import path
from . import views

urlpatterns = [
    path('questions/', views.QuestionListView.as_view()),
    path('submit/', views.SubmitView.as_view()),
]
