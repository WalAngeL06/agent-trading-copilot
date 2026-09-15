"""Stable decimal text for artifacts. Exact values stay Decimal in memory."""
from decimal import Decimal


def plain(value):
    """Trailing-zero-free, never exponent notation: 302.0000000000 -> '302'."""
    if not isinstance(value, Decimal):
        return value
    if not value.is_finite():
        return str(value)
    trimmed = value.normalize()
    if trimmed.as_tuple().exponent > 0:          # 1E+1 must render as 10
        trimmed = trimmed.quantize(Decimal(1))
    return format(trimmed, 'f')
