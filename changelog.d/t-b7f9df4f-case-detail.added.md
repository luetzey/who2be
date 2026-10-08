- Web: case detail page at `/w/:workspace/feedback/cases/:caseId` (ADR-0053
  D6c, read-only). It shows the header "Case · {agent}" with status (dot and
  word) and the report date, the four reported blocks (empty ones hidden, 2×2
  from `md`), a note that the content stays as reported, the agent's account,
  the assignment (editor and above, read-only) and the history, newest first.
  Unknown history events fall back to "Change". Viewers see their own cases
  without the assignment; anyone else's case shows the not-found view. "Cases"
  leads back to the case list with the filters it was opened from.
- Web: "Delete case…" in the case overflow menu for editor and above, with a
  destructive confirmation. It removes the case with its history, assignment
  and the agent's account (`DELETE /cases/{id}`); a content-free log entry
  remains. Viewers do not see the action.
- Web: the case list waits for the workspace role before loading, and a viewer
  whose cases are all closed now gets a sentence of their own instead of the
  editor text.
