"""
models.py — Modelos del Sistema Conjunto Residencial
Base de datos: SQLite (desarrollo local)
Sin cifrado externo, compatible con cualquier entorno
"""

import uuid
import hashlib
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser


# ─────────────────────────────────────────────
# USUARIOS Y ROLES
# ─────────────────────────────────────────────

class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        RESIDENTE     = 'residente',    'Residente'
        VACACIONISTA  = 'vacacionista', 'Vacacionista / Visitante'
        ADMINISTRADOR = 'admin',        'Administrador'
        GUARDIA       = 'guardia',      'Guardia'

    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rol      = models.CharField(max_length=20, choices=Rol.choices, default=Rol.RESIDENTE)
    telefono = models.CharField(max_length=20, blank=True)
    foto     = models.ImageField(upload_to='fotos/', null=True, blank=True)
    activo   = models.BooleanField(default=True)
    creado   = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_rol_display()})'


# ─────────────────────────────────────────────
# APARTAMENTOS
# ─────────────────────────────────────────────

class Apartamento(models.Model):
    numero      = models.CharField(max_length=10, unique=True)
    torre       = models.CharField(max_length=5, blank=True)
    piso        = models.PositiveSmallIntegerField()
    propietario = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='apartamentos_propios'
    )
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Apto {self.numero} — Torre {self.torre or "Única"}'

    class Meta:
        ordering = ['torre', 'piso', 'numero']
        verbose_name = 'Apartamento'
        verbose_name_plural = 'Apartamentos'


class RelacionResidenteApto(models.Model):
    class TipoRelacion(models.TextChoices):
        PROPIETARIO  = 'propietario',  'Propietario'
        ARRENDATARIO = 'arrendatario', 'Arrendatario'
        FAMILIAR     = 'familiar',     'Familiar'
        VACACIONISTA = 'vacacionista', 'Vacacionista'

    usuario       = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='relaciones_apto')
    apartamento   = models.ForeignKey(Apartamento, on_delete=models.CASCADE, related_name='residentes')
    tipo_relacion = models.CharField(max_length=20, choices=TipoRelacion.choices)
    fecha_inicio  = models.DateField()
    fecha_fin     = models.DateField(null=True, blank=True)
    activo        = models.BooleanField(default=True)

    class Meta:
        unique_together = ('usuario', 'apartamento')
        verbose_name = 'Relación Residente-Apto'
        verbose_name_plural = 'Relaciones Residente-Apto'

    def __str__(self):
        return f'{self.usuario} → {self.apartamento} ({self.tipo_relacion})'


# ─────────────────────────────────────────────
# CÓDIGOS QR
# ─────────────────────────────────────────────

class CodigoQR(models.Model):
    class TipoQR(models.TextChoices):
        PERMANENTE = 'permanente', 'Permanente (Residente)'
        TEMPORAL   = 'temporal',   'Temporal (Vacacionista)'

    class EstadoQR(models.TextChoices):
        ACTIVO   = 'activo',   'Activo'
        EXPIRADO = 'expirado', 'Expirado'
        REVOCADO = 'revocado', 'Revocado'

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario      = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='codigos_qr')
    apartamento  = models.ForeignKey(Apartamento, on_delete=models.SET_NULL, null=True, blank=True)
    tipo         = models.CharField(max_length=15, choices=TipoQR.choices)
    estado       = models.CharField(max_length=10, choices=EstadoQR.choices, default=EstadoQR.ACTIVO)
    token        = models.CharField(max_length=64, unique=True, blank=True)
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_fin    = models.DateTimeField(null=True, blank=True)
    creado_por   = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='qrs_generados'
    )
    creado = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = hashlib.sha256(f'{self.id}{self.usuario_id}'.encode()).hexdigest()
        super().save(*args, **kwargs)

    @property
    def esta_vigente(self):
        if self.estado != self.EstadoQR.ACTIVO:
            return False
        if self.fecha_fin and timezone.now() > self.fecha_fin:
            return False
        return True

    def __str__(self):
        return f'QR {self.tipo} — {self.usuario} ({self.estado})'

    class Meta:
        verbose_name = 'Código QR'
        verbose_name_plural = 'Códigos QR'
        ordering = ['-creado']


# ─────────────────────────────────────────────
# VEHÍCULOS Y PARQUEADERO
# ─────────────────────────────────────────────

class Vehiculo(models.Model):
    class TipoVehiculo(models.TextChoices):
        CARRO = 'carro', 'Carro'
        MOTO  = 'moto',  'Motocicleta'
        BICI  = 'bici',  'Bicicleta'

    propietario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='vehiculos')
    placa       = models.CharField(max_length=10, unique=True)
    marca       = models.CharField(max_length=50)
    modelo      = models.CharField(max_length=50, blank=True)
    color       = models.CharField(max_length=30)
    tipo        = models.CharField(max_length=10, choices=TipoVehiculo.choices, default=TipoVehiculo.CARRO)
    activo      = models.BooleanField(default=True)
    creado      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.placa} — {self.marca} {self.color}'

    class Meta:
        verbose_name = 'Vehículo'
        verbose_name_plural = 'Vehículos'


class RegistroParqueadero(models.Model):
    CAPACIDAD_MAXIMA = 75

    vehiculo        = models.ForeignKey(Vehiculo, on_delete=models.PROTECT, related_name='registros')
    codigo_qr_usado = models.ForeignKey(CodigoQR, on_delete=models.SET_NULL, null=True, blank=True)
    hora_entrada    = models.DateTimeField(default=timezone.now)
    hora_salida     = models.DateTimeField(null=True, blank=True)
    autorizado_por  = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='autorizaciones'
    )
    notas = models.TextField(blank=True)

    @property
    def esta_adentro(self):
        return self.hora_salida is None

    @property
    def duracion_minutos(self):
        fin = self.hora_salida or timezone.now()
        return round((fin - self.hora_entrada).total_seconds() / 60)

    def __str__(self):
        estado = 'Adentro' if self.esta_adentro else 'Salió'
        return f'{self.vehiculo.placa} — {estado}'

    class Meta:
        ordering = ['-hora_entrada']
        verbose_name = 'Registro de Parqueadero'
        verbose_name_plural = 'Registros de Parqueadero'


# ─────────────────────────────────────────────
# PQRS
# ─────────────────────────────────────────────

class PQRS(models.Model):
    class Tipo(models.TextChoices):
        PETICION   = 'peticion',   'Petición'
        QUEJA      = 'queja',      'Queja'
        RECLAMO    = 'reclamo',    'Reclamo'
        SUGERENCIA = 'sugerencia', 'Sugerencia'

    class Estado(models.TextChoices):
        ABIERTA    = 'abierta',    'Abierta'
        EN_PROCESO = 'en_proceso', 'En proceso'
        RESUELTA   = 'resuelta',   'Resuelta'
        CERRADA    = 'cerrada',    'Cerrada'

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario     = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='pqrs')
    apartamento = models.ForeignKey(Apartamento, on_delete=models.SET_NULL, null=True, blank=True)
    tipo        = models.CharField(max_length=15, choices=Tipo.choices)
    titulo      = models.CharField(max_length=200)
    descripcion = models.TextField()
    estado      = models.CharField(max_length=15, choices=Estado.choices, default=Estado.ABIERTA)
    respuesta   = models.TextField(blank=True)
    respondido_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pqrs_respondidas'
    )
    creado      = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'[{self.get_tipo_display()}] {self.titulo}'

    class Meta:
        verbose_name = 'PQRS'
        verbose_name_plural = 'PQRS'
        ordering = ['-creado']


# ─────────────────────────────────────────────
# LOG DE AUDITORÍA
# ─────────────────────────────────────────────

class LogAuditoria(models.Model):
    class Accion(models.TextChoices):
        INGRESO_VALIDO    = 'ingreso_valido',    'Ingreso válido'
        INGRESO_RECHAZADO = 'ingreso_rechazado', 'Ingreso rechazado'
        QR_GENERADO       = 'qr_generado',       'QR generado'
        QR_EXPIRADO       = 'qr_expirado',       'QR expirado'
        PARQUEADERO_LLENO = 'parking_lleno',     'Parqueadero lleno'
        PQRS_CREADA       = 'pqrs_creada',       'PQRS creada'

    usuario    = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    accion     = models.CharField(max_length=30, choices=Accion.choices)
    detalle    = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.timestamp:%d/%m/%Y %H:%M} — {self.accion}'

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Log de Auditoría'
        verbose_name_plural = 'Logs de Auditoría'
