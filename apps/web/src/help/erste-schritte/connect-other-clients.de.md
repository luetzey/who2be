---
title: Andere Programme verbinden
description: Claude Code, Cursor, VS Code und andere Programme mit deinem Agenten verbinden.
section: erste-schritte
order: 30
updated: 2026-10-22
audience: all
---

Who2Be-Agenten funktionieren nicht nur in Claude. Jedes Programm, das Remote-MCP mit Anmeldung (OAuth) kann, holt sich deinen Agenten auf dieselbe Weise ab. Den passenden Weg findest du auf der Seite deines Agenten im Tab **Überblick**, Karte **Verbindung**, unter „Wo nutzt du deine Agenten?“.

## Claude Code [#claude-code]

1. Wähle **Claude Code** und klick auf **Befehl kopieren**.
2. Führe den Befehl im Terminal aus. Er hat diese Form:

```
claude mcp add --transport http who2be-builder https://…
```

3. Beim ersten Aufruf meldest du dich bei Who2Be an und bestätigst den Agenten.
4. Schreib den Test-Satz aus der Karte, zum Beispiel „Wer bist du? Lade deine Persona aus Who2Be.“

Die Adresse im Befehl gehört genau zu diesem einen Agenten. Kopiere sie deshalb immer aus der Karte und tipp sie nicht ab.

## Cursor und VS Code [#cursor-vscode]

1. Wähle **Cursor oder VS Code**.
2. Klick auf **Zu Cursor hinzufügen** oder **In VS Code installieren**. Der Editor öffnet sich und fragt einmal nach.
3. Beim ersten Aufruf meldest du dich bei Who2Be an und bestätigst den Agenten.

Klappt der Knopf nicht, öffne „Klappt der Knopf nicht? Von Hand eintragen“. Trag die **Server-URL** im Editor als Remote-MCP-Server mit Transport HTTP ein.

## Etwas anderes [#andere]

Wähle **Etwas anderes**. Who2Be zeigt dir die **Server-URL** zum Kopieren. Trag sie in deinem Programm als Remote-MCP-Server ein. Danach meldest du dich bei Who2Be an, bestätigst den Agenten und schreibst den Test-Satz. Klick zum Schluss auf **Ich habe die Adresse eingetragen**.

Dein Programm muss dafür zwei Dinge können:

- Remote-MCP über HTTP, also nicht nur lokale Server.
- Anmeldung per OAuth, damit du den Zugriff in Who2Be bestätigen kannst.

## Mehrere Agenten [#mehrere]

Jeder Agent hat seine eigene Adresse. Willst du zwei Agenten im selben Programm nutzen, verbindest du beide einzeln. Für Claude steht alles auf der Seite [Mit Claude verbinden](/help/connect-claude#troubleshooting).
