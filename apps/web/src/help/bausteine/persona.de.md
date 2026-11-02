---
title: Persona
description: Wer dein Agent ist, wie er klingt und wo seine Grenzen liegen.
section: bausteine
order: 10
updated: 2026-10-23
audience: all
---

Die Persona sagt dem Agenten, wer er ist. Sie ist das Erste, was er in einem neuen Chat aus Who2Be lädt. Du findest alle Personas in der Navigation unter **Personas**.

## Was in eine Persona gehört [#felder]

- **Identität:** Name und eine kurze Beschreibung, wofür die Persona zuständig ist. Beides taucht in Listen und Auswahlfeldern auf.
- **Profil:** Rolle, Tonfall, Beispiele und Ausnahmen. Daraus leitet der Agent ab, wie er antworten soll. Konkrete Beispiele wirken besser als lange Stichpunkt-Listen.
- **Modi (optional):** Varianten für verschiedene Situationen, siehe unten.
- **Tags:** Stichwörter für Suche und Gruppierung.

Im Profil fügst du mit `/` Verweise ein, zum Beispiel ein einzelnes Playbook, eine Resource oder den Playbook-Katalog. Beim Abruf ersetzt Who2Be sie durch die aktuelle Fassung.

## Modi [#modi]

Ein Modus ist eine situative Variante der Persona, etwa „Coaching“ und „Analyse“. Jeder Modus hat:

- **Trigger:** Schlüsselwörter, bei denen der Modus greift. Ein Modus ohne Trigger ist der Standard-Modus. Es gibt höchstens einen.
- **Identity-Ergänzung**, **Output-Stil** und **Anti-Patterns:** was in diesem Modus anders ist.
- **Playbook (optional):** ein Ablauf, der zu diesem Modus gehört.

Passt kein Trigger, arbeitet der Agent im Standard-Modus.

## Wie lang darf eine Persona sein? [#laenge]

Die Persona lädt der Agent in jedem Chat ganz. Je länger sie ist, desto mehr Platz nimmt sie ein und desto schlechter befolgt er einzelne Regeln. Deshalb gibt es Richtwerte:

- **Profil:** Richtwert 400 Wörter, Hinweis ab 600.
- **Ein Modus** (alle drei Felder zusammen): Richtwert 150 Wörter, Hinweis ab 250.
- **Zahl der Modi:** Richtwert 3, Hinweis ab 5.
- **Playbook-Inhalt:** Richtwert 1 000 Wörter, Hinweis ab 1 500.

Unter dem Editor siehst du, wo du stehst, etwa „412 Wörter · Richtwert 400“. Ab der Hinweis-Schwelle steht dort „über dem Richtwert“ mit einem Vorschlag. Das ist keine Grenze: Who2Be speichert trotzdem. Codeblöcke zählen nicht mit, ein eingefügter Verweis zählt als ein Wort.

Wird es zu lang, hilft meist eins davon:

- **Abläufe** („erst …, dann …“) gehören in ein [Playbook](/help/playbooks). Im Profil bleibt ein Verweis darauf.
- **Nachschlagewissen** wie Tabellen, Listen und Vorlagen gehört in eine [Resource](/help/resources).
- **Modi**, die sich kaum unterscheiden, legst du zusammen.

## Versionen und Aktivieren [#versionen]

Jede Änderung erzeugt eine neue Version, zuerst als Entwurf. Ein Entwurf wirkt noch nicht. Bist du fertig, klickst du auf **Zur Freigabe einreichen**. Ein Admin prüft die Version und klickt auf **Aktivieren** oder schickt sie mit **Zurück in den Entwurf** zurück. Erst die aktive Version lädt der Agent.

Ein Agent lässt sich nur einschalten, wenn seine Persona aktiv ist. Fehlt das, zeigt die Agent-Seite „Noch nicht aktivierbar“.

## Tipps [#tipps]

- Schreib das Profil so, wie du einem neuen Kollegen die Rolle erklären würdest.
- Leg Abläufe nicht ins Profil, sondern in [Playbooks](/help/playbooks). So bleibt die Persona kurz.
- Nachschlagewissen gehört in [Resources](/help/resources).
