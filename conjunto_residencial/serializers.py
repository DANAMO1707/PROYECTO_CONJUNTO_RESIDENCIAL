from rest_framework import serializers
from django.utils import timezone
from .models import (
    Usuario, Apartamento, CodigoQR, Vehiculo,
    RegistroParqueadero, PQRS, LogAuditoria
)


class UsuarioPublicoSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.SerializerMethodField()

    class Meta:
        model  = Usuario
        fields = ['id', 'username', 'nombre_completo', 'rol', 'activo']

    def get_nombre_completo(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip() or obj.username


class UsuarioDetalleSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.SerializerMethodField()

    class Meta:
        model  = Usuario
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'nombre_completo', 'rol', 'telefono', 'activo', 'creado']
        read_only_fields = ['id', 'creado']

    def get_nombre_completo(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip()


class CrearUsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model  = Usuario
        fields = ['username', 'email', 'first_name', 'last_name', 'rol', 'telefono', 'password']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = Usuario(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ApartamentoSerializer(serializers.ModelSerializer):
    propietario = UsuarioPublicoSerializer(read_only=True)

    class Meta:
        model  = Apartamento
        fields = ['id', 'numero', 'torre', 'piso', 'propietario', 'creado']
        read_only_fields = ['id', 'creado']


class CodigoQRSerializer(serializers.ModelSerializer):
    usuario      = UsuarioPublicoSerializer(read_only=True)
    esta_vigente = serializers.BooleanField(read_only=True)
    imagen_url   = serializers.SerializerMethodField()

    class Meta:
        model  = CodigoQR
        fields = ['id', 'usuario', 'tipo', 'estado', 'token',
                  'fecha_inicio', 'fecha_fin', 'esta_vigente', 'imagen_url', 'creado']
        read_only_fields = ['id', 'token', 'estado', 'creado']

    def get_imagen_url(self, obj):
        request = self.context.get('request')
        url = f'/api/qr/{obj.id}/imagen/'
        return request.build_absolute_uri(url) if request else url


class GenerarQRSerializer(serializers.Serializer):
    usuario_id   = serializers.UUIDField()
    tipo         = serializers.ChoiceField(choices=[('permanente', 'Permanente'), ('temporal', 'Temporal')])
    fecha_inicio = serializers.DateTimeField(required=False)
    fecha_fin    = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, data):
        if data.get('tipo') == 'temporal' and not data.get('fecha_fin'):
            raise serializers.ValidationError('Los QR temporales requieren fecha_fin.')
        if data.get('fecha_fin') and data['fecha_fin'] <= timezone.now():
            raise serializers.ValidationError('La fecha_fin debe ser en el futuro.')
        try:
            data['usuario'] = Usuario.objects.get(id=data['usuario_id'], activo=True)
        except Usuario.DoesNotExist:
            raise serializers.ValidationError('Usuario no encontrado.')
        return data


class ValidarQRSerializer(serializers.Serializer):
    token  = serializers.CharField(max_length=64)
    placa  = serializers.CharField(max_length=10, required=False, default='')
    accion = serializers.ChoiceField(choices=['ingreso', 'salida'])


class VehiculoSerializer(serializers.ModelSerializer):
    propietario = UsuarioPublicoSerializer(read_only=True)

    class Meta:
        model  = Vehiculo
        fields = ['id', 'propietario', 'placa', 'marca', 'modelo', 'color', 'tipo', 'activo', 'creado']
        read_only_fields = ['id', 'creado']

    def validate_placa(self, value):
        return value.upper().strip()


class RegistroParqueaderoSerializer(serializers.ModelSerializer):
    placa        = serializers.CharField(source='vehiculo.placa', read_only=True)
    esta_adentro = serializers.BooleanField(read_only=True)
    duracion_min = serializers.IntegerField(source='duracion_minutos', read_only=True)

    class Meta:
        model  = RegistroParqueadero
        fields = ['id', 'placa', 'hora_entrada', 'hora_salida', 'esta_adentro', 'duracion_min']


class PQRSSerializer(serializers.ModelSerializer):
    usuario        = UsuarioPublicoSerializer(read_only=True)
    respondido_por = UsuarioPublicoSerializer(read_only=True)

    class Meta:
        model  = PQRS
        fields = ['id', 'usuario', 'apartamento', 'tipo', 'titulo', 'descripcion',
                  'estado', 'respuesta', 'respondido_por', 'creado', 'actualizado']
        read_only_fields = ['id', 'estado', 'respuesta', 'respondido_por', 'creado', 'actualizado']


class ResponderPQRSSerializer(serializers.Serializer):
    respuesta = serializers.CharField(min_length=5)
    estado    = serializers.ChoiceField(choices=['en_proceso', 'resuelta', 'cerrada'])


class LogAuditoriaSerializer(serializers.ModelSerializer):
    usuario = UsuarioPublicoSerializer(read_only=True)

    class Meta:
        model  = LogAuditoria
        fields = ['id', 'usuario', 'accion', 'detalle', 'ip_address', 'timestamp']
