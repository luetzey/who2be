---
title: Memory
description: What your agents remember and how you decide about it.
section: agenten-verbessern
order: 20
updated: 2026-10-22
audience: all
---

Agents can remember things across conversations: how their environment works, what you prefer, what they have learned. None of it takes effect behind your back. You see every entry and decide what counts. You find everything in the navigation under **Memory** and per agent in the **Memory** tab.

## Kinds of entries [#arten]

- **Agent note:** what an agent remembers about its environment and tools. It only applies to this agent.
- **User fact:** facts about you, such as "prefers short answers". All your agents share your user memory.
- **Learning suggestion:** an insight the agent suggests. Learning suggestions never flow into a prompt. They are counted and can turn into a new version via a [case](/help/feedback-and-cases), a test case and your approval.

## Memory mode [#modus]

On the agent, under **Settings**, you decide whether and how it stores memories:

- **Off:** the agent remembers nothing.
- **Read only:** it uses approved entries but doesn't suggest new ones.
- **With approval:** new entries land as suggestions awaiting approval. The agent can only fetch them after your approval.
- **Automatic (workspace rules):** only what is switched on under **Settings › Workspace › Memory** is released without review. Everything else awaits approval.

## Approve and reject [#freigabe]

**Memory › Awaiting approval** lists all suggestions. For each entry you can **Approve** or **Reject**. Rejected entries stay stored so that the agent doesn't suggest them again.

Who2Be holds back some suggestions so you check them one by one:

- **From a website, file or tool:** entries from outside content never take effect automatically.
- **Classified as an instruction:** the entry tells the agent how to work. That acts like a rule.
- **Inferred by the agent:** you didn't say it yourself, the agent derived it.

## Change and delete [#aendern]

If an entry is outdated, the agent suggests a change or deletion instead of adding a second, contradicting entry. You apply that only after review as well. Under **Entries** you search and filter all entries by agent, kind and status.

## What never belongs in memory [#grenzen]

Passwords, credentials and information about other people don't belong in memory. Who2Be also checks every suggestion with a filter against injected instructions.
