from django import template

register = template.Library()

@register.filter
def map_status(value, arg):
    return arg.get(value)