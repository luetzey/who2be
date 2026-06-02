# `K_pub`-Slot — oeffentlicher On-Prem-Lizenz-Signing-Key

Hier liegt **ausschliesslich** der oeffentliche Ed25519-Verifikationsschluessel
(`K_pub`) fuer die Offline-Pruefung von On-Prem-Lizenzdateien
(`licensing/crypto.py`).

- Dateiname: `signing_key.pub` (PEM, `-----BEGIN PUBLIC KEY-----`).
- Heute nur der `.gitkeep`-Platzhalter — der echte `K_pub` wird im Deployment
  hinterlegt (Plan §3.5: "K_pub … heute .gitkeep").

**Guardrail (verbindlich, Plan §3.6):** Der **private** Signing-Key gehoert
**niemals** ins Repo. Mit `K_pub` laesst sich nur verifizieren, nicht signieren.
Lizenzen werden offline ausgestellt und mit `WHO2BE_LICENSE_KEY` eingespielt —
**kein Phone-Home**.
