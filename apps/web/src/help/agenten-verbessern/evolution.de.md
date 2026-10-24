---
title: Agenten weiterentwickeln
description: In vier Schritten von der Rückmeldung zur besseren Version.
section: agenten-verbessern
order: 30
updated: 2026-10-23
audience: all
---

Dein Agent wird besser, wenn du sagst, was nicht passt, und prüfst, ob die Änderung wirkt. Auf der Seite deines Agenten zeigt der Tab **Weiterentwicklung** die vier Schritte und was gerade auf dich wartet.

## Wer was tut [#rollen]

- **Du entscheidest.** Welche Änderung kommt, ob ein Entwurf aktiv wird und ob sie gewirkt hat, legst du fest.
- **Der Agent schildert.** Der betroffene Agent beschreibt aus seiner Sicht, was passiert ist. Er bewertet sich nicht selbst.
- **Der Builder moderiert.** Er führt durch das Review, ordnet zu und legt Entwürfe an. Er entscheidet nichts und schließt keine Rückmeldungen ab.

## ① Sammeln [#sammeln]

Gib eine Rückmeldung, wenn der Agent etwas falsch macht. Auch Agenten melden Rückmeldungen selbst. Wie das geht, steht unter [Rückmeldungen und Fälle](/help/feedback-and-cases#rueckmeldung).

Ordne Rückmeldungen einem Baustein zu, zum Beispiel dem Playbook, das falsch war. Eingeordnete Rückmeldungen sind bereit für das Review.

## ② Besprechen [#besprechen]

Klick auf **Review vorbereiten**:

1. Wähle die Rückmeldungen aus. Eine bis drei sind ideal, mehr machen das Review lang.
2. Who2Be stellt die Lage zusammen: offene Rückmeldungen, Nutzungen und Signale je Version.
3. Klick auf **Im Client starten** und führe das Review in Claude mit dem Builder.
4. Hol die Sicht des Agenten ein, wenn sie noch fehlt. Wie das geht, steht direkt darunter.

Der Builder schlägt Änderungen vor. Entscheiden tust du. Vereinbarte Änderungen erscheinen danach im nächsten Schritt.

### Sicht des Agenten [#sicht-des-agenten]

Zu jeder Rückmeldung gibt der betroffene Agent eine Schilderung ab: welcher Anweisung er gefolgt ist, was ihm gefehlt hat und wo sich Anweisungen widersprochen haben. Die Schilderung beschreibt, sie bewertet nicht. Nur der Agent selbst kann sie abgeben. Der Builder darf das nicht für ihn tun.

Fehlt die Schilderung, sagt dir das der Builder im Review. Läuft der Agent in einem anderen Programm, etwa in Claude Desktop oder Hermes, gehst du so vor:

1. Öffne die Rückmeldung und kopier ihre ID über das Menü **⋯** mit **ID kopieren**.
2. Bitte den Agenten in seinem eigenen Chat, seine Schilderung zur Rückmeldung mit dieser ID abzugeben.
3. Geht das nicht, lass dir seine Sicht im Chat beschreiben und füg den Wortlaut im Review beim Builder ein.

Die Schilderung erscheint danach bei der Rückmeldung unter **Schilderung des Agenten**.

## ③ Umsetzen [#umsetzen]

Jede vereinbarte Änderung wird ein Entwurf am Baustein, etwa eine neue Version des Playbooks. Prüfe den Entwurf und aktiviere ihn. Erst dann arbeitet der Agent mit der neuen Fassung. Die zugehörigen Rückmeldungen stehen jetzt auf **Geändert**.

## ④ Prüfen [#pruefen]

Zum vereinbarten Termin erscheint die Nachkontrolle unter „Zu erledigen“. Dort beantwortest du „Hat es gewirkt?“.

- **Ja:** Die Rückmeldung steht auf **Hat gewirkt**.
- **Nein:** Die Rückmeldung ist wieder offen, und der Kreislauf beginnt von vorn.

## Prüffälle [#prueffaelle]

Aus einer Rückmeldung kann ein Prüffall werden. Er beschreibt Eingabe und erwartetes Verhalten. Der Tab **Prüffälle** am Agenten sammelt sie. So prüfst du bei jeder neuen Version, ob alte Fehler wiederkommen.

Tipp: Lieber oft kleine Reviews als selten ein großes. Was sich wiederholt, zeigt dir der Tab **Muster** unter **Feedback**, siehe [Muster](/help/feedback-and-cases#muster).
