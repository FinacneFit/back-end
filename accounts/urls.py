from django.urls import path
from . import views

urlpatterns = [
    path('auth/signup/', views.signup),
    path('auth/login/', views.login_view),
    path('auth/logout/', views.logout_view),
    path('users/me/', views.MeView.as_view()),
    path('users/me/followers/', views.FollowersView.as_view()),
    path('users/me/following/', views.FollowingView.as_view()),
    path('users/<int:user_id>/', views.UserDetailView.as_view()),
    path('users/<int:user_id>/follow/', views.FollowView.as_view()),
]
