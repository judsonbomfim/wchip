"""Embed local SVGs as data-URIs for Iconify --svg (avoids CDN CORS on mask-image)."""
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from django import template
from django.conf import settings
from django.contrib.staticfiles.finders import find
from django.utils.safestring import mark_safe

register = template.Library()


@lru_cache(maxsize=64)
def _svg_data_uri(static_path: str) -> str:
    absolute = find(static_path)
    if not absolute:
        for directory in getattr(settings, 'STATICFILES_DIRS', []):
            candidate = Path(directory) / static_path
            if candidate.is_file():
                absolute = str(candidate)
                break
    if not absolute:
        return "url('')"

    svg = Path(absolute).read_text(encoding='utf-8').strip()
    # Masks need opaque black; currentColor is unreliable inside CSS mask SVGs.
    svg = svg.replace('currentColor', '#000')
    # Single quotes: style="--svg: ..." cannot contain unescaped double quotes.
    return f"url('data:image/svg+xml,{quote(svg, safe='')}')"


@register.simple_tag
def icon_svg(path: str):
    """CSS value for style="--svg: {% icon_svg 'painel/inspina/icons/foo.svg' %}"."""
    return mark_safe(_svg_data_uri(path))
