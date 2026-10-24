---
title: Build your own agent
description: Let the Builder build an agent for you in chat, or create one yourself.
section: erste-schritte
order: 40
updated: 2026-10-23
audience: all
---

The easiest way to get your own agent is a conversation with the Builder. You say what it is for, the Builder asks follow-up questions and creates everything in Who2Be. Prerequisite: the Builder is already connected, see [Connect to Claude](/help/connect-claude).

## With the Builder in chat [#mit-dem-builder]

1. In Claude, start a new chat with the Builder.
2. Describe in one or two sentences what your agent should do. For example:

```
Build me an agent in Who2Be for customer requests by email. Ask me first what you need to know.
```

3. Answer the follow-up questions. The more specific you are, the better the agent fits.
4. The Builder creates the persona, playbooks and the agent in Who2Be. Allow the tool calls when Claude asks.

You'll then find the new agent under **Agents**.

## Create it yourself [#formular]

You can also create an agent without the Builder:

1. Under **Agents**, click **Create new agent**. Who2Be opens **Settings › Configuration** right away, with the cursor in the **Persona** field.
2. Give it a name and choose a **Persona** and a **System prompt**. Then click **Save**.
3. The persona must be active. As long as something is missing, Who2Be shows "Not yet activatable" and names what is missing.
4. Once everything is set, Who2Be asks "Activate the agent now?". With **Activate** it can be fetched right away, and you land in the overview at the **Connection** card. With **Later** it stays deactivated; you can change the status under **Settings**.

## Connect the new agent [#verbinden]

Every agent has its own connection. Open the new agent, go to the **Connection** card and connect it like the Builder. Then send the test sentence:

```
Who are you? Load your persona from Who2Be.
```

Once the new agent loads its persona, the step "Build your own agent" in the tutorial [Getting started](/help/tutorials/getting-started#build-own-agent) is done.

If you use Claude Free, only one custom connector is allowed there. Remove the Builder in Claude first.

## Building good agents [#tipps]

- **One purpose per agent.** Two small agents are better than one for everything.
- **Give examples.** Tell the Builder what a good answer looks like.
- **Start small.** Add playbooks only once a task comes up more often.
