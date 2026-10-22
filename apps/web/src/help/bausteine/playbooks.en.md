---
title: Playbooks
description: Repeatable procedures your agent loads when it needs them.
section: bausteine
order: 20
updated: 2026-10-22
audience: all
---

A playbook describes how your agent handles a specific task. From a short text snippet to a multi-step procedure with branches. You find all playbooks in the navigation under **Playbooks**.

## Structure [#aufbau]

- **Identity:** name, type and a short description.
- **Content:** the playbook itself, for example "Step 1: greet the customer. Step 2: verify identity. Step 3: send the link." With `/` you insert references to other playbooks, resources and external tools.
- **Trigger:** keywords at which the agent should load this playbook.
- **Tags:** for search and filters.

## Types [#typen]

The type helps you organise and helps the agent classify:

- **Workflow:** multi-step procedure with branches.
- **Checklist:** list to check before a step.
- **FAQ:** collection of questions and answers.
- **Snippet:** short, reusable piece of text.

There are also single prompts and multi-part instructions.

## How the agent uses playbooks [#laden]

The agent doesn't load all playbooks at once. It sees a catalog with names, triggers and descriptions and fetches the matching playbook when a trigger comes up. That keeps its context small.

A playbook can also be tied to a [persona](/help/persona), for example to a mode. Then it belongs to that role.

## Composite playbooks [#composite]

A playbook can contain other playbooks. Who2Be calls this a **composite**. The agent works through the sub-playbooks in order. That way you maintain a building block once and use it in several procedures.

## Versions [#versionen]

Every change creates a new version, old versions are kept. The agent only loads an active version. Knowledge a playbook refers to is best kept in a [resource](/help/resources).
