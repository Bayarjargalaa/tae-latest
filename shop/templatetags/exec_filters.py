"""Удирдлагын нэгтгэлийн (/dashboard/) тоон форматууд."""
from django import template

register = template.Library()


@register.filter
def mnt_short(value):
    """Том дүнг товчлох: 2 670 018 961 -> "2.67 тэрбум", 224 654 282 -> "224.7 сая"."""
    if value is None or value == '':
        return '-'
    v = float(value)
    sign = '-' if v < 0 else ''
    v = abs(v)
    if v >= 1e9:
        return f'{sign}{v / 1e9:.2f} тэрбум'
    if v >= 1e6:
        return f'{sign}{v / 1e6:.1f} сая'
    if v >= 1e3:
        return f'{sign}{v / 1e3:.0f} мянга'
    return f'{sign}{v:.0f}'


@register.filter
def signed(value, digits=1):
    """Өөрчлөлтийн хувь/пунктийг тэмдэгтэй: +12.3, -4.0 (None бол хоосон)."""
    if value is None or value == '':
        return ''
    return f'{float(value):+.{int(digits)}f}'


@register.filter
def pct(value, digits=1):
    if value is None or value == '':
        return '-'
    return f'{float(value):.{int(digits)}f}%'


@register.filter
def clamp100(value):
    """Явцын мөрийн өргөн (0-100)."""
    try:
        return max(0, min(100, float(value)))
    except (TypeError, ValueError):
        return 0
