- Pull requests must now state their issue reference. The PR template asks for
  it up front with three named cases (`Closes #___`, `Refs #___`,
  `n/a (kein Issue)` with a reason) and `CONTRIBUTING.md` carries the rule with
  the `Closes`-vs-`Refs` distinction: `Closes` lets the merge close the issue,
  `Refs` is the deliberate case for partial work on a tracking/epic issue that
  must stay open (Queue rule 19, #442). Until now nothing asked for the line —
  in wave 3 eleven of twelve PRs carried none, so nine finished issues stayed
  open and had to be closed by hand (Issue #625). No CI check enforces it yet;
  template and CONTRIBUTING come first, and whether they suffice is measured
  before an enforcing check with its Dependabot/docs exception list is built.
