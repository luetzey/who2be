"""Geteilte Slug-Ableitung fuer slug-fuehrende Aggregate.

`slugify` erzeugt aus einem Namen einen URL-tauglichen Slug (`SlugStr`-Form).
Eine Quelle fuer System-Prompt-Templates und Resources — nicht forken.
"""

import re
import unicodedata

_SLUG_FALLBACK = "resource"


def slugify(text: str, fallback: str = _SLUG_FALLBACK) -> str:
    """Erzeugt einen URL-tauglichen Slug aus dem Namen.

    Standard-NFKD + ASCII-Zwang: Umlaute werden zerlegt, Punkte/Sonderzeichen
    fallen raus, Whitespace wird zu `-`, mehrfache Bindestriche zusammengefasst.
    Bewusst klein gehalten — fuer alles weitere uebergibt der Client den Slug.
    """
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return cleaned or fallback
