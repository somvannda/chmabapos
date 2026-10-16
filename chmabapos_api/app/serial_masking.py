"""Masking for serial numbers shown to the public.

A serial identifies one physical unit, so publishing one in full tells the world what a
shop holds and hands out an identifier that can be used elsewhere. The ends are the
useful part to a buyer - the prefix a shop recognises its stock by, and the last digits
you compare against the box or quote on a warranty claim - so the rule keeps both and
hides the middle.
"""

VISIBLE_PREFIX = 2
VISIBLE_SUFFIX = 3

# Fixed width rather than one star per hidden character: how long the hidden part is
# would otherwise leak through, and a uniform run is easier to scan.
MASK = "******"


def mask_serial(value: str | None) -> str:
    """``AB123456789`` -> ``AB******789``.

    A value too short to hide anything meaningful - shorter than the visible ends plus
    one hidden character - is masked completely rather than shown nearly in full, which
    would defeat the point. An empty value stays empty, so callers can drop the row.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) < VISIBLE_PREFIX + VISIBLE_SUFFIX + 1:
        return MASK
    return f"{text[:VISIBLE_PREFIX]}{MASK}{text[-VISIBLE_SUFFIX:]}"
