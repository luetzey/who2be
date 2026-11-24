---
title: Connect to ChatGPT
description: Add your own MCP server in ChatGPT, in the browser.
section: erste-schritte
order: 25
updated: 2026-11-22
audience: all
---

For ChatGPT to use your agent, you add it once as a custom MCP server in ChatGPT. Unlike Claude, there is no button that fills everything in. You copy the name and server URL from Who2Be and paste them into ChatGPT. It takes about three minutes.

## Before you start [#voraussetzungen]

- This only works on chatgpt.com in the browser. You can't add a custom server in the ChatGPT app on your computer or phone.
- OpenAI decides what your plan allows. Depending on the plan, ChatGPT may only let your agent read and not use write tools.
- In ChatGPT Business, only admins add custom servers. In Enterprise and Edu, you can only do it if your admin has allowed it.

## Step by step [#schritte]

1. Under **Agents**, open your agent, for example the Builder. The **Overview** tab has the **Connection** card. Under “Where do you use your agents?”, choose **ChatGPT**.
2. Click **Open ChatGPT**. ChatGPT opens in a new tab. Go to **Plugins**, then **+** and **Add custom MCP server**.
3. Copy the **Name** and **Server URL** from the **Connection** card and paste both into ChatGPT. Leave sign-in on **OAuth**.
4. ChatGPT shows a notice about the risk of custom servers. Accept it and click **Create as a plugin**.
5. ChatGPT sends you to Who2Be. Sign in and confirm that ChatGPT may use this agent.

Who2Be starts waiting as soon as you copy the server URL or open ChatGPT. You can leave the Who2Be page open.

## The test sentence [#test]

Open a new chat in ChatGPT. Type **@** and pick your plugin. It has the name from the card, for example “Who2Be – Builder”. Then write:

```
Who are you? Load your persona from Who2Be.
```

Once the agent loads its persona, Who2Be shows the connection as **Connected**. In the “Getting started” tutorial, the step checks itself off.

ChatGPT calls reading tools without asking. Before a tool changes anything, for example creates a draft, ChatGPT asks. Allow the call, otherwise nothing happens.

## If it doesn't work [#troubleshooting]

- **No “Plugins” menu or no “Add custom MCP server”:** Your plan or your role in the workspace doesn't allow custom servers. In Business, Enterprise and Edu, your admin can allow it or add the server for everyone.
- **Sign-in error:** Delete the plugin in ChatGPT and add it again. Who2Be will then ask for your confirmation once more.
- **No answer to the test sentence:** Check that you picked the plugin with **@** in the chat and didn't decline a tool call. After two minutes, Who2Be offers “Yes, continue” in case the agent answered.
- **The agent can only read:** Your plan doesn't allow write tools in ChatGPT. OpenAI decides this, not Who2Be.
- **The agent isn't ready:** Instead of the guide, the card shows what's missing, for example an active persona. Fix that first.

Claude Code, Cursor, VS Code, Hermes Agent and other programs work in a similar way, see [Connect other programs](/help/connect-other-clients).
