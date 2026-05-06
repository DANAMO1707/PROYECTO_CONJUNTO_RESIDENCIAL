"""
urls.py — Rutas de la API del conjunto
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register(r'usuarios',     views.UsuarioViewSet,     basename='usuario')
router.register(r'apartamentos', views.ApartamentoViewSet, basename='apartamento')
router.register(r'vehiculos',    views.VehiculoViewSet,    basename='vehiculo')
router.register(r'pqrs',         views.PQRSViewSet,        basename='pqrs')

urlpatterns = [
    # Auth
    path('api/auth/login/',   views.LoginView.as_view(),    name='login'),
    path('api/auth/refresh/', TokenRefreshView.as_view(),   name='token-refresh'),

    # Perfil propio
    path('api/usuarios/yo/',  views.MiPerfilView.as_view(), name='mi-perfil'),

    # Parqueadero
    path('api/parqueadero/estado/',    views.EstadoParqueaderoView.as_view(), name='parqueadero-estado'),
    path('api/parqueadero/validar/',   views.ValidarQRView.as_view(),         name='validar-qr'),
    path('api/parqueadero/historial/', views.HistorialParqueaderoView.as_view(), name='historial'),

    # QR
    path('api/qr/',                      views.ListaQRView.as_view(),    name='lista-qr'),
    path('api/qr/generar/',              views.GenerarQRView.as_view(),  name='generar-qr'),
    path('api/qr/<uuid:qr_id>/imagen/',  views.ImagenQRView.as_view(),   name='imagen-qr'),
    path('api/qr/<uuid:qr_id>/revocar/', views.RevocarQRView.as_view(),  name='revocar-qr'),

    # Dashboard y auditoría
    path('api/dashboard/',  views.DashboardView.as_view(),    name='dashboard'),
    path('api/auditoria/',  views.LogAuditoriaView.as_view(), name='auditoria'),

    # ViewSets
    path('api/', include(router.urls)),
path('', RedirectView.as_view(url='admin/'), name='index'),
]