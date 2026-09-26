- Die Zahl der Workspaces je Organisation ist in der Cloud jetzt nach Tarif
  begrenzt: Free 1, Pro 5.

  Die Speicher- und Token-Kontingente zaehlen je Workspace; erst zusammen mit
  einem Deckel auf die Zahl der Workspaces ergeben sie eine endliche Zusage —
  bei Pro 5 x 10 GiB = 50 GiB. Bestehende Workspaces bleiben vollstaendig
  nutzbar, auch oberhalb der Grenze; abgewiesen wird ausschliesslich die
  **Anlage** (`402`, `reason: workspace_quota_exceeded`, Grenze in `params`).
  On-Prem und OSS bleiben unbegrenzt.
