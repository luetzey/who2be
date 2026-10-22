---
title: System prompts and placeholders
description: The template an agent reads at every start, and which placeholders you can use in it.
section: bausteine
order: 40
updated: 2026-10-22
audience: all
---

A system prompt is the template your agent reads at every start. It brings together persona, playbooks and resources. You find all templates in the navigation under **System prompts**. Every agent uses exactly one system prompt.

## Structure [#aufbau]

- **Identity:** name and description. Both appear in the template list and when you choose a template for an agent.
- **Content:** the text the agent reads. Type `/` for blocks and placeholders.

Many agents can share the same template. What differs per agent comes from its [persona](/help/persona).

## What a placeholder is [#was-ist-ein-platzhalter]

A placeholder appears in the text as a small pill. When the agent fetches the template, Who2Be replaces it with real content, for example the persona's name or the text of a playbook. That keeps the prompt short and always up to date.

To insert one: type `/` in the editor and pick the placeholder from the menu.

## All placeholders [#placeholders]

- **Playbook:** embeds a playbook permanently. It is loaded at every start.
- **Resource:** links a specific resource.
- **External tool:** binds an external tool via its alias, see [Tools](/help/tools#externe-tools).
- **Persona field:** embeds the name, description, the full profile, only the profile content or only the modes.
- **Load persona (MCP):** embeds no content. It instructs the agent to load its persona at start with `get_persona` and apply its modes.
- **Date:** the current date, as ISO date or human-readable.
- **Playbook catalog:** table of the assigned playbooks with name, trigger, call and description. This tells the agent what it can load when with `fetch_playbook`. Either all of them or only those with triggers.
- **Resource catalog:** table of the workspace resources, optionally filtered by tag.
- **MCP tools:** list of the tools with call and short description. Add the order in which the agent should use them, such as "first `list_triggers`, then `fetch_playbook`".
- **Memory:** a memory hint matching the agent's memory setting.

## Versions and review [#versionen]

Every save creates a new version. An agent only uses the active version. If a version is waiting for review, check the changes and activate it or send it back to draft.

## Tips [#tipps]

- **Load persona (MCP)** keeps the template lean, because the persona only arrives at runtime.
- Only embed playbooks permanently if the agent really always needs them. Otherwise the playbook catalog is enough, see [Playbooks](/help/playbooks#laden).
- Reference knowledge belongs in [resources](/help/resources), not in the prompt.
