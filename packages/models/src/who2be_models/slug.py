"""Geteilter Slug-Typ fuer workspace-eindeutige Kennungen.

`SlugStr` ist die eine Quelle fuer die Slug-Form (Kleinbuchstaben + Ziffern +
Bindestriche), damit System-Prompt-Templates und Resources dieselbe Regel
teilen, statt sie zu duplizieren.
"""

from typing import Annotated

from pydantic import StringConstraints

# Slug-Form: Kleinbuchstaben/Ziffern + Bindestriche; max. 100 Zeichen. Muss mit
# einem alphanumerischen Zeichen beginnen.
SlugStr = Annotated[
    str, StringConstraints(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
]
