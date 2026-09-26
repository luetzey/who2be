- Die System-Prompt-Domäne läuft auf 320px nicht mehr über: lange Slugs brechen in Liste und Detail mitten im Wort, die Label-Zeile über dem Prompt-Editor darf umbrechen, und lange Platzhalternamen in der Hilfe kürzen kontrolliert statt das Icon zu zerdrücken.

  Gemessen am gerenderten Baum: der Slug-Badge maß bei 320px 497px und trieb `body.scrollWidth` auf 590 (Liste) bzw. 577 (Detail); beides liegt jetzt bei 320. Der Cap des Platzhalter-Popovers bleibt wie in W2 entschieden im Primitive — er greift nachweislich (304px bei `left 8` / `right 312`).
