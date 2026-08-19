"""Die EINE Kappungsregel fuer Such-Snippets.

Beide Suchpfade — WorkArea-Passagen (`wa_search_repository`) und KB-Aussagen
(`kb_repository`) — liefern Anker + Kostprobe, nie den ganzen Text: den holt
der Aufrufer gezielt nach (`read_artifact(anchor)` bzw. der Node selbst).
Damit „Kostprobe" fuer einen Agenten etwas Verlaessliches heisst, muss die
Grenze in beiden Pfaden dieselbe sein — sonst haengt die Snippet-Laenge davon
ab, welcher Index zufaellig getroffen hat.

Bis 2026-08-19 stand die Funktion zweimal byte-identisch im Code. Das ging
gut, aber genau diese Sorte Kopie hat an diesem Wochenende dreimal
zugeschlagen (doppelter Konventions-Mapper → 500; zwei Passagen-Definitionen
→ Treffer ohne Inhalt; beinahe eine dritte FTS-Config).
"""

from __future__ import annotations

from typing import Final

# Obergrenze des ausgelieferten Snippets. Eine WorkArea-Passage traegt bis zu
# 4000 Zeichen (`wa_chunks._MAX_CHUNK_CHARS`), eine KB-Aussage ist kurz — die
# Grenze schuetzt vor allem den Kontext des Agenten.
SNIPPET_MAX_CHARS: Final = 200


def snippet(text: str) -> str:
    """Kuerzt `text` auf Snippet-Laenge (harte Kappung + Ellipse).

    Bewusst hart geschnitten statt an Wortgrenzen: die Ellipse sagt an, dass
    es weitergeht, und eine wortweise Kappung wuerde je nach Sprache
    unterschiedlich viel liefern.
    """
    if len(text) <= SNIPPET_MAX_CHARS:
        return text
    return text[: SNIPPET_MAX_CHARS - 1].rstrip() + "…"
