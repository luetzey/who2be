---
title: Rückmeldungen und Fälle
description: Wie du sagst, was dein Agent anders machen soll, und was daraus wird.
section: agenten-verbessern
order: 10
updated: 2026-10-22
audience: all
---

Dein Agent wird besser, wenn du sagst, was nicht passt. Dafür gibt es zwei Wege: kurze Signale zu einem Baustein und Rückmeldungen zu einer konkreten Situation. Beides findest du in der Navigation unter **Feedback**.

## Signale zu einem Baustein [#signale]

Ein Signal ist eine kurze Bewertung eines Bausteins, also einer Persona, eines Playbooks oder einer Resource: **Hilfreich**, **Veraltet**, **Falsch** oder **Unklar**, dazu eine optionale Notiz.

- Agenten geben Signale selbst, wenn ihnen beim Arbeiten etwas auffällt.
- Du gibst ein Signal auf der Seite des Bausteins mit **Feedback geben**.

Im Tab **Bausteine** siehst du je Baustein, wie oft er genutzt wurde und wie die Signale ausfallen. So erkennst du, welcher Baustein Pflege braucht.

## Eine Rückmeldung geben [#rueckmeldung]

Eine Rückmeldung beschreibt eine konkrete Situation, in der ein Agent anders handeln sollte. Klick unter **Feedback** auf **Rückmeldung geben**, wähle den Agenten und füll diese Felder aus:

- **Lage:** Was war los? Zum Beispiel „Kunde fragt nach einer Rechnung von 2024“.
- **Getan:** Was hat der Agent gemacht?
- **Erwartet:** Was hätte er tun sollen?
- **Folge (optional):** Was ist dadurch passiert?

Füg keine Passwörter oder Kundendaten ein. Agenten können Rückmeldungen auch selbst melden, wenn sie merken, dass etwas nicht passt.

## Was mit einer Rückmeldung passiert [#ablauf]

Jede Rückmeldung hat einen Zustand:

1. **Offen:** neu gemeldet.
2. **Eingeordnet:** einem Baustein zugeordnet, etwa dem Playbook, das falsch war.
3. **In Arbeit:** Eine Änderung am Baustein ist vereinbart.
4. **Geändert:** Die neue Version ist aktiv.
5. **Hat gewirkt:** Die Nachkontrolle hat bestätigt, dass die Änderung hilft.

Passt eine Rückmeldung nicht, kannst du sie **verwerfen**. Kommt das Problem zurück, steht sie wieder auf **Wieder offen**. Aus einer Rückmeldung kann auch ein Prüffall werden, der jede neue Version des Agenten testet.

## Muster [#muster]

Im Tab **Muster** zählt Who2Be ähnliche Rückmeldungen und Lernvorschläge. Ab einer festen Zahl erscheint ein Muster, zum Beispiel „Ähnliche Rückmeldungen 3×“. Who2Be deutet dabei nichts, es zählt nur. Was du daraus machst, entscheidest du.

## Probleme mit Who2Be selbst [#problem-melden]

Klappt etwas an Who2Be selbst nicht, etwa ein Werkzeug-Aufruf oder eine Seite, nutze **Problem melden**. Das ist keine Rückmeldung zu deinem Agenten, sondern eine Meldung an uns.

Wie aus Rückmeldungen eine bessere Version wird, steht unter [Agenten weiterentwickeln](/help/evolution).
