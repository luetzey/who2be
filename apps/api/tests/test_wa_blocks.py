"""Unit-Tests (DB-los) fuer den Markdown↔Block-Konverter (`services/wa_blocks`)
und den Passagen-Schnitt (`services/wa_chunks.build_chunks`) — ADR-0047, WP4.

Kern-Invarianten:
- Der Split ist deterministisch und der Render-Roundtrip verlustfrei
  (kind/level/md bleiben stabil; nur die IDs sind frisch).
- Block-IDs sind 8-stellig (a-z0-9), untereinander UND gegen Bestand
  kollisionsfrei.
- `apply_patch` (pure Patch-Op-Logik): replace erbt die Anker-ID,
  insert_after/delete positionieren korrekt, unbekannter Anker → None.
- `build_chunks`: heading_path aus VORFAHREN, fortlaufende `ord`,
  4000-Zeichen-Cap ohne Textverlust.
- `passage_for_anchor`: ein Passagen-Anker (Heading bzw. erster Block vor dem
  ersten Heading) loest die ganze Passage auf, ein Anker mitten drin `None` —
  und die Menge der Passagen-Anker deckt sich mit den Ankern des Index.
"""

from __future__ import annotations

import re
from itertools import chain, repeat

import pytest

from who2be_api.services.wa_blocks import (
    apply_patch,
    new_block_id,
    render_markdown,
    split_markdown,
)
from who2be_api.services.wa_chunks import build_chunks, passage_for_anchor
from who2be_models import DocBlock, DocBlockKind
from who2be_models.workarea import DOC_BLOCK_MD_MAX_LENGTH

_SAMPLE_MD = (
    "# Reklamation\n"
    "\n"
    "Erster Absatz mit Kontext.\n"
    "Zweite Zeile desselben Absatzes.\n"
    "\n"
    "## Eskalation\n"
    "\n"
    "- Stufe eins\n"
    "- Stufe zwei\n"
    "\n"
    "```python\n"
    "def foo():\n"
    "\n"
    "    return 42\n"
    "```\n"
    "\n"
    "Abschliessender Absatz."
)


def test_split_markdown_kinds_und_levels() -> None:
    blocks = split_markdown(_SAMPLE_MD)
    kinds = [(b.kind, b.level) for b in blocks]
    assert kinds == [
        (DocBlockKind.heading, 1),
        (DocBlockKind.paragraph, None),
        (DocBlockKind.heading, 2),
        (DocBlockKind.list, None),
        (DocBlockKind.code, None),
        (DocBlockKind.paragraph, None),
    ]
    # Code-Fence ist EIN Block inkl. Fences und innerer Leerzeile.
    code = blocks[4]
    assert code.md.startswith("```python") and code.md.endswith("```")
    assert "\n\n" in code.md  # Leerzeile im Code splittet NICHT


def test_split_markdown_roundtrip_ist_verlustfrei() -> None:
    """render(split(md), ohne Anker) → erneut splitten ⇒ identische Bloecke."""
    first = split_markdown(_SAMPLE_MD)
    rendered = render_markdown(first, with_anchors=False)
    second = split_markdown(rendered)
    assert [(b.kind, b.level, b.md) for b in first] == [(b.kind, b.level, b.md) for b in second]


def test_block_ids_format_und_eindeutigkeit() -> None:
    existing = {"aaaaaaaa"}
    blocks = split_markdown(_SAMPLE_MD, existing_ids=existing)
    ids = [b.block_id for b in blocks]
    assert len(ids) == len(set(ids))
    assert not set(ids) & existing
    for block_id in ids:
        assert re.fullmatch(r"[a-z0-9]{8}", block_id), block_id


def test_new_block_id_weicht_kollision_aus(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Kollisions-Check greift: der erste (kollidierende) Kandidat wird
    verworfen, der zweite geliefert."""
    # Erst 8x 'a' (kollidiert mit Bestand), dann 8x 'b'.
    feeder = chain(repeat("a", 8), repeat("b", 8))
    monkeypatch.setattr(
        "who2be_api.services.wa_blocks.secrets.choice", lambda _alphabet: next(feeder)
    )
    assert new_block_id({"aaaaaaaa"}) == "bbbbbbbb"


def test_sieben_rauten_sind_kein_heading() -> None:
    blocks = split_markdown("####### kein Heading")
    assert [b.kind for b in blocks] == [DocBlockKind.paragraph]


def test_nummerierte_liste_und_leerer_input() -> None:
    assert split_markdown("") == []
    assert split_markdown("   \n\n  ") == []
    blocks = split_markdown("1. eins\n2. zwei")
    assert [b.kind for b in blocks] == [DocBlockKind.list]


def test_unschliessende_fence_laeuft_bis_zum_ende() -> None:
    blocks = split_markdown("```\nkein Ende")
    assert [b.kind for b in blocks] == [DocBlockKind.code]
    assert blocks[0].md == "```\nkein Ende"


def test_oversize_block_wird_gesplittet() -> None:
    md = "x" * (DOC_BLOCK_MD_MAX_LENGTH + 10)
    blocks = split_markdown(md)
    assert len(blocks) == 2
    assert "".join(b.md for b in blocks) == md
    assert all(len(b.md) <= DOC_BLOCK_MD_MAX_LENGTH for b in blocks)


def test_render_markdown_anker_annotation() -> None:
    blocks = split_markdown("# Titel\n\nAbsatz.\n\n```\ncode\n```")
    rendered = render_markdown(blocks, with_anchors=True)
    heading, paragraph, code = blocks
    # Heading + Absatz: Anker am Zeilen-/Block-Ende.
    assert f"# Titel [#{heading.block_id}]" in rendered
    assert f"Absatz. [#{paragraph.block_id}]" in rendered
    # Code: Anker auf EIGENER Zeile nach der schliessenden Fence.
    assert f"```\n[#{code.block_id}]" in rendered
    # Ohne Anker bleibt das Markdown unangetastet.
    assert "[#" not in render_markdown(blocks, with_anchors=False)


# ------------------------------------------------------------------ apply_patch


def _blocks(*mds: str) -> list[DocBlock]:
    return [
        DocBlock(block_id=f"blk{i:05d}", kind=DocBlockKind.paragraph, md=md)
        for i, md in enumerate(mds)
    ]


def test_apply_patch_replace_erbt_anker_id() -> None:
    blocks = _blocks("eins", "zwei", "drei")
    replacement = split_markdown("neu-a\n\nneu-b", {b.block_id for b in blocks})
    result = apply_patch(blocks, "blk00001", "replace", replacement)
    assert result is not None
    assert [b.md for b in result] == ["eins", "neu-a", "neu-b", "drei"]
    # Der ERSTE Ersatz-Block traegt die Anker-ID (Anker-Stabilitaet).
    assert result[1].block_id == "blk00001"
    assert result[2].block_id != "blk00001"


def test_apply_patch_insert_after_und_delete() -> None:
    blocks = _blocks("eins", "zwei")
    inserted = apply_patch(blocks, "blk00000", "insert_after", _blocks("dazwischen"))
    assert inserted is not None
    assert [b.md for b in inserted] == ["eins", "dazwischen", "zwei"]

    deleted = apply_patch(blocks, "blk00000", "delete", [])
    assert deleted is not None
    assert [b.md for b in deleted] == ["zwei"]


def test_apply_patch_unbekannter_anker_liefert_none() -> None:
    assert apply_patch(_blocks("eins"), "gibtsnich", "delete", []) is None


# ------------------------------------------------------------------ build_chunks


def test_build_chunks_heading_path_und_ord() -> None:
    blocks = split_markdown(
        "Praeambel vor dem ersten Heading.\n\n"
        "# Reklamation\n\nGrundlagen.\n\n"
        "## Eskalation\n\nStufenplan.\n\n"
        "# Neues Kapitel\n\nInhalt."
    )
    chunks = build_chunks(blocks)
    assert [c.ord for c in chunks] == list(range(len(chunks)))
    # Praeambel ankert auf dem ERSTEN Block (jeder doc-Block traegt eine ID).
    assert chunks[0].block_id == blocks[0].block_id
    assert chunks[0].heading_path == ""
    # H2-Sektion traegt die VORFAHREN-Kette (eigene Ueberschrift nur im Text).
    eskalation = next(c for c in chunks if "Stufenplan." in c.text)
    assert eskalation.heading_path == "Reklamation"
    assert eskalation.text.startswith("Eskalation")
    # Neues H1 setzt den Pfad zurueck.
    kapitel = next(c for c in chunks if "Inhalt." in c.text)
    assert kapitel.heading_path == ""


def test_build_chunks_cap_splittet_ohne_verlust() -> None:
    absatz = "wort " * 1_000  # ~5000 Zeichen > 4000er-Cap
    blocks = split_markdown(f"# Lang\n\n{absatz.strip()}")
    chunks = build_chunks(blocks)
    assert len(chunks) >= 2
    # Alle Teile derselben Sektion: gleicher Anker, fortlaufende ord.
    assert {c.block_id for c in chunks} == {blocks[0].block_id}
    assert all(len(c.text) <= 4_000 for c in chunks)
    zusammen = "".join(c.text for c in chunks)
    assert "wort" in zusammen and len(zusammen) >= len(absatz.strip())


def test_build_chunks_leere_blockliste() -> None:
    assert build_chunks([]) == []


# -------------------------------------------------------------- passage_for_anchor


def test_passage_for_anchor_liefert_die_ganze_sektion() -> None:
    """Der Anker eines Suchtreffers muss die PASSAGE aufmachen, nicht die Zeile.

    Ein Heading-Anker liefert Ueberschrift + zugehoerigen Text bis zum
    naechsten Heading — genau die Bloecke, aus denen `build_chunks` den
    Indextext baut. Vorher gab derselbe Anker nur den Heading-Block zurueck:
    ein Treffer fuehrte zur Ueberschrift ohne eine Zeile Inhalt.
    """
    blocks = split_markdown(
        "Praeambel vor dem ersten Heading.\n\n"
        "# Reklamation\n\nGrundlagen.\n\n"
        "## Eskalation\n\nStufenplan.\n\nZweiter Absatz der Eskalation.\n\n"
        "# Neues Kapitel\n\nInhalt."
    )
    by_md = {block.md: block for block in blocks}

    eskalation = passage_for_anchor(blocks, by_md["## Eskalation"].block_id)
    assert eskalation is not None
    assert [b.md for b in eskalation] == [
        "## Eskalation",
        "Stufenplan.",
        "Zweiter Absatz der Eskalation.",
    ]

    # Die Passage endet am naechsten Heading — auch bei tieferer Ebene.
    reklamation = passage_for_anchor(blocks, by_md["# Reklamation"].block_id)
    assert reklamation is not None
    assert [b.md for b in reklamation] == ["# Reklamation", "Grundlagen."]

    # Praeambel: ankert auf ihrem ersten Block.
    praeambel = passage_for_anchor(blocks, blocks[0].block_id)
    assert praeambel is not None
    assert [b.md for b in praeambel] == ["Praeambel vor dem ersten Heading."]


def test_passage_for_anchor_none_mitten_in_der_passage() -> None:
    """Ein Anker INNERHALB einer Passage ist keine Passage.

    `None` heisst fuer den Lesepfad „bleib beim einzelnen Block" — das ist der
    Blick, den ein Agent vor einem `patch_artifact` braucht.
    """
    blocks = split_markdown("# Reklamation\n\nGrundlagen.\n\nZweiter Absatz.")
    mitten_drin = next(b for b in blocks if b.md == "Zweiter Absatz.")
    assert passage_for_anchor(blocks, mitten_drin.block_id) is None
    assert passage_for_anchor(blocks, "gibtsnich") is None


def test_passage_anker_sind_genau_die_indexanker() -> None:
    """Jeder Anker, den der Index vergibt, loest im Lesepfad eine Passage auf.

    Das ist die Kopplung, um die es geht: waeren es zwei Mengen, liefe ein
    Suchtreffer wieder ins Leere — nur eben nicht bei jedem Dokument.
    """
    blocks = split_markdown("Praeambel.\n\n# A\n\nText A.\n\n## A1\n\nText A1.\n\n# B\n\nText B.")
    for chunk in build_chunks(blocks):
        assert passage_for_anchor(blocks, chunk.block_id) is not None
