from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include([
        path('', include('accounts.urls')),
        path('survey/', include('survey.urls')),
        path('stocks/', include('stocks.urls')),
        path('portfolio/', include('portfolio.urls')),
        path('community/', include('community.urls')),
        path('chat/', include('chat.urls')),
    ])),
]
