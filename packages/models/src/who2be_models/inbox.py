"""Aufgaben-Zaehler fuer Glocke, Dashboard-Zeile und Agent-Ueberblick.

Navigation & Transparenz W1 (Spec §2.2, §2.6 a, §5 A1). Eine Aufgabe ist ein
offener Zustand, kein Benachrichtigungs-Eintrag (Weiche N1 a): es gibt kein
gelesen/ungelesen und keine eigene Tabelle. Jede Zahl entsteht aus derselben
Abfrage und derselben Sichtbarkeit wie die zugehoerige Liste.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InboxCounts(BaseModel):
    """Antwort von `GET /inbox/counts[?agent_id]`.

    Je Art eine Zahl. `None` heisst: diese Art gibt es fuer die Rolle des
    Aufrufers nicht (Abschnitt entfaellt), `0` heisst: sichtbar, nichts offen.

    - `follow_ups_due`: faellige Nachkontrollen — Massnahmen, deren
      Nachschau-Datum (`measure.follow_up_at`, sonst das des Protokolls)
      heute oder frueher liegt und die weder eingestuft noch zurueckgezogen
      sind. Ab `editor`.
    - `memory_approval`: Gedaechtnis zur Freigabe (`status=pending` ohne
      Lernvorschlaege plus offene Aenderungsvorschlaege). Ab `viewer`; ein
      viewer zaehlt nur das eigene Nutzergedaechtnis.
    - `versions_review`, `system_prompts_review`: Versionen bzw.
      System-Prompts zur Freigabe. Ab `editor` sichtbar, in `total` nur fuer
      `admin` (nur admin darf freigeben). Mit `agent_id` immer `None`: eine
      Version gehoert keinem einzelnen Agenten.
    - `cases_open`: Rueckmeldungen, nicht eingeordnet (Faelle `open` und
      `reopened`). Ab `editor`.
    - `patterns`: Zahl der Muster. Ab `editor`, nie in `total` (Muster haben
      keinen Zustand „erledigt“, ADR-0053 3.7).
    - `total`: die Zahl an der Glocke (Spec §2.2, Spalte „zaehlt in Glocke“).
    """

    model_config = ConfigDict(frozen=True)

    follow_ups_due: int | None = Field(default=None, ge=0)
    memory_approval: int | None = Field(default=None, ge=0)
    versions_review: int | None = Field(default=None, ge=0)
    system_prompts_review: int | None = Field(default=None, ge=0)
    cases_open: int | None = Field(default=None, ge=0)
    patterns: int | None = Field(default=None, ge=0)
    total: int = Field(ge=0)
