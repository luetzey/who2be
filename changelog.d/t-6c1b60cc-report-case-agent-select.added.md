- "Report a case" can now be opened without a fixed agent (learning loop
  D6b0, preparation for the feedback hub in D6b).

  Without a preset agent the dialog loads the agents the user may read
  (`GET /agents`, from viewer) and shows a required "Agent" select in front of
  the four questions. Submitting without a choice shows "Please choose an
  agent." and moves focus to the select. A workspace without agents shows
  "No agent in this workspace yet. A case always belongs to an agent." with a
  link to Agents instead of the form. The trigger gets a `variant` (default
  `outline`), so the agent detail page is unchanged. A new test pins the
  "What did the agent do?" limit at 4 000 characters.
