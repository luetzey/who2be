---
title: Connect other programs
description: Connect Claude Code, Cursor, VS Code and other programs to your agent.
section: erste-schritte
order: 30
updated: 2026-10-22
audience: all
---

Who2Be agents don't only work in Claude. Every program that supports remote MCP with sign-in (OAuth) picks up your agent the same way. You find the right way on your agent's page in the **Overview** tab, **Connection** card, under "Where do you use your agents?".

## Claude Code [#claude-code]

1. Choose **Claude Code** and click **Copy command**.
2. Run the command in your terminal. It looks like this:

```
claude mcp add --transport http who2be-builder https://…
```

3. On first use you sign in to Who2Be and confirm the agent.
4. Send the test sentence from the card, for example "Who are you? Load your persona from Who2Be."

The address in the command belongs to exactly this one agent. So always copy it from the card instead of typing it.

## Cursor and VS Code [#cursor-vscode]

1. Choose **Cursor or VS Code**.
2. Click **Add to Cursor** or **Install in VS Code**. The editor opens and asks once.
3. On first use you sign in to Who2Be and confirm the agent.

If the button doesn't work, open "Button not working? Add it manually". Add the **Server URL** in your editor as a remote MCP server with HTTP transport.

## Something else [#andere]

Choose **Something else**. Who2Be shows you the **Server URL** to copy. Add it in your program as a remote MCP server. Then sign in to Who2Be, confirm the agent and send the test sentence. Finally click **I've entered the address**.

Your program needs to support two things:

- Remote MCP over HTTP, not only local servers.
- Sign-in via OAuth, so you can confirm access in Who2Be.

## Several agents [#mehrere]

Every agent has its own address. If you want to use two agents in the same program, connect each of them. Everything about Claude is on the page [Connect to Claude](/help/connect-claude#troubleshooting).
