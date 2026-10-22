---
title: Resources
description: Knowledge in blocks that your agent looks up when needed.
section: bausteine
order: 30
updated: 2026-10-22
audience: all
---

A resource is a knowledge document: an FAQ, a price list, a policy. The agent doesn't carry it around all the time, it fetches the part it needs right now. You find all resources in the navigation under **Resources**.

## Structure [#aufbau]

- **Identity:** name and a short description of what it is about.
- **Content:** the text itself in the block editor.
- **Tags:** for search and filters. The agent can also list resources by tag.

## Blocks [#bloecke]

Every heading in a resource forms a block. An agent can load a single block instead of the whole document. That saves room in its context and keeps the answer precise.

So structure a resource with clear headings, for example one per question or topic.

## Using resources [#einbinden]

- **In a playbook:** link a block of the resource in the playbook. The agent then loads exactly that section when it runs the [playbook](/help/playbooks).
- **In the persona:** with `/` you insert a resource or the resource catalog into the profile of the [persona](/help/persona).
- **As a sub-resource:** a resource can point to further resources that the agent loads when needed.

On a resource's page, "Linked in" shows where it is already used.

## Versions [#versionen]

Every change creates a new version. When you are done, you submit it for review. After the review it is activated, and only then does the agent read the new version.

## Tips [#tipps]

- One topic per resource. Three short ones beat one long one.
- Write facts, not instructions. How the agent should do something belongs in the playbook.
- Keep data like prices or deadlines up to date. Agents report outdated parts as feedback.
