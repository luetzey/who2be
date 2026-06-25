"""Gate-Fehler mit strukturierter Taxonomie (WP-2 / #254, ADR-Vorbild D2).

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


__all__ = ["ApiGateError"]
