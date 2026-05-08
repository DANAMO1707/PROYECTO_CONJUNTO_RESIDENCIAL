from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='admin/', permanent=True)), # Te lleva al inicio
    path('api/', include('conjunto_residencial.urls')),
]