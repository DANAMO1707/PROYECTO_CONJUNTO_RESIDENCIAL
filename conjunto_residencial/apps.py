from django.apps import AppConfig


class ConjuntoResidencialConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name         = 'conjunto_residencial'
    verbose_name = 'Sistema Conjunto Residencial'

    def ready(self):
        import conjunto_residencial.signals  # noqa
