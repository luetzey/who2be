"""API-Fehler mit strukturierter Taxonomie (WP-2 / #254; ADR-0051 / #436).

Zwei Klassen, EIN Vokabular (`who2be_models.ProblemReason`):

- `ApiGateError` — die zentralen Autorisierungs- und State-Machine-Gates.
  Serialisiert als RFC-7807-`ApiProblem` (``application/problem+json``).
- `ApiError` — alles uebrige. Serialisiert schlank als `ApiErrorBody`
  (``application/json``: `detail` + `reason` + optional `params`).

Warum zwei Huellen: die Gate-Antworten sind ein bestehender Vertrag mit
eigenem Content-Type; sie auf das schlanke Format zu ziehen (oder umgekehrt)
waere ein Breaking Change am gesamten Fehler-Contract (#402, Weg C). Der
Client interessiert sich nur fuer `reason` und hat deshalb trotzdem genau
einen Uebersetzungspfad.

`ApiGateError` ist die eine Exception, die alle zentralen Autorisierungs- und
State-Machine-Gates werfen, statt nackter `HTTPException`. Sie traegt nur den
Call-Site-spezifischen Teil — `(status, reason, actionable_by, detail)` — und
ueberlaesst `type`/`title`/`request_id` dem zentralen Exception-Handler in
`main.py` (analog `PromoteValidationError`). Der Handler serialisiert daraus ein
`ApiProblem` als ``application/problem+json``.

`status` und `detail` spiegeln die Felder, die Call-Sites historisch ueber
`HTTPException` gefuehrt haben — Unit-Tests, die ein Gate direkt aufrufen,
lesen `exc.value.status`/`exc.value.detail` weiterhin gleich.
"""

from fastapi import HTTPException

from who2be_models import ActionableBy, ProblemReason


class ApiGateError(Exception):
    """Strukturierter Gate-Fehler — zentral zu ``application/problem+json``.

    Args:
        status: HTTP-Statuscode (z. B. 403, 409).
        reason: Stabiler Enum-Grund aus der Taxonomie (D1).
        actionable_by: Wer den Fehler beheben kann (`agent`/`human`/`none`).
        detail: Menschenlesbare Begruendung (RFC-7807 `detail`).
    """

    def __init__(
        self,
        *,
        status: int,
        reason: ProblemReason,
        actionable_by: ActionableBy,
        detail: str,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.reason: ProblemReason = reason
        self.actionable_by: ActionableBy = actionable_by
        self.detail = detail


class ApiError(HTTPException):
    """`HTTPException` plus stabiler `reason` — die zweite Serialisierung (ADR-0051).

    Bewusst eine **Unterklasse von `HTTPException`**, nicht ein neuer
    Exception-Ast: die rund 79 Bestands-Stellen mit reinem ``detail=`` werden
    Welle fuer Welle (#402 W1-Wn) hierher gezogen, und solange sie
    `HTTPException` bleiben, gilt fuer sie unveraendert alles, was heute gilt —
    `except HTTPException`, `exc.status_code`, `exc.detail`, Header. Eine
    migrierte Stelle unterscheidet sich fuer den Aufrufer nur um das
    zusaetzliche Feld im Body.

    Starlette waehlt den Handler entlang der MRO, `ApiError` steht darin vor
    `HTTPException` — deshalb greift `_on_api_error` in `main.py` genau fuer
    diese Klasse und der FastAPI-Default fuer alle anderen. Nicht migrierte
    Fehler bleiben damit byte-identisch.

    Abgrenzung zu `ApiGateError`: dasselbe Vokabular (`ProblemReason`), andere
    Huelle. Die zentralen Autorisierungs-/State-Machine-Gates liefern
    RFC-7807-Bodys mit `actionable_by`/`request_id`; hier reicht
    `detail` + `reason` (+ `params`).

    Args:
        status_code: HTTP-Statuscode — unveraendert gegenueber der Stelle vorher.
        detail: Menschenlesbarer Text — ebenfalls unveraendert (additiv!).
        reason: Stabiler Enum-Grund aus `ProblemReason`.
        params: Werte fuer die Platzhalter der uebersetzten Client-Meldung.
        headers: Wie bei `HTTPException` (z. B. ``WWW-Authenticate``).
    """

    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        reason: ProblemReason,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.reason: ProblemReason = reason
        self.params = params


__all__ = ["ApiError", "ApiGateError"]
