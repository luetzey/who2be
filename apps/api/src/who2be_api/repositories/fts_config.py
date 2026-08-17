"""Die EINE Abbildung Sprache → Postgres-Textsuch-Config.

Drei Suchpfade brauchen dieselbe Regel — `content_chunk` (0070), `wa_chunk`
(0076) und `kb_node` (0082) —, und sie brauchen sie zweimal je Pfad: einmal
im Ausdruck der generierten `search`-Spalte (SQL, in der Migration) und
einmal in der Query, die diese Spalte trifft. Passen die beiden nicht
zusammen, findet die Query ihren eigenen Index nicht — und zwar lautlos: es
gibt keinen Fehler, nur keine Treffer.

Deshalb steht der Ausdruck hier genau einmal statt in jedem Repository. Die
beiden ersten Pfade hielten ihn bis 2026-08-17 als wortgleiche Kopien; der
dritte kam mit Befund B dazu. Parallel gepflegte Definitionen derselben
Sache driften auseinander, ohne dass es auffaellt — an diesem Wochenende hat
genau dieses Muster schon zwei Fehler erzeugt (zwei Mapper fuer dieselbe
Zeile → 500 im describe-Pfad; zwei Definitionen der Passagen-Grenze →
Suchtreffer ohne Inhalt).

Unbekannte Sprachen fallen bewusst auf ``simple`` zurueck: die DB-Schicht ist
fuer Sprachen offen (0069 setzt kein CHECK), die App-Schicht startet mit
de/en (`builder_content.SUPPORTED_LOCALES`). Ein Fallback ist hier die
richtige Antwort — Suchen ohne Stemming ist brauchbar, ein Fehler waere es
nicht.

**Aendert sich diese Abbildung, braucht es eine Migration**, die alle
betroffenen generierten Spalten neu baut. Der Ausdruck hier allein umzu-
stellen wuerde Query und Index auseinanderlaufen lassen.
"""

from __future__ import annotations


def fts_config_expr(locale_column: str) -> str:
    """SQL-Ausdruck, der `locale_column` auf eine `regconfig` abbildet.

    `locale_column` ist die qualifizierte Spalte im jeweiligen Statement
    (z. B. ``c.locale`` oder ``n.locale``) — nur der Alias unterscheidet die
    Aufrufer, die Regel ist dieselbe.
    """
    return (
        f"CASE split_part({locale_column}, '-', 1) "
        "WHEN 'de' THEN 'german'::regconfig "
        "WHEN 'en' THEN 'english'::regconfig "
        "ELSE 'simple'::regconfig END"
    )
