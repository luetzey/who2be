---
title: Connect other programs
description: Connect Claude Code, Cursor, VS Code, Hermes Agent and other programs to your agent.
section: erste-schritte
order: 30
updated: 2026-10-23
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

## Hermes Agent [#hermes]

1. Choose **Hermes Agent** and click **Copy command**.
2. Run the command in the terminal of the machine Hermes runs on. It looks like this:

```
hermes mcp add who2be-builder --url https://… --auth oauth
```

3. Hermes opens sign-in in the browser or prints a link for it. Sign in to Who2Be and confirm the agent. If Hermes runs on a server without a browser, open the link on your computer and paste the address the browser ends up on into the terminal.
4. Type `/reload-mcp` or start a new session. Then send the test sentence from the card.

If you use several Hermes profiles, pick the profile with `-p`, for example `hermes -p work mcp add …`. The address in the command belongs to exactly one agent. So always copy it from the card. More about MCP in Hermes is in the [Hermes documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp).

## Something else [#andere]

Choose **Something else**. Who2Be shows you the **Server URL** to copy. Add it in your program as a remote MCP server. Then sign in to Who2Be, confirm the agent and send the test sentence. Finally click **I've entered the address**.

Your program needs to support two things:

- Remote MCP over HTTP, not only local servers.
- Sign-in via OAuth, so you can confirm access in Who2Be.

## Profiles [#steckbriefe]

How far other programs support remote MCP with OAuth is changing quickly. The details here come without guarantee, as of October 2026. The vendor's documentation is what counts.

### Gemini [#gemini]

The Gemini app only accepts custom MCP servers in the US, from age 18, with a personal Google account and in English. In the Gemini CLI you add the agent with `gemini mcp add`, sign-in runs via OAuth. Gemini Enterprise needs a fixed OAuth client, which the admin sets up.

### Microsoft Copilot [#copilot]

Custom MCP servers reach Copilot through Copilot Studio. Only admins can set that up.

### Windsurf [#windsurf]

Windsurf supports remote MCP with OAuth. Enter the **Server URL** manually, there is no one-click link for custom addresses.

### Zed [#zed]

Zed supports remote MCP with OAuth. The sign-in only applies to Zed's own agent, not to external agents you start inside Zed.

### Mistral Le Chat [#le-chat]

In Le Chat you add the **Server URL** as a custom MCP connector. Sign-in runs via OAuth.

## Several agents [#mehrere]

Every agent has its own address. If you want to use two agents in the same program, connect each of them. Everything about Claude is on the page [Connect to Claude](/help/connect-claude#troubleshooting).
