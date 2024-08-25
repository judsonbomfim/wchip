from django import template
from datetime import timedelta

register = template.Library()

@register.simple_tag
def dateaddday(a, b):
    day_ = b - 1
    td = timedelta(day_)
    addDay = a + td
    addF = addDay.strftime('%d/%m/%Y')
    return addF