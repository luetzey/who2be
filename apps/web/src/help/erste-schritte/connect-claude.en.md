---
title: Connect to Claude
description: One click, one confirmation, one test sentence.
section: erste-schritte
order: 20
updated: 2026-10-23
audience: all
---

For Claude to use your agent, you add it to Claude once as a connector. Who2Be fills in everything for you. It takes about two minutes.

The connector belongs to your Claude account. You add it once, and then it works in claude.ai, in the Claude app on your computer and on your phone, and in Claude Code.

## Step by step [#schritte]

1. Under **Agents**, open your agent, for example the Builder. The **Overview** tab shows the **Connection** card.
2. Under "Where do you use your agents?" choose **Claude (web, app, mobile)** and click **Connect to Claude**. Claude opens in a new tab with the name and address already filled in.
3. In Claude, click **Add** and then **Connect**.
4. Who2Be asks whether Claude may use this agent. Confirm.
5. In Claude, start a new chat, send the test sentence and allow the tool call when Claude asks.

## The test sentence [#test]

```
Who are you? Load your persona from Who2Be.
```

Once the agent loads its persona, Who2Be shows the connection as **Connected**. In the tutorial "Getting started" the step is checked off by itself. You can leave the Who2Be page open meanwhile.

## Add it manually [#von-hand]

If the button doesn't work, open "Button not working? Add it manually" in the **Connection** card. It shows the **Name** and the **Server URL** to copy.

In Claude, go to **Customize › Connectors**, click **+ Add** and then **Add custom connector**. Paste both there. On the iPhone the button sometimes doesn't open the dialog. Then use this way.

## Team and Enterprise plans [#team-plan]

On Claude plans for teams and companies, the owner of the Claude organization adds the connector under **Organization settings › Connectors**. Send them the name and server URL from the **Connection** card. After that, each member connects on their own in Claude under **Customize › Connectors**.

## If it doesn't work [#troubleshooting]

- **No check mark after the test sentence:** Make sure you sent the sentence in a new chat and allowed the tool call. After two minutes Who2Be offers "Yes, continue" in case the agent did answer.
- **Claude shows a sign-in error:** Remove the connector in Claude and connect again. Who2Be asks for your confirmation once more.
- **The agent isn't ready:** Instead of the button you see what is missing, for example an active persona. Fix that first.
- **Claude Free:** Only one custom connector is allowed there. If one is already added, remove it first.

Claude Code, Cursor, VS Code and Hermes Agent work in a similar way, see [Connect other programs](/help/connect-other-clients).
