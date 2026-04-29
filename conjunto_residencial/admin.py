from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils import timezone

from .models import (
    Usuario, Apartamento, RelacionResidenteApto,
    CodigoQR, Vehiculo, RegistroParqueadero,
    PQRS, LogAuditoria
)


# ── Usuarios ──────────────────────────────────────────────────────────────────

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display  = ('username', 'nombre_completo', 'rol_badge', 'telefono', 'activo', 'creado')
    list_filter   = ('rol', 'activo')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering      = ('-creado',)

    fieldsets = UserAdmin.fieldsets + (
        ('Datos del conjunto', {
            'fields': ('rol', 'telefono', 'foto', 'activo')
        }),
    )

    def nombre_completo(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip() or '—'
    nombre_completo.short_description = 'Nombre'

    def rol_badge(self, obj):
        colores = {
            'residente':    '#1a6eb5',
            'vacacionista': '#c27c10',
            'admin':        '#1a7a4a',
            'guardia':      '#8b2500',
        }
        color = colores.get(obj.rol, '#666')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 9px;'
            'border-radius:99px;font-size:11px;font-weight:500">{}</span>',
            color, obj.get_rol_display()
        )
    rol_badge.short_description = 'Rol'


# ── Apartamentos ──────────────────────────────────────────────────────────────

class RelacionInline(admin.TabularInline):
    model  = RelacionResidenteApto
    extra  = 1
    fields = ('usuario', 'tipo_relacion', 'fecha_inicio', 'fecha_fin', 'activo')


@admin.register(Apartamento)
class ApartamentoAdmin(admin.ModelAdmin):
    list_display  = ('numero', 'torre', 'piso', 'propietario', 'n_residentes')
    list_filter   = ('torre',)
    search_fields = ('numero',)
    inlines       = [RelacionInline]

    def n_residentes(self, obj):
        return obj.residentes.filter(activo=True).count()
    n_residentes.short_description = 'Residentes'


# ── Códigos QR ────────────────────────────────────────────────────────────────

@admin.register(CodigoQR)
class CodigoQRAdmin(admin.ModelAdmin):
    list_display  = ('usuario', 'tipo_badge', 'estado_badge', 'vigente_icon', 'fecha_inicio', 'fecha_fin')
    list_filter   = ('tipo', 'estado')
    search_fields = ('usuario__username', 'usuario__first_name', 'token')
    readonly_fields = ('id', 'token', 'creado')
    ordering      = ('-creado',)
    actions       = ['revocar_seleccionados']

    def tipo_badge(self, obj):
        color = '#1a6eb5' if obj.tipo == 'permanente' else '#c27c10'
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:99px;font-size:11px">{}</span>',
            color, obj.get_tipo_display()
        )
    tipo_badge.short_description = 'Tipo'

    def estado_badge(self, obj):
        c = {'activo': '#1a7a4a', 'expirado': '#b52828', 'revocado': '#666'}
        return format_html(
            '<b style="color:{}">{}</b>', c.get(obj.estado, '#333'), obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'

    def vigente_icon(self, obj):
        ok = obj.esta_vigente
        return format_html(
            '<span style="color:{}">{}</span>',
            '#1a7a4a' if ok else '#b52828',
            '✓ Vigente' if ok else '✗ Vencido'
        )
    vigente_icon.short_description = 'Vigente'

    @admin.action(description='Revocar QRs seleccionados')
    def revocar_seleccionados(self, request, queryset):
        n = queryset.filter(estado='activo').update(estado='revocado')
        self.message_user(request, f'{n} QR(s) revocados.')


# ── Vehículos ─────────────────────────────────────────────────────────────────

@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display  = ('placa', 'marca', 'color', 'tipo', 'propietario', 'adentro_ahora', 'activo')
    list_filter   = ('tipo', 'activo')
    search_fields = ('placa', 'marca', 'propietario__username')

    def adentro_ahora(self, obj):
        adentro = obj.registros.filter(hora_salida__isnull=True).exists()
        return format_html(
            '<span style="color:{}">{}</span>',
            '#1a7a4a' if adentro else '#999',
            '● Sí' if adentro else '○ No'
        )
    adentro_ahora.short_description = 'Adentro'


# ── Registros Parqueadero ─────────────────────────────────────────────────────

@admin.register(RegistroParqueadero)
class RegistroParqueaderoAdmin(admin.ModelAdmin):
    list_display  = ('vehiculo', 'hora_entrada', 'hora_salida', 'duracion', 'estado_display')
    list_filter   = ('hora_entrada',)
    search_fields = ('vehiculo__placa',)
    readonly_fields = ('hora_entrada',)
    ordering      = ('-hora_entrada',)
    date_hierarchy = 'hora_entrada'

    def estado_display(self, obj):
        if obj.hora_salida is None:
            return format_html('<b style="color:#1a7a4a">● Adentro</b>')
        return format_html('<span style="color:#999">○ Salió</span>')
    estado_display.short_description = 'Estado'

    def duracion(self, obj):
        m = obj.duracion_minutos
        h, mn = divmod(m, 60)
        return f'{h}h {mn}m' if h else f'{mn}m'
    duracion.short_description = 'Duración'


# ── PQRS ──────────────────────────────────────────────────────────────────────

@admin.register(PQRS)
class PQRSAdmin(admin.ModelAdmin):
    list_display  = ('titulo', 'tipo_b', 'estado_b', 'usuario', 'creado', 'respondido_por')
    list_filter   = ('tipo', 'estado')
    search_fields = ('titulo', 'usuario__username')
    readonly_fields = ('id', 'creado', 'actualizado')

    fieldsets = (
        ('Solicitud', {'fields': ('usuario', 'apartamento', 'tipo', 'titulo', 'descripcion')}),
        ('Respuesta', {'fields': ('estado', 'respuesta', 'respondido_por')}),
        ('Info',      {'fields': ('id', 'creado', 'actualizado'), 'classes': ('collapse',)}),
    )

    def tipo_b(self, obj):
        c = {'queja':'#b52828','peticion':'#1a6eb5','reclamo':'#c27c10','sugerencia':'#1a7a4a'}
        return format_html('<b style="color:{}">{}</b>', c.get(obj.tipo,'#333'), obj.get_tipo_display())
    tipo_b.short_description = 'Tipo'

    def estado_b(self, obj):
        c = {'abierta':'#b52828','en_proceso':'#c27c10','resuelta':'#1a7a4a','cerrada':'#999'}
        return format_html('<b style="color:{}">{}</b>', c.get(obj.estado,'#333'), obj.get_estado_display())
    estado_b.short_description = 'Estado'


# ── Log Auditoría (solo lectura) ──────────────────────────────────────────────

@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display  = ('timestamp', 'accion', 'usuario', 'ip_address')
    list_filter   = ('accion',)
    search_fields = ('usuario__username',)
    readonly_fields = ('usuario', 'accion', 'detalle', 'ip_address', 'timestamp')
    ordering      = ('-timestamp',)

    def has_add_permission(self, request):   return False
    def has_change_permission(self, *a):     return False
    def has_delete_permission(self, *a):     return False
