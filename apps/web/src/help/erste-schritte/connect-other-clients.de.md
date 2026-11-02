---
title: Andere Programme verbinden
description: Claude Code, Cursor, VS Code, Hermes Agent und andere Programme mit deinem Agenten verbinden.
section: erste-schritte
order: 30
updated: 2026-10-23
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

## Hermes Agent [#hermes]

1. Wähle **Hermes Agent** und klick auf **Befehl kopieren**.
2. Führe den Befehl im Terminal des Rechners aus, auf dem Hermes läuft. Er hat diese Form:

```
hermes mcp add who2be-builder --url https://… --auth oauth
```

3. Hermes öffnet die Anmeldung im Browser oder zeigt einen Link dafür. Melde dich bei Who2Be an und bestätige den Agenten. Läuft Hermes auf einem Server ohne Browser, öffne den Link auf deinem Rechner und füg die Adresse, auf der der Browser am Ende landet, im Terminal ein.
4. Tipp `/reload-mcp` oder starte eine neue Sitzung. Dann schreib den Test-Satz aus der Karte.

Nutzt du mehrere Hermes-Profile, wählst du das Profil mit `-p`, zum Beispiel `hermes -p arbeit mcp add …`. Die Adresse im Befehl gehört genau zu einem Agenten. Kopiere sie deshalb immer aus der Karte. Mehr zu MCP in Hermes steht in der [Hermes-Dokumentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp).

## Etwas anderes [#andere]

Wähle **Etwas anderes**. Who2Be zeigt dir die **Server-URL** zum Kopieren. Trag sie in deinem Programm als Remote-MCP-Server ein. Danach meldest du dich bei Who2Be an, bestätigst den Agenten und schreibst den Test-Satz. Klick zum Schluss auf **Ich habe die Adresse eingetragen**.

Dein Programm muss dafür zwei Dinge können:

- Remote-MCP über HTTP, also nicht nur lokale Server.
- Anmeldung per OAuth, damit du den Zugriff in Who2Be bestätigen kannst.

## Steckbriefe [#steckbriefe]

Wie weit andere Programme Remote-MCP mit OAuth unterstützen, ändert sich gerade schnell. Die Angaben hier sind ohne Gewähr, Stand Oktober 2026. Maßgeblich ist die Dokumentation des Herstellers.

### Gemini [#gemini]

Die Gemini-App nimmt eigene MCP-Server nur in den USA an, ab 18 Jahren, mit privatem Google-Konto und auf Englisch. In der Gemini CLI trägst du den Agenten mit `gemini mcp add` ein, die Anmeldung läuft per OAuth. Gemini Enterprise braucht einen fest eingetragenen OAuth-Client, das richtet der Admin ein.

### Microsoft Copilot [#copilot]

Eigene MCP-Server kommen über Copilot Studio in Copilot. Das richten nur Admins ein.

### Windsurf [#windsurf]

Windsurf kann Remote-MCP mit OAuth. Trag die **Server-URL** von Hand ein, einen Ein-Klick-Link für eigene Adressen gibt es dort nicht.

### Zed [#zed]

Zed kann Remote-MCP mit OAuth. Die Anmeldung gilt nur für den Agenten von Zed selbst, nicht für externe Agenten, die du in Zed startest.

### Mistral Le Chat [#le-chat]

In Le Chat trägst du die **Server-URL** als eigenen MCP-Connector ein. Die Anmeldung läuft per OAuth.

## Mehrere Agenten [#mehrere]

Jeder Agent hat seine eigene Adresse. Willst du zwei Agenten im selben Programm nutzen, verbindest du beide einzeln. Für Claude steht alles auf der Seite [Mit Claude verbinden](/help/connect-claude#troubleshooting).
