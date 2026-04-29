"""
signals.py — Automatizaciones
Crea QR permanente automáticamente cuando se registra un residente nuevo.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone


@receiver(post_save, sender='conjunto_residencial.Usuario')
def crear_qr_residente(sender, instance, created, **kwargs):
    """Al crear un residente nuevo, genera su QR permanente automáticamente."""
    if not created:
        return
    if instance.rol != 'residente':
        return

    from .models import CodigoQR
    if CodigoQR.objects.filter(usuario=instance, tipo='permanente').exists():
        return

    CodigoQR.objects.create(
        usuario=instance,
        tipo='permanente',
        estado='activo',
        fecha_inicio=timezone.now(),
        fecha_fin=None,
    )


@receiver(pre_save, sender='conjunto_residencial.Usuario')
def revocar_qrs_al_desactivar(sender, instance, **kwargs):
    """Si desactivan un usuario, se revocan todos sus QRs."""
    if not instance.pk:
        return
    try:
        anterior = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if anterior.activo and not instance.activo:
        from .models import CodigoQR
        CodigoQR.objects.filter(
            usuario=instance, estado='activo'
        ).update(estado='revocado')
