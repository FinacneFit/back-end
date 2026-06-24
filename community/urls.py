from django.urls import path
from . import views

urlpatterns = [
    path('posts/', views.PostListCreateView.as_view()),
    path('posts/my/', views.MyPostListView.as_view()),
    path('posts/<int:post_id>/', views.PostDetailView.as_view()),
    path('posts/<int:post_id>/like/', views.PostLikeView.as_view()),
    path('posts/<int:post_id>/comments/', views.CommentListCreateView.as_view()),
    path('posts/<int:post_id>/comments/<int:comment_id>/replies/', views.CommentReplyCreateView.as_view()),
    path('posts/<int:post_id>/comments/<int:comment_id>/', views.CommentDetailView.as_view()),
]
