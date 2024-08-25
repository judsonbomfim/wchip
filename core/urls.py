from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static
from apps.dashboard.views import index, clear_cache

urlpatterns = [
    path('', index, name='dashboard'),
    path('admin/', admin.site.urls),
    path('pedidos/', include('apps.orders.urls')),
    path('sims/', include('apps.sims.urls')),
    path('', include('apps.users.urls')),
    path('email/', include('apps.send_email.urls')),
    path('clear_cache/', clear_cache, name='clear_cache'),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )