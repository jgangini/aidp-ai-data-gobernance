"""Compare Oracle ISO/numeric timestamps at their shared microsecond resolution."""
import math


def at_or_after(observed, submitted):
    values = (observed, submitted)
    if any(type(value) not in {int, float} or not math.isfinite(value) for value in values):
        return False
    return round(observed * 1_000_000) >= round(submitted * 1_000_000)
