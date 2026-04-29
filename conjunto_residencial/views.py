"""
views.py — Vistas de la API REST
Compatible con SQLite, sin dependencias externas complejas.
"""

import hashlib
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.db import transaction

from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import (
    Usuario, Apartamento, CodigoQR, Vehiculo,
    RegistroParqueadero, PQRS, LogAuditoria
)
from .serializers import (
    UsuarioDetalleSerializer, CrearUsuarioSerializer,
    ApartamentoSerializer, CodigoQRSerializer,
    VehiculoSerializer, RegistroParqueaderoSerializer,
    PQRSSerializer, LogAuditoriaSerializer,
    GenerarQRSerializer, ValidarQRSerializer, ResponderPQRSSerializer
)


# ─────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────

CAPACIDAD_PARQUEADERO = 75


def ocupacion_actual():
    return RegistroParqueadero.objects.filter(hora_salida__isnull=True).count()


def hay_espacio():
    return ocupacion_actual() < CAPACIDAD_PARQUEADERO


def get_ip(request):
    x = request.META.get('HTTP_X_FORWARDED_FOR')
    return x.split(',')[0] if x else request.META.get('REMOTE_ADDR')


# ─────────────────────────────────────────────
# PERMISOS
# ─────────────────────────────────────────────

class EsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'admin'


class EsAdminOGuardia(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol in ('admin', 'guardia')


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

class MiTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol']    = user.rol
        token['nombre'] = f'{user.first_name} {user.last_name}'.strip()
        return token


class LoginView(TokenObtainPairView):
    serializer_class = MiTokenSerializer


# ─────────────────────────────────────────────
# USUARIOS
# ─────────────────────────────────────────────

class UsuarioViewSet(ModelViewSet):
    queryset = Usuario.objects.filter(activo=True).order_by('-creado')

    def get_serializer_class(self):
        return CrearUsuarioSerializer if self.action == 'create' else UsuarioDetalleSerializer

    def get_permissions(self):
        if self.action in ('list', 'destroy', 'create'):
            return [EsAdmin()]
        return [permissions.IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        u = self.get_object()
        u.activo = False
        u.save()
        return Response({'mensaje': 'Usuario desactivado.'})


class MiPerfilView(generics.RetrieveUpdateAPIView):
    serializer_class   = UsuarioDetalleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# ─────────────────────────────────────────────
# APARTAMENTOS
# ─────────────────────────────────────────────

class ApartamentoViewSet(ModelViewSet):
    queryset           = Apartamento.objects.order_by('torre', 'numero')
    serializer_class   = ApartamentoSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [EsAdmin()]
        return [permissions.IsAuthenticated()]


# ─────────────────────────────────────────────
# PARQUEADERO
# ─────────────────────────────────────────────

class EstadoParqueaderoView(APIView):
    """GET /api/parqueadero/estado/ — Ocupación en tiempo real."""
    permission_classes = [EsAdminOGuardia]

    def get(self, request):
        ocu = ocupacion_actual()
        registros = RegistroParqueadero.objects.filter(
            hora_salida__isnull=True
        ).select_related('vehiculo').order_by('-hora_entrada')

        return Response({
            'ocupadas':        ocu,
            'libres':          CAPACIDAD_PARQUEADERO - ocu,
            'capacidad':       CAPACIDAD_PARQUEADERO,
            'porcentaje':      round(ocu / CAPACIDAD_PARQUEADERO * 100, 1),
            'puede_ingresar':  hay_espacio(),
            'vehiculos_adentro': RegistroParqueaderoSerializer(registros, many=True).data,
        })


class ValidarQRView(APIView):
    """
    POST /api/parqueadero/validar/
    El guardia escanea el QR y registra ingreso o salida.
    Body: { "token": "...", "placa": "ABC123", "accion": "ingreso" }
    """
    permission_classes = [EsAdminOGuardia]

    @transaction.atomic
    def post(self, request):
        ser = ValidarQRSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        token  = ser.validated_data['token']
        placa  = ser.validated_data.get('placa', '').upper()
        accion = ser.validated_data['accion']

        # Validar QR
        try:
            qr = CodigoQR.objects.select_related('usuario').get(token=token)
        except CodigoQR.DoesNotExist:
            return Response({'valido': False, 'mensaje': 'QR no reconocido.'}, status=403)

        if not qr.esta_vigente:
            return Response({'valido': False, 'mensaje': 'QR expirado o revocado.'}, status=403)

        # Buscar vehículo
        try:
            vehiculo = Vehiculo.objects.get(placa=placa, activo=True)
        except Vehiculo.DoesNotExist:
            return Response({'valido': False, 'mensaje': f'Vehículo {placa} no registrado.'}, status=404)

        if accion == 'ingreso':
            if not hay_espacio():
                LogAuditoria.objects.create(
                    usuario=request.user, accion='parking_lleno',
                    detalle={'placa': placa}, ip_address=get_ip(request)
                )
                return Response({
                    'valido': False,
                    'mensaje': f'Parqueadero lleno ({CAPACIDAD_PARQUEADERO}/{CAPACIDAD_PARQUEADERO}).'
                }, status=409)

            if RegistroParqueadero.objects.filter(vehiculo=vehiculo, hora_salida__isnull=True).exists():
                return Response({'valido': False, 'mensaje': 'El vehículo ya está adentro.'}, status=400)

            reg = RegistroParqueadero.objects.create(
                vehiculo=vehiculo, codigo_qr_usado=qr, autorizado_por=request.user
            )
            LogAuditoria.objects.create(
                usuario=request.user, accion='ingreso_valido',
                detalle={'placa': placa, 'libres': CAPACIDAD_PARQUEADERO - ocupacion_actual()},
                ip_address=get_ip(request)
            )
            return Response({
                'valido': True,
                'mensaje': f'✅ Ingreso autorizado. Plazas libres: {CAPACIDAD_PARQUEADERO - ocupacion_actual()}',
                'usuario': str(qr.usuario),
                'plazas_libres': CAPACIDAD_PARQUEADERO - ocupacion_actual(),
            })

        else:  # salida
            reg = RegistroParqueadero.objects.filter(
                vehiculo=vehiculo, hora_salida__isnull=True
            ).first()
            if not reg:
                return Response({'valido': False, 'mensaje': 'No hay ingreso activo para este vehículo.'}, status=400)
            reg.hora_salida = timezone.now()
            reg.save()
            return Response({
                'valido': True,
                'mensaje': f'✅ Salida registrada. Plazas libres: {CAPACIDAD_PARQUEADERO - ocupacion_actual()}',
                'plazas_libres': CAPACIDAD_PARQUEADERO - ocupacion_actual(),
            })


class HistorialParqueaderoView(generics.ListAPIView):
    serializer_class   = RegistroParqueaderoSerializer
    permission_classes = [EsAdmin]

    def get_queryset(self):
        qs    = RegistroParqueadero.objects.select_related('vehiculo').order_by('-hora_entrada')
        placa = self.request.query_params.get('placa')
        fecha = self.request.query_params.get('fecha')
        if placa:
            qs = qs.filter(vehiculo__placa__icontains=placa)
        if fecha:
            qs = qs.filter(hora_entrada__date=fecha)
        return qs


# ─────────────────────────────────────────────
# CÓDIGOS QR
# ─────────────────────────────────────────────

class GenerarQRView(APIView):
    """POST /api/qr/generar/"""
    permission_classes = [EsAdmin]

    def post(self, request):
        ser = GenerarQRSerializer(data=request.data, context={'request': request})
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        data    = ser.validated_data
        usuario = data['usuario']
        tipo    = data['tipo']

        if tipo == 'temporal' and not hay_espacio():
            return Response(
                {'error': f'No se puede generar QR: parqueadero lleno.'},
                status=409
            )

        qr = CodigoQR.objects.create(
            usuario=usuario,
            tipo=tipo,
            fecha_inicio=data.get('fecha_inicio', timezone.now()),
            fecha_fin=data.get('fecha_fin'),
            creado_por=request.user,
        )

        LogAuditoria.objects.create(
            usuario=request.user, accion='qr_generado',
            detalle={'qr_id': str(qr.id), 'tipo': tipo, 'para': str(usuario)},
            ip_address=get_ip(request)
        )

        return Response(CodigoQRSerializer(qr, context={'request': request}).data, status=201)


class ImagenQRView(APIView):
    """GET /api/qr/{id}/imagen/ — Devuelve PNG del QR."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, qr_id):
        qr = get_object_or_404(CodigoQR, id=qr_id)

        if request.user.rol == 'residente' and qr.usuario != request.user:
            return Response({'error': 'Sin permiso.'}, status=403)

        try:
            from .qr_generator import GeneradorQR
            tamanio = int(request.query_params.get('tamanio', 300))
            imagen  = GeneradorQR.generar_png(qr, tamanio=tamanio)
            resp    = HttpResponse(imagen, content_type='image/png')
            resp['Content-Disposition'] = f'inline; filename="QR_{qr.usuario.username}.png"'
            resp['Cache-Control'] = 'no-store'
            return resp
        except Exception as e:
            return Response({'error': f'No se pudo generar la imagen: {e}'}, status=500)


class ListaQRView(generics.ListAPIView):
    serializer_class   = CodigoQRSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs   = CodigoQR.objects.select_related('usuario').order_by('-creado')
        if user.rol == 'residente':
            return qs.filter(usuario=user)
        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        return qs


class RevocarQRView(APIView):
    permission_classes = [EsAdmin]

    def post(self, request, qr_id):
        qr = get_object_or_404(CodigoQR, id=qr_id)
        if qr.estado != 'activo':
            return Response({'error': 'El QR ya está inactivo.'}, status=400)
        qr.estado = 'revocado'
        qr.save()
        return Response({'mensaje': 'QR revocado.'})


# ─────────────────────────────────────────────
# VEHÍCULOS
# ─────────────────────────────────────────────

class VehiculoViewSet(ModelViewSet):
    serializer_class   = VehiculoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.rol in ('admin', 'guardia'):
            return Vehiculo.objects.filter(activo=True)
        return Vehiculo.objects.filter(propietario=user, activo=True)

    def perform_create(self, serializer):
        serializer.save(propietario=self.request.user)

    def destroy(self, request, *args, **kwargs):
        v = self.get_object()
        v.activo = False
        v.save()
        return Response({'mensaje': 'Vehículo desregistrado.'})


# ─────────────────────────────────────────────
# PQRS
# ─────────────────────────────────────────────

class PQRSViewSet(ModelViewSet):
    serializer_class   = PQRSSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs   = PQRS.objects.order_by('-creado')
        if user.rol == 'admin':
            return qs
        return qs.filter(usuario=user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)
        LogAuditoria.objects.create(
            usuario=self.request.user, accion='pqrs_creada',
            detalle={'titulo': serializer.instance.titulo[:60]}
        )

    def responder(self, request, pk=None):
        pqrs = self.get_object()
        ser  = ResponderPQRSSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        pqrs.respuesta      = ser.validated_data['respuesta']
        pqrs.estado         = ser.validated_data['estado']
        pqrs.respondido_por = request.user
        pqrs.save()
        return Response(PQRSSerializer(pqrs).data)


# ─────────────────────────────────────────────
# DASHBOARD Y AUDITORÍA
# ─────────────────────────────────────────────

class DashboardView(APIView):
    permission_classes = [EsAdmin]

    def get(self, request):
        hoy = timezone.now().date()
        return Response({
            'parqueadero': {
                'ocupadas':  ocupacion_actual(),
                'libres':    CAPACIDAD_PARQUEADERO - ocupacion_actual(),
                'capacidad': CAPACIDAD_PARQUEADERO,
            },
            'usuarios': {
                'total':        Usuario.objects.filter(activo=True).count(),
                'residentes':   Usuario.objects.filter(rol='residente', activo=True).count(),
                'vacacionistas':Usuario.objects.filter(rol='vacacionista', activo=True).count(),
            },
            'qrs': {
                'activos':   CodigoQR.objects.filter(estado='activo').count(),
            },
            'pqrs': {
                'abiertas':   PQRS.objects.filter(estado='abierta').count(),
                'en_proceso': PQRS.objects.filter(estado='en_proceso').count(),
            },
            'ingresos_hoy': RegistroParqueadero.objects.filter(hora_entrada__date=hoy).count(),
        })


class LogAuditoriaView(generics.ListAPIView):
    serializer_class   = LogAuditoriaSerializer
    permission_classes = [EsAdmin]

    def get_queryset(self):
        return LogAuditoria.objects.order_by('-timestamp')
