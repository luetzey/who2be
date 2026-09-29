"""Pruefall + Prueflauf (ADR-0053 Abschnitt 3.2, Lernschleife Phase B).

Spiegel der Tabellen `test_case` / `test_run` aus
`apps/api/src/who2be_api/migrations/0089_test_case_test_run.sql`.

- **Pruefall** (`test_case`): Eingabe an einen Agenten plus die vom Menschen
  formulierte Erwartung. Der Inhalt ist unveraenderlich; aendern laesst sich
  nur `status` (`active` -> `retired`). Eine Korrektur ist ein neuer Pruefall
  mit `supersedes_id` auf den alten. `agent_id` ist Pflicht, das Element
  (`entity_type`/`entity_id`) optional (Weiche P4, Abschnitt 3.2.1).
- **Prueflauf** (`test_run`): ein Ergebnis fuer eine Elementversion,
  append-only. `attestation` setzt der Server aus dem Aufrufweg, nie aus dem
  Request-Body — `TestRunCreate` hat deshalb kein solches Feld.

Die Konsistenzregel fuer `runs_total`/`runs_passed`/`verdict` steht als
`verdict_consistent` hier (eine Quelle) und zusaetzlich als DB-CHECK. Das
Request-Modell prueft sie bewusst NICHT per Validator: die API antwortet
darauf mit dem eigenen ProblemReason `test_run_verdict_inconsistent` (ADR 6.1),
nicht mit dem generischen Pydantic-422.

Die Klassen tragen `__test__ = False`, damit pytest sie beim Import in
Testmodule nicht als Testklassen einzusammeln versucht (Praefix `Test`).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from who2be_models.status_history import EntityType

# Laengen-Deckel, gespiegelt aus den CHECKs der Migration 0089 (ADR 3.2,
# Anhang B).
TEST_CASE_TITLE_MAX_LENGTH = 200
TEST_CASE_INPUT_MAX_LENGTH = 8_000
TEST_CASE_EXPECTED_MAX_LENGTH = 2_000
TEST_RUN_OUTPUT_MAX_LENGTH = 4_000


class TestCaseStatus(StrEnum):
    """Lebenszyklus eines Pruefalls: `active` -> `retired` (kein Rueckweg)."""

    __test__: ClassVar[bool] = False

    active = "active"
    retired = "retired"


class TestCheckKind(StrEnum):
    """Wie ein Ergebnis bewertet wird.

    `human_rule`: ein Mensch bewertet (der Client meldet nur Ausgabe mit
    `verdict='error'`). `must_contain`/`must_not_contain`: deterministisch
    gegen `check_pattern`.
    """

    __test__: ClassVar[bool] = False

    human_rule = "human_rule"
    must_contain = "must_contain"
    must_not_contain = "must_not_contain"


class TestCaseCreatedByKind(StrEnum):
    """Wer den Pruefall angelegt hat (der Builder darf anlegen)."""

    __test__: ClassVar[bool] = False

    human = "human"
    agent = "agent"


class TestVerdict(StrEnum):
    """Urteil eines Prueflaufs. `pass` nur bei n/n bestandenen Laeufen."""

    __test__: ClassVar[bool] = False

    pass_ = "pass"
    fail = "fail"
    error = "error"


class TestAttestation(StrEnum):
    """Herkunft eines Ergebnisses — serverseitig aus dem Aufrufweg gesetzt.

    `client_self_report`: Meldung ueber Agent-Token/MCP (Selbstauskunft des
    Clients, Weiche P1). `human_rating`: Bewertung eines Menschen ueber die
    Web-Session; verlangt `reported_by_user_id`.
    """

    __test__: ClassVar[bool] = False

    client_self_report = "client_self_report"
    human_rating = "human_rating"


def verdict_consistent(runs_total: int, runs_passed: int, verdict: TestVerdict) -> bool:
    """True, wenn Laufzahlen und Urteil zusammenpassen (ADR 3.2, 6.1).

    `runs_total >= 1`, `0 <= runs_passed <= runs_total` und `pass` nur bei
    `runs_passed == runs_total`. Dieselbe Regel steht als CHECK in
    Migration 0089; der Service (B2) prueft hier vorab, um mit
    `test_run_verdict_inconsistent` statt einem DB-Fehler zu antworten.
    """
    if runs_total < 1 or not 0 <= runs_passed <= runs_total:
        return False
    return verdict is not TestVerdict.pass_ or runs_passed == runs_total


class TestCaseCreate(BaseModel):
    """Eingabe fuer einen neuen Pruefall.

    `created_by_kind`/`created_by` setzt der Server aus dem Aufrufweg; sie sind
    deshalb nicht Teil des Modells.
    """

    __test__: ClassVar[bool] = False
    model_config = ConfigDict(extra="forbid")

    agent_id: UUID
    entity_type: EntityType | None = None
    entity_id: UUID | None = None
    title: str = Field(min_length=1, max_length=TEST_CASE_TITLE_MAX_LENGTH)
    input: str = Field(min_length=1, max_length=TEST_CASE_INPUT_MAX_LENGTH)
    expected_behavior: str = Field(min_length=1, max_length=TEST_CASE_EXPECTED_MAX_LENGTH)
    check_kind: TestCheckKind = TestCheckKind.human_rule
    check_pattern: str | None = Field(default=None, min_length=1)
    origin_case_id: UUID | None = None
    origin_measure_id: UUID | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> TestCaseCreate:
        """Spiegelt die Zeilen-CHECKs der Migration (Element-Paar, Muster)."""
        if (self.entity_type is None) != (self.entity_id is None):
            raise ValueError("entity_type und entity_id nur gemeinsam angeben.")
        needs_pattern = self.check_kind is not TestCheckKind.human_rule
        if needs_pattern != (self.check_pattern is not None):
            raise ValueError(
                "check_pattern ist bei must_contain/must_not_contain Pflicht "
                "und bei human_rule nicht erlaubt."
            )
        return self


class TestCaseRead(BaseModel):
    """Ein Pruefall, wie er gespeichert ist."""

    __test__: ClassVar[bool] = False
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    agent_id: UUID
    entity_type: EntityType | None
    entity_id: UUID | None
    title: str
    input: str
    expected_behavior: str
    check_kind: TestCheckKind
    check_pattern: str | None
    origin_case_id: UUID | None
    origin_measure_id: UUID | None
    status: TestCaseStatus
    supersedes_id: UUID | None
    created_by_kind: TestCaseCreatedByKind
    created_by: UUID
    created_at: datetime


class TestRunCreate(BaseModel):
    """Ein gemeldetes Ergebnis fuer einen Pruefall.

    Kein `attestation`-Feld (wird aus dem Aufrufweg gesetzt) und
    `extra="forbid"`, damit ein mitgeschicktes Feld abgewiesen statt still
    verworfen wird. Die n/n-Regel prueft `verdict_consistent`, nicht dieses
    Modell (s. Modul-Doc).
    """

    __test__: ClassVar[bool] = False
    model_config = ConfigDict(extra="forbid")

    test_case_id: UUID
    runs_total: int
    runs_passed: int
    verdict: TestVerdict
    output_excerpt: str | None = Field(default=None, max_length=TEST_RUN_OUTPUT_MAX_LENGTH)


class TestRunRead(BaseModel):
    """Ein gespeichertes Ergebnis (append-only)."""

    __test__: ClassVar[bool] = False
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    test_case_id: UUID
    subject_entity_type: EntityType
    subject_version_id: UUID
    runs_total: int
    runs_passed: int
    verdict: TestVerdict
    output_excerpt: str | None
    attestation: TestAttestation
    model_provider: str | None
    model_name: str | None
    reported_by_agent_id: UUID | None
    reported_by_user_id: UUID | None
    created_at: datetime
