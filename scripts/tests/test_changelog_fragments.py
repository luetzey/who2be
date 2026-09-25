"""Tests fuer ``scripts/changelog_fragments.py``.

Der Kern ist :func:`render` — eine reine Funktion ueber Text. Die Tests halten
sie deshalb gegen handgeschriebene CHANGELOG-Ausschnitte statt gegen ein
nachgebautes Repo.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from changelog_fragments import (  # noqa: E402
    CATEGORIES,
    Fragment,
    FragmentError,
    collect_fragments,
    diff_against,
    guard_violation,
    main,
    parse_fragment,
    render,
)

CHANGELOG_MIT_FIXED = """\
# Changelog

Vorspann.

## [Unreleased]

### Fixed

- Ein bestehender Eintrag.

## [0.1.0] - 2026-01-01

### Added

- Der erste Wurf.
"""

CHANGELOG_LEER = """\
# Changelog

Vorspann.

## [Unreleased]

## [0.1.0] - 2026-01-01

### Added

- Der erste Wurf.
"""


def frag(category: str, body: str, name: str = "x") -> Fragment:
    return Fragment(path=Path(f"{name}.{category}.md"), category=category, body=body)


class TestParseFragment:
    def test_liest_slug_typ_und_inhalt(self, tmp_path: Path) -> None:
        path = tmp_path / "oauth-issuer.fixed.md"
        path.write_text("- Etwas repariert.\n", encoding="utf-8")

        fragment = parse_fragment(path)

        assert fragment.category == "fixed"
        assert fragment.slug == "oauth-issuer"
        assert fragment.body == "- Etwas repariert."

    def test_mehrabsaetziger_eintrag_behaelt_einrueckung(self, tmp_path: Path) -> None:
        path = tmp_path / "lang.fixed.md"
        path.write_text("- Erster Absatz.\n\n  Zweiter Absatz, eingerueckt.\n", encoding="utf-8")

        assert parse_fragment(path).body == "- Erster Absatz.\n\n  Zweiter Absatz, eingerueckt."

    @pytest.mark.parametrize("name", ["ohne-typ.md", "zu.viele.punkte.fixed.md", "fixed.md"])
    def test_falsche_namensform_nennt_die_erwartete_form(self, tmp_path: Path, name: str) -> None:
        path = tmp_path / name
        path.write_text("- Inhalt.\n", encoding="utf-8")

        with pytest.raises(FragmentError, match="<slug>.<typ>.md"):
            parse_fragment(path)

    def test_unbekannter_typ_listet_die_erlaubten(self, tmp_path: Path) -> None:
        path = tmp_path / "x.repariert.md"
        path.write_text("- Inhalt.\n", encoding="utf-8")

        with pytest.raises(FragmentError, match="unbekannter Typ"):
            parse_fragment(path)

    def test_leeres_fragment_faellt_auf(self, tmp_path: Path) -> None:
        path = tmp_path / "x.fixed.md"
        path.write_text("\n  \n", encoding="utf-8")

        with pytest.raises(FragmentError, match="leer"):
            parse_fragment(path)

    def test_fliesstext_ohne_listenpunkt_faellt_auf(self, tmp_path: Path) -> None:
        path = tmp_path / "x.fixed.md"
        path.write_text("Etwas repariert.\n", encoding="utf-8")

        with pytest.raises(FragmentError, match="Listenpunkt"):
            parse_fragment(path)


class TestCollectFragments:
    def test_ignoriert_readme_und_gitkeep(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("Anleitung, kein Fragment.\n", encoding="utf-8")
        (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
        (tmp_path / "echt.fixed.md").write_text("- Echt.\n", encoding="utf-8")

        assert [f.slug for f in collect_fragments(tmp_path)] == ["echt"]

    def test_fehlendes_verzeichnis_ist_kein_fehler(self, tmp_path: Path) -> None:
        assert collect_fragments(tmp_path / "gibt-es-nicht") == []

    def test_meldet_alle_fehler_gemeinsam(self, tmp_path: Path) -> None:
        (tmp_path / "a.quatsch.md").write_text("- A.\n", encoding="utf-8")
        (tmp_path / "b.md").write_text("- B.\n", encoding="utf-8")

        with pytest.raises(FragmentError) as excinfo:
            collect_fragments(tmp_path)

        assert "a.quatsch.md" in str(excinfo.value)
        assert "b.md" in str(excinfo.value)

    def test_sortiert_stabil_nach_dateiname(self, tmp_path: Path) -> None:
        for slug in ("zeta", "alpha", "mitte"):
            (tmp_path / f"{slug}.added.md").write_text(f"- {slug}\n", encoding="utf-8")

        assert [f.slug for f in collect_fragments(tmp_path)] == ["alpha", "mitte", "zeta"]


class TestRender:
    def test_ohne_fragmente_bleibt_der_text_byte_gleich(self) -> None:
        assert render(CHANGELOG_MIT_FIXED, []) == CHANGELOG_MIT_FIXED

    def test_haengt_an_bestehenden_unterabschnitt_an(self) -> None:
        out = render(CHANGELOG_MIT_FIXED, [frag("fixed", "- Neu repariert.")])

        assert "- Ein bestehender Eintrag." in out
        assert out.index("- Ein bestehender Eintrag.") < out.index("- Neu repariert.")

    def test_legt_fehlenden_unterabschnitt_an(self) -> None:
        out = render(CHANGELOG_LEER, [frag("added", "- Etwas Neues.")])

        assert "### Added\n\n- Etwas Neues." in out

    def test_haelt_die_kanonische_reihenfolge_ein(self) -> None:
        out = render(
            CHANGELOG_MIT_FIXED,
            [frag("security", "- Sicher."), frag("added", "- Neu."), frag("fixed", "- Fix.")],
        )
        unreleased = out.split("## [0.1.0]")[0]

        assert (
            unreleased.index("### Added")
            < unreleased.index("### Fixed")
            < unreleased.index("### Security")
        )

    def test_ruehrt_aeltere_releases_nicht_an(self) -> None:
        out = render(CHANGELOG_MIT_FIXED, [frag("added", "- Neu.")])
        alt = "## [0.1.0] - 2026-01-01\n\n### Added\n\n- Der erste Wurf.\n"

        assert out.endswith(alt)

    def test_mehrabsaetziger_eintrag_behaelt_seine_zeilen(self) -> None:
        body = "- Kopfzeile.\n\n  Zweiter Absatz mit Einrueckung."
        out = render(CHANGELOG_MIT_FIXED, [frag("fixed", body)])

        assert body in out

    def test_ohne_unreleased_sektion_bricht_es_ab(self) -> None:
        with pytest.raises(FragmentError, match="Unreleased"):
            render("# Changelog\n\n## [0.1.0]\n", [frag("fixed", "- Fix.")])

    def test_jede_kategorie_landet_unter_ihrer_ueberschrift(self) -> None:
        fragments = [frag(c, f"- Eintrag {c}.", name=c) for c in CATEGORIES]
        unreleased = render(CHANGELOG_LEER, fragments).split("## [0.1.0]")[0]

        for category in CATEGORIES:
            heading = f"### {category.capitalize()}"
            assert heading in unreleased
            assert unreleased.index(heading) < unreleased.index(f"- Eintrag {category}.")


class TestCli:
    def test_check_meldet_gute_fragmente_als_erfolg(self, tmp_path: Path) -> None:
        (tmp_path / "a.fixed.md").write_text("- A.\n", encoding="utf-8")

        assert main(["--dir", str(tmp_path), "check"]) == 0

    def test_check_scheitert_an_kaputtem_fragment(self, tmp_path: Path) -> None:
        (tmp_path / "a.quatsch.md").write_text("- A.\n", encoding="utf-8")

        assert main(["--dir", str(tmp_path), "check"]) == 1

    def test_collect_schreibt_und_loescht(self, tmp_path: Path) -> None:
        fragments = tmp_path / "changelog.d"
        fragments.mkdir()
        (fragments / "a.fixed.md").write_text("- Frisch repariert.\n", encoding="utf-8")
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(CHANGELOG_MIT_FIXED, encoding="utf-8")

        code = main(["--dir", str(fragments), "--changelog", str(changelog), "collect"])

        assert code == 0
        assert "- Frisch repariert." in changelog.read_text(encoding="utf-8")
        assert list(fragments.iterdir()) == []

    def test_dry_run_laesst_alles_liegen(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fragments = tmp_path / "changelog.d"
        fragments.mkdir()
        (fragments / "a.fixed.md").write_text("- Frisch repariert.\n", encoding="utf-8")
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(CHANGELOG_MIT_FIXED, encoding="utf-8")

        code = main(
            ["--dir", str(fragments), "--changelog", str(changelog), "collect", "--dry-run"]
        )

        assert code == 0
        assert "- Frisch repariert." in capsys.readouterr().out
        assert changelog.read_text(encoding="utf-8") == CHANGELOG_MIT_FIXED
        assert (fragments / "a.fixed.md").exists()


class TestGuardViolation:
    """Die reine Entscheidung ueber zwei Dateilisten (E2).

    Zulaessig ist ein CHANGELOG-Hunk nur als Signatur eines ``collect``-Laufs:
    derselbe Diff loescht mindestens ein Fragment.
    """

    def test_normaler_pr_mit_changelog_hunk_faellt_durch(self) -> None:
        violation = guard_violation(["CHANGELOG.md", "apps/api/src/x.py"], [])

        assert violation is not None
        assert "changelog.d/<slug>.<typ>.md" in violation

    def test_release_diff_ist_erlaubt(self) -> None:
        changed = ["CHANGELOG.md", "changelog.d/p5-sammeldateien.changed.md"]
        deleted = ["changelog.d/p5-sammeldateien.changed.md"]

        assert guard_violation(changed, deleted) is None

    def test_pr_ohne_changelog_hunk_ist_erlaubt(self) -> None:
        assert guard_violation(["apps/api/src/x.py", "changelog.d/neu.fixed.md"], []) is None

    def test_nur_geloeschte_readme_zaehlt_nicht_als_collect(self) -> None:
        """Sonst liesse sich das Gate durch Loeschen der Anleitung aushebeln."""
        violation = guard_violation(
            ["CHANGELOG.md", "changelog.d/README.md"], ["changelog.d/README.md"]
        )

        assert violation is not None

    def test_geloeschte_datei_ausserhalb_des_verzeichnisses_zaehlt_nicht(self) -> None:
        assert guard_violation(["CHANGELOG.md", "docs/alt.md"], ["docs/alt.md"]) is not None

    def test_leerer_diff_ist_erlaubt(self) -> None:
        assert guard_violation([], []) is None


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    """Ein winziges Repo mit einem CHANGELOG und einem Fragment auf ``main``."""
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    (repo / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n", encoding="utf-8")
    (repo / "changelog.d").mkdir()
    (repo / "changelog.d" / "README.md").write_text("Anleitung.\n", encoding="utf-8")
    (repo / "changelog.d" / "alt.fixed.md").write_text("- Alt.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")


class TestDiffAgainst:
    """Der git-Teil: aus einem echten Diff die zwei Listen gewinnen."""

    def test_trennt_geaenderte_von_geloeschten_pfaden(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        _git(tmp_path, "checkout", "-q", "-b", "release")
        (tmp_path / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [Unreleased]\n\n### Fixed\n\n- Alt.\n", encoding="utf-8"
        )
        (tmp_path / "changelog.d" / "alt.fixed.md").unlink()
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-qm", "release")

        changed, deleted = diff_against("main")

        assert set(changed) == {"CHANGELOG.md", "changelog.d/alt.fixed.md"}
        assert deleted == ["changelog.d/alt.fixed.md"]

    def test_umbenanntes_fragment_zaehlt_nicht_als_geloescht(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ein ``git mv`` laesst das Fragment bestehen — es ist kein ``collect``."""
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        _git(tmp_path, "checkout", "-q", "-b", "feature")
        _git(tmp_path, "mv", "changelog.d/alt.fixed.md", "changelog.d/neu.fixed.md")
        _git(tmp_path, "commit", "-qm", "slug korrigiert")

        changed, deleted = diff_against("main")

        assert set(changed) == {"changelog.d/alt.fixed.md", "changelog.d/neu.fixed.md"}
        assert deleted == []

    def test_unbekannter_ref_meldet_git_stderr(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)

        with pytest.raises(FragmentError, match="fehlgeschlagen"):
            diff_against("gibt-es-nicht")


class TestGuardCli:
    def test_normaler_pr_mit_changelog_hunk_liefert_exit_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        _git(tmp_path, "checkout", "-q", "-b", "feature")
        (tmp_path / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [Unreleased]\n\n- Direkt eingetragen.\n", encoding="utf-8"
        )
        _git(tmp_path, "commit", "-qam", "changelog direkt")

        code = main(["guard", "--base", "main"])

        assert code == 1
        assert "wird nicht direkt bearbeitet" in capsys.readouterr().err

    def test_release_lauf_liefert_exit_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        _git(tmp_path, "checkout", "-q", "-b", "release")
        (tmp_path / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [Unreleased]\n\n### Fixed\n\n- Alt.\n", encoding="utf-8"
        )
        (tmp_path / "changelog.d" / "alt.fixed.md").unlink()
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-qm", "release")

        assert main(["guard", "--base", "main"]) == 0

    def test_umbenanntes_fragment_rettet_den_changelog_hunk_nicht(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Slug-Korrektur per ``git mv`` ist keine Freigabe fuer die Sammeldatei."""
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        _git(tmp_path, "checkout", "-q", "-b", "feature")
        _git(tmp_path, "mv", "changelog.d/alt.fixed.md", "changelog.d/neu.fixed.md")
        (tmp_path / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [Unreleased]\n\n- Eintrag per Rename-Trick.\n", encoding="utf-8"
        )
        _git(tmp_path, "commit", "-qam", "rename plus changelog")

        code = main(["guard", "--base", "main"])

        assert code == 1
        assert "wird nicht direkt bearbeitet" in capsys.readouterr().err

    def test_pr_ohne_changelog_hunk_liefert_exit_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        _git(tmp_path, "checkout", "-q", "-b", "feature")
        (tmp_path / "changelog.d" / "neu.fixed.md").write_text("- Neu.\n", encoding="utf-8")
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-qm", "fragment statt sammeldatei")

        assert main(["guard", "--base", "main"]) == 0


def test_der_echte_changelog_traegt_die_unreleased_sektion() -> None:
    """Regression: ``collect`` haengt an einer Annahme ueber CHANGELOG.md.

    Verschwindet die Sektion (Umbau, Release-Automatik), soll das hier
    auffallen und nicht erst beim naechsten Release.
    """
    repo_root = Path(__file__).resolve().parents[2]
    text = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")

    assert render(text, []) == text
    # Ein Probe-Eintrag laesst sich einfuegen, ohne dass es knallt.
    assert "- Probe." in render(text, [frag("fixed", "- Probe.")])
