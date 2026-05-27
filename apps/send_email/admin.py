from django.contrib import admin
from apps.send_email.models import Templates


@admin.register(Templates)
class TemplatesAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    fields = ('name', 'slug', 'content')

