---
title: Persona
description: Who your agent is, how it sounds and where its limits are.
section: bausteine
order: 10
updated: 2026-10-22
audience: all
---

The persona tells the agent who it is. It is the first thing the agent loads from Who2Be in a new chat. You find all personas in the navigation under **Personas**.

## What goes into a persona [#felder]

- **Identity:** name and a short description of what the persona is responsible for. Both appear in lists and pickers.
- **Profile:** role, tone, examples and exceptions. The agent derives from it how to answer. Concrete examples work better than long bullet lists.
- **Modes (optional):** variants for different situations, see below.
- **Tags:** keywords for search and grouping.

In the profile you insert references with `/`, for example a single playbook, a resource or the playbook catalog. On every fetch Who2Be replaces them with the current version.

## Modes [#modi]

A mode is a situational variant of the persona, such as "coaching" and "analysis". Every mode has:

- **Trigger:** keywords that switch the mode on. A mode without a trigger is the default mode. There is at most one.
- **Identity addition**, **Output style** and **Anti-patterns:** what is different in this mode.
- **Playbook (optional):** a procedure that belongs to this mode.

If no trigger matches, the agent works in the default mode.

## Versions and activation [#versionen]

Every change to a persona creates a new version. A draft has no effect yet. Only once a version is active does the agent load it. Only admins can activate.

An agent can only be switched on when its persona is active. If not, the agent page shows "Not yet activatable".

## Tips [#tipps]

- Write the profile the way you would explain the role to a new colleague.
- Don't put procedures into the profile, put them into [playbooks](/help/playbooks). That keeps the persona short.
- Reference knowledge belongs in [resources](/help/resources).
