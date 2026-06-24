from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include([
        path('', include('accounts.urls')),
        path('survey/', include('survey.urls')),
        path('stocks/', include('stocks.urls')),
        path('portfolio/', include('portfolio.urls')),
        path('community/', include('community.urls')),
        path('chat/', include('chat.urls')),
        path('deposits/', include('deposits.urls')),
    ])),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
