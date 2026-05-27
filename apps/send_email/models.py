from django.db import models


class Templates(models.Model):
    SLUG_CHOICES = [
        ('esim_eua', 'eSIM EUA'),
        ('esim_other', 'eSIM Outros'),
        ('sim_all', 'SIM Físico'),
    ]

    name = models.CharField(max_length=255, verbose_name='Nome')
    slug = models.CharField(
        max_length=20,
        choices=SLUG_CHOICES,
        unique=True,
        verbose_name='Tipo de template',
    )
    content = models.TextField(verbose_name='Conteúdo (HTML)')

    class Meta:
        verbose_name = 'Template de e-mail'
        verbose_name_plural = 'Templates de e-mail'

    def __str__(self):
        return self.name