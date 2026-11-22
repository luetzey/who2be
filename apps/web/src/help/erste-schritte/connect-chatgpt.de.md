---
title: Mit ChatGPT verbinden
description: Eigenen MCP-Server in ChatGPT eintragen, im Browser.
section: erste-schritte
order: 25
updated: 2026-11-22
audience: all
---

Damit ChatGPT deinen Agenten nutzen kann, trägst du ihn einmal als eigenen MCP-Server in ChatGPT ein. Anders als bei Claude gibt es dafür keinen Knopf, der alles vorausfüllt. Du kopierst Name und Server-URL aus Who2Be und fügst sie in ChatGPT ein. Das dauert etwa drei Minuten.

## Bevor du anfängst [#voraussetzungen]

- Das geht nur auf chatgpt.com im Browser. In der ChatGPT-App am Computer oder am Handy kannst du keinen eigenen Server eintragen.
- Was dein Plan darf, legt OpenAI fest. Je nach Plan kann ChatGPT deinen Agenten nur lesen lassen und keine Schreibwerkzeuge nutzen.
- In ChatGPT Business legen nur Admins eigene Server an. In Enterprise und Edu geht das nur, wenn der Admin es dir erlaubt hat.

ChatGPT zeigt die Menünamen auf Englisch, auch wenn die Oberfläche sonst auf Deutsch ist. Diese Anleitung nennt sie deshalb so, wie du sie auf dem Bildschirm siehst.

## Schritt für Schritt [#schritte]

1. Öffne unter **Agenten** deinen Agenten, zum Beispiel den Builder. Im Tab **Überblick** steht die Karte **Verbindung**. Wähle bei „Wo nutzt du deine Agenten?“ **ChatGPT**.
2. Klick auf **ChatGPT öffnen**. ChatGPT öffnet sich in einem neuen Tab. Geh dort auf **Plugins**, dann auf **+** und auf **Add custom MCP server**.
3. Kopiere aus der Karte **Verbindung** den **Namen** und die **Server-URL** und füg beides in ChatGPT ein. Lass die Anmeldung auf **OAuth**.
4. ChatGPT zeigt einen Hinweis zum Risiko eigener Server. Bestätige ihn und klick auf **Create as a plugin**.
5. ChatGPT leitet dich zu Who2Be weiter. Melde dich an und bestätige, dass ChatGPT diesen Agenten nutzen darf.

Who2Be wartet, sobald du die Server-URL kopiert oder ChatGPT geöffnet hast. Du kannst die Who2Be-Seite dabei offen lassen.

## Der Test-Satz [#test]

Öffne in ChatGPT einen neuen Chat. Tipp **@** und wähl dein Plugin aus, es heißt so wie der Name aus der Karte, zum Beispiel „Who2Be – Builder“. Schreib dann:

```
Wer bist du? Lade deine Persona aus Who2Be.
```

Lädt der Agent seine Persona, zeigt Who2Be die Verbindung als **Verbunden**. Im Tutorial „Erste Schritte“ hakt sich der Schritt von selbst ab.

Lesende Werkzeuge ruft ChatGPT ohne Rückfrage auf. Bevor ein Werkzeug etwas ändert, zum Beispiel einen Entwurf anlegt, fragt ChatGPT nach. Erlaube den Aufruf, sonst passiert nichts.

## Wenn es nicht klappt [#troubleshooting]

- **Kein Menü „Plugins“ oder kein „Add custom MCP server“:** Dein Plan oder deine Rolle im Workspace erlaubt keine eigenen Server. In Business, Enterprise und Edu kann dein Admin das freigeben oder den Server für alle anlegen.
- **Anmeldefehler:** Lösch das Plugin in ChatGPT und leg es neu an. Who2Be fragt dann noch einmal nach deiner Bestätigung.
- **Keine Antwort auf den Test-Satz:** Prüfe, ob du das Plugin im Chat mit **@** gewählt hast und ob du einen Werkzeug-Aufruf abgelehnt hast. Nach zwei Minuten bietet Who2Be dir „Ja, weiter“ an, falls der Agent geantwortet hat.
- **Der Agent kann nur lesen:** Dein Plan erlaubt in ChatGPT keine Schreibwerkzeuge. Das legt OpenAI fest, nicht Who2Be.
- **Der Agent ist nicht bereit:** Statt der Anleitung steht in der Karte, was fehlt, zum Beispiel eine aktive Persona. Behebe das zuerst.

Mit Claude Code, Cursor, VS Code, Hermes Agent und anderen Programmen geht es ähnlich, siehe [Andere Programme verbinden](/help/connect-other-clients).
