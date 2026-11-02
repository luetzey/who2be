// ERZEUGT aus packages/models/src/who2be_models/content_budgets.py (ADR-0063).
// Nicht von Hand aendern. Neu erzeugen im Repo-Root mit:
//   uv run python -m who2be_models.content_budgets
// test_content_budgets.py haelt diese Datei gleich mit den Python-Werten.

export interface ContentBudget {
  /** Richtwert (Ziel); `null`: nur Warnschwelle. */
  target: number | null
  /** Warnschwelle. */
  warn: number
  unit: 'words' | 'chars' | 'count'
  /** `true`: gewarnt wird erst ueber `warn`, sonst ab `warn`. */
  strict: boolean
}

export const CONTENT_BUDGETS = {
  profile: { target: 400, warn: 600, unit: 'words', strict: false },
  mode: { target: 150, warn: 250, unit: 'words', strict: false },
  mode_count: { target: 3, warn: 5, unit: 'count', strict: false },
  playbook_body: { target: 1000, warn: 1500, unit: 'words', strict: false },
  playbook_summary: { target: 300, warn: 500, unit: 'chars', strict: false },
  resource_section: { target: null, warn: 600, unit: 'words', strict: true },
} as const satisfies Record<string, ContentBudget>

export type ContentBudgetElement = keyof typeof CONTENT_BUDGETS
