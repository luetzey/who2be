- Der Längenzähler unter dem Editor zeigt bei Persona-Profil, Modus und
  Playbook-Inhalt jetzt auch Wörter und Richtwert (ADR-0063, Builder
  schlank B5), etwa „412 Wörter · Richtwert 400“. Ab der Warnschwelle steht
  dort „über dem Richtwert 400, Abläufe besser in ein Playbook“, zusätzlich
  in Kontrastfarbe. Unter der Modus-Liste steht die Zahl der Modi mit ihrem
  Richtwert. Gespeichert wird immer. Die Werte kommen aus
  `who2be_models.content_budgets` über die erzeugte Datei
  `apps/web/src/components/editor/contentBudgets.generated.ts`, gezählt wird
  wie in der Schreibantwort der API. Neuer Hilfe-Abschnitt „Wie lang darf
  eine Persona sein?“ (DE/EN), verlinkt aus der Fußzeile.
