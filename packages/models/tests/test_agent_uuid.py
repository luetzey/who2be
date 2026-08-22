from who2be_models import AGENT_UUID_PATTERN, AGENT_UUID_RE, is_canonical_agent_uuid

CANONICAL = "2f1c4d6e-8a90-4b12-9c34-56789abcdef0"


def test_canonical_form_is_accepted() -> None:
    assert is_canonical_agent_uuid(CANONICAL)
    assert is_canonical_agent_uuid(CANONICAL.upper())


def test_alias_spellings_are_rejected() -> None:
    # `uuid.UUID(...)` akzeptiert diese Formen — die kanonische Pruefung bewusst
    # nicht, sonst waeren mehrere Schreibweisen mehrere Resource-Identitaeten.
    for alias in (
        CANONICAL.replace("-", ""),
        f"urn:uuid:{CANONICAL}",
        f"{{{CANONICAL}}}",
        f" {CANONICAL}",
        f"{CANONICAL} ",
        "not-a-uuid",
    ):
        assert not is_canonical_agent_uuid(alias)


def test_pattern_is_unanchored_for_embedding() -> None:
    # `AGENT_UUID_PATTERN` muss ohne eigene Anker daherkommen, damit Aufrufer
    # (z. B. Pfad-Regexe) es in ein groesseres Muster einbetten koennen.
    assert not AGENT_UUID_PATTERN.startswith("^")
    assert not AGENT_UUID_PATTERN.endswith("$")
    assert AGENT_UUID_RE.match(CANONICAL) is not None
    assert AGENT_UUID_RE.match(f"x{CANONICAL}") is None
