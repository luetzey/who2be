- Versionen verklemmen nicht mehr, wenn neben einer offenen Review-Version
  ein neuer Draft entsteht (z. B. per PUT während der Review). Vorher scheiterte
  das Einreichen des Drafts (409, Review belegt) ebenso wie das Zurückschicken
  der Review (409, Draft belegt). Jetzt ersetzt das Einreichen (`→ review`) eine
  andere offene Review derselben Entity: sie wird `inactive`, die Herkunft
  vermerkt „Review ersetzt durch Einreichen von vN“, und über `inactive → draft`
  bleibt sie wiederherstellbar. Gilt für Playbooks, Personas, Resources,
  System-Prompts und externe Tools und löst auch bereits verklemmte Bestände.
