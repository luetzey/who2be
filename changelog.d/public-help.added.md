- Help without sign-in: `/help` and `/help/<page>` are now readable without a
  session, for every page meant for everyone (`audience: all`). A help link
  from the connect screen ("What happens here?"), the website or an invitation
  opens the page directly, including the section it points to. The public view
  has a header with "Sign in" (returning to the same section afterwards) and
  shows only the reference pages; admin pages, tutorials, progress and "What's
  new" stay behind the sign-in and are not listed or searchable without it.
  Signed in, `/help/…` still opens the help inside the workspace.

  The sign-in redirect now keeps the anchor of the target page in `next`
  (`/help/connect-claude#schritte` no longer lands at the top of the page).
