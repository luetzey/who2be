- pypdf von 6.21.2 auf 6.21.4 und joserfc von 1.7.2 auf 1.7.7 gehoben
  (pypdf direkt in `apps/api`, joserfc transitiv). Damit sind neun Advisories
  geschlossen: CVE-2026-119203 bis CVE-2026-119209 (pypdf) sowie
  CVE-2026-119283 und CVE-2026-119284 (joserfc). Der CI-Job `audit` ist wieder
  grün.
