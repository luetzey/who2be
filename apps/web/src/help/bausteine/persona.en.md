---
title: Persona
description: Who your agent is, how it sounds and where its limits are.
section: bausteine
order: 10
updated: 2026-10-23
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

## How long can a persona be? [#laenge]

The agent loads the whole persona in every chat. The longer it is, the more room it takes and the less reliably the agent follows any single rule. That is why there are guide values:

- **Profile:** guide value 400 words, note from 600.
- **One mode** (all three fields together): guide value 150 words, note from 250.
- **Number of modes:** guide value 3, note from 5.
- **Playbook content:** guide value 1,000 words, note from 1,500.

Below the editor you see where you stand, for example "412 words · guide value 400". From the note threshold on it says "over the guide value" with a suggestion. This is not a limit: Who2Be saves anyway. Code blocks don't count, an inserted reference counts as one word.

If it gets too long, one of these usually helps:

- **Procedures** ("first …, then …") belong in a [playbook](/help/playbooks). The profile keeps a reference to it.
- **Reference knowledge** such as tables, lists and templates belongs in a [resource](/help/resources).
- **Modes** that barely differ can be merged.

## Versions and activation [#versionen]

Every change to a persona creates a new version. A draft has no effect yet. Only once a version is active does the agent load it. Only admins can activate.

An agent can only be switched on when its persona is active. If not, the agent page shows "Not yet activatable".

## Tips [#tipps]

- Write the profile the way you would explain the role to a new colleague.
- Don't put procedures into the profile, put them into [playbooks](/help/playbooks). That keeps the persona short.
- Reference knowledge belongs in [resources](/help/resources).
