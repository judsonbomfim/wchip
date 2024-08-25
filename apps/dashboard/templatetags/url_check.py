from django import template

register = template.Library()

@register.simple_tag
def urL_active(request, url):
    return 'active' if request.path == url else ''

@register.simple_tag
def urL_open(request, url):
    return 'open' if request.path == url else ''