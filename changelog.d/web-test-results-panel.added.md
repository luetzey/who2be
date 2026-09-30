- Version review shows test case results next to the diff (learning loop B5,
  design spec S11, part A).

  When a version's diff is opened in the "Versions" tab, the latest result of
  every applicable test case for exactly that version appears beside it (two
  columns from `lg`, stacked below with test cases first). Results are grouped
  by agent with the path through which the agent is affected, the number of
  affected agents is shown first, and each row carries icon plus word
  (failed, no result, awaiting judgment, passed) with its `k/n` run count —
  only n/n counts as passed. Every result says where it came from
  ("self-report by the client" or "rated by <user>"). Test cases rated by a
  person can be judged right there; the rating is stored as a new result.
  Without results the panel shows a prompt to start the run in the client.
  The detail pages switch the panel on in a follow-up change; activating with
  a warning follows as part B.
