---
title: Resources
description: Wissen in Blöcken, das dein Agent gezielt nachliest.
section: bausteine
order: 30
updated: 2026-10-23
audience: all
---

Eine Resource ist ein Wissensdokument: eine FAQ, eine Preisliste, eine Richtlinie. Der Agent liest sie nicht ständig mit, sondern holt sich den Teil, den er gerade braucht. Du findest alle Resources in der Navigation unter **Resources**.

## Aufbau [#aufbau]

- **Identität:** Name und eine kurze Beschreibung, worum es geht.
- **Inhalt:** der eigentliche Text im Block-Editor.
- **Tags:** für Suche und Filter. Auch der Agent kann Resources nach Tag auflisten.

## Blöcke [#bloecke]

Jede Überschrift in einer Resource bildet einen Block. Ein Agent kann einen einzelnen Block laden statt des ganzen Dokuments. Das spart Platz in seinem Kontext und hält die Antwort genau.

Gliedere eine Resource deshalb mit klaren Überschriften, zum Beispiel eine je Frage oder je Thema.

## Resources einbinden [#einbinden]

- **In ein Playbook:** Verlinke im Playbook einen Block der Resource. Der Agent lädt dann genau diesen Abschnitt, wenn er das [Playbook](/help/playbooks) ausführt.
- **In die Persona:** Mit `/` fügst du im Profil der [Persona](/help/persona) eine Resource oder den Resource-Katalog ein.
- **Als Sub-Resource:** Eine Resource kann auf weitere Resources verweisen, die der Agent bei Bedarf nachlädt.

Auf der Seite einer Resource siehst du unter „Verlinkt in“, wo sie schon verwendet wird.

## Versionen und Aktivieren [#versionen]

Jede Änderung erzeugt eine neue Version, zuerst als Entwurf. Ein Entwurf wirkt noch nicht. Bist du fertig, klickst du auf **Zur Freigabe einreichen**. Ein Admin prüft die Version und klickt auf **Aktivieren** oder schickt sie mit **Zurück in den Entwurf** zurück. Erst die aktive Version liest der Agent.

## Tipps [#tipps]

- Ein Thema je Resource. Lieber drei kurze als eine lange.
- Schreib Fakten, keine Anweisungen. Wie der Agent etwas tun soll, gehört ins Playbook.
- Halte Daten wie Preise oder Fristen aktuell. Agenten melden veraltete Stellen als Feedback.
