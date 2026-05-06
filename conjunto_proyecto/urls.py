from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header  = 'Conjunto Residencial — Admin'
admin.site.site_title   = 'Panel Administración'
admin.site.index_title  = 'Bienvenido al sistema'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('conjunto_residencial.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
from django.views.generic.base import RedirectView