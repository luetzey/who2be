- authlib von 1.7.2 auf 1.9.1 und dnspython von 2.8.0 auf 2.9.0 gehoben
  (beide transitiv über fastmcp).

  Damit sind acht Advisories geschlossen: CVE-2026-96760, CVE-2026-114614,
  CVE-2026-114615, CVE-2026-114616, CVE-2026-114617, CVE-2026-114618,
  CVE-2026-114620 (authlib) und CVE-2026-114605 (dnspython). Der CI-Job
  `audit` ist wieder grün.
