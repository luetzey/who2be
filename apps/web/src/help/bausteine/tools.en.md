---
title: Tools
description: What your agent may do in Who2Be and how to add tools from other services.
section: bausteine
order: 50
updated: 2026-10-22
audience: all
---

Your agent talks to Who2Be through tools (MCP tools). With them it loads its persona, looks up playbooks and reports feedback. This page explains which tools exist, how you allow them and how you add tools from other services.

## What an agent can do with them [#faehigkeiten]

- **Read:** load its persona, see the playbook catalog, fetch a playbook or a block of a resource, search the content.
- **Report:** say which playbook it used and whether it helped, and report situations as feedback.
- **Remember:** suggest entries for its memory. Depending on the agent's settings, they only take effect after your approval.
- **Write (only if allowed):** create and change personas, playbooks or resources. The Builder uses this to build agents for you.

Typical names are `get_persona`, `list_triggers`, `fetch_playbook` and `fetch_resource`. You insert the full list into a system prompt with `/` as "MCP tools".

## Setting permissions [#rechte]

On your agent's page under **Settings › Tools & permissions** you decide what it may do:

- By default an agent only reads what is assigned to it and may change nothing.
- A preset sets the write permissions in one step: **Read only**, **Editor without approval** or **Editor with approval**.
- You can still change single checkboxes afterwards.

The server rejects blocked tools. The agent's prompt only lists the tools it may use.

## External tools [#externe-tools]

Under **External tools** you store tools from other services, for example a to-do list. Every external tool gets a fixed **alias** such as `todo`. Playbooks and personas refer to the alias, not to the service.

If you switch services later, you only change the external tool. All references stay valid. For every tool you can add usage notes and a fallback note in case the service isn't connected.

You set the reference with `/` in the [playbook](/help/playbooks) or in the [persona](/help/persona).
