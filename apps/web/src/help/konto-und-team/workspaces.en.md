---
title: Workspaces, members and roles
description: How Who2Be separates content, whom you invite and who may do what.
section: konto-und-team
order: 10
updated: 2026-10-24
audience: all
---

Everything in Who2Be lives in a workspace: agents, personas, playbooks, resources and cases. A workspace belongs to an organization. That way you keep customer support and marketing cleanly apart, for example.

## Organization and workspace [#aufbau]

- **Organization:** the frame, such as your company. With your account you get a personal organization with a first workspace.
- **Workspace:** a self-contained area with its own content and its own members.

You switch workspaces at the top of the navigation with **Switch workspace**. You create a new one there with **Create workspace** or under **Settings › Organization**.

## Roles [#rollen]

Every member has exactly one role in a workspace:

- **Viewer:** sees everything, changes nothing. Viewers can report cases and follow the status of their own cases.
- **Editor:** creates content, edits it and submits it for review.
- **Admin:** activates versions and manages members and invitations.

That is a four-eyes principle: an editor writes, an admin activates. So an editor or admin creates your own agents. As a viewer, ask an admin to do it.

## Invite members [#einladen]

1. Open **Settings › Members**. The page is for admins only.
2. Under **Invite new member**, enter the email address and choose the **Role**.
3. Click **Invite**. The person receives a one-time link to join.

Open invitations expire automatically and can be revoked. In a team workspace, invited people see the checklist [Getting started](/help/tutorials/getting-started). The welcome only appears in their own personal workspace.

## Let colleagues use agents only [#nur-nutzen]

If a colleague should use your agents without changing them, invite them with the role **Viewer** (see [Invite members](#einladen)).

What the colleague can do:

- Connect an agent to Claude or another client through a connector (see [Connect to Claude](/help/connect-claude)) and use it there. The agent loads its persona, playbooks and resources and searches them.
- Read everything in the workspace, including drafts.
- Report cases and follow their status.

What they cannot do:

- Create, change or delete agents, personas, playbooks or resources.
- Activate versions.
- Create API tokens or manage members.

While talking to the colleague, the agent may use its [memory](/help/memory) and propose new entries or changes. Proposals for the agent memory go to [approval](/help/memory#freigabe) and only take effect once an editor or admin approves them. Only in the memory mode **Automatic (workspace rules)** does whatever an admin switched on there apply right away. In the web app the colleague only sees their own user memory, not the agent memory.

The colleague has to be a member of the same workspace. Sharing agents across organizations is not possible yet. If your colleague works in another organization, invite them as described above into a workspace of your organization. You then work in the shared organization.

## Change a role or remove [#aendern]

In the member list you change the role or remove a member. When you do, Who2Be revokes that member's API tokens automatically. New tokens get the new role.
