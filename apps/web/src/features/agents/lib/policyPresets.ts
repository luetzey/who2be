/**
 * Policy-Presets fuer den Agent-Policy-Editor (Issue #394).
 *
 * Reine UI-Ableitung ueber die bestehenden Write-Capability-Checkboxen aus
 * `AgentToolPolicy` (`packages/models/src/who2be_models/tool_policy.py`) —
 * KEIN neues Persistenz-Feld, KEIN Backend-Aufruf. Der Preset ist abgeleiteter
 * Zustand: er wird bei jedem Render aus den aktuellen Formularwerten neu
 * berechnet (`derivePolicyPreset`), nie separat gespeichert.
 *
 * Zuordnung Preset -> Capability-Menge (alle Felder aus `WRITE_CAP_FIELDS`,
 * das 1:1 die Checkboxen der „Schreiben"-Sektion in `AgentEditorForm` sind):
 *
 * - `readOnly` ("Nur lesen"): ALLE Write-/Transition-Capabilities aus,
 *   inkl. `promote_retire`. Reine Leserechte (playbook_read etc.) bleiben von
 *   Presets unberuehrt.
 * - `editorNoApproval` ("Editor ohne Freigabe"): alle Write-Capabilities AUSSER
 *   `promote_retire` an; `promote_retire` explizit AUS — der Agent darf Inhalte
 *   anlegen/aendern und zur Review einreichen (draft->review, siehe
 *   `_require_transition_capability` in `version_status.py`), aber keine
 *   Version aktivieren/deaktivieren (review/inactive->active/inactive bleibt
 *   gesperrt, Zwei-Gate-Modell).
 * - `editorWithApproval` ("Editor mit Freigabe"): alle Write-Capabilities an,
 *   inkl. `promote_retire` — darf zusaetzlich selbst aktivieren/zurueckziehen.
 *
 * Passt die aktuelle Checkbox-Kombination zu keinem der drei Muster, ist der
 * abgeleitete Zustand `custom` ("Benutzerdefiniert") — bewusst kein viertes,
 * waehlbares Preset, sondern nur eine Anzeige (kleinstes konsistentes Muster).
 */

export const WRITE_CAP_FIELDS = [
  'persona_write',
  'playbook_write',
  'resource_write',
  'agent_write',
  'system_prompt_write',
  'external_tool_write',
  'feedback_write',
  'feedback_resolve',
  'promote_retire',
  'workarea_write',
  'kb_write',
  'kb_edge_write',
] as const

export type WriteCapField = (typeof WRITE_CAP_FIELDS)[number]

/** Aktuelle An/Aus-Werte aller Write-Capability-Checkboxen. */
export type WriteCapValues = Record<WriteCapField, boolean>

export type PolicyPreset = 'readOnly' | 'editorNoApproval' | 'editorWithApproval'

/** Waehlbare Presets (Anzeigereihenfolge = Radio-Reihenfolge im Formular). */
export const POLICY_PRESETS: readonly PolicyPreset[] = [
  'readOnly',
  'editorNoApproval',
  'editorWithApproval',
]

/** Abgeleiteter Anzeigezustand: ein Preset oder „Benutzerdefiniert". */
export type DerivedPolicyPreset = PolicyPreset | 'custom'

const NON_APPROVAL_FIELDS = WRITE_CAP_FIELDS.filter((field) => field !== 'promote_retire')

/** Ermittelt das aktuell passende Preset aus den Checkbox-Werten (oder `custom`). */
export function derivePolicyPreset(values: WriteCapValues): DerivedPolicyPreset {
  const allOff = WRITE_CAP_FIELDS.every((field) => !values[field])
  if (allOff) {
    return 'readOnly'
  }
  const allWritesOn = NON_APPROVAL_FIELDS.every((field) => values[field])
  if (allWritesOn && !values.promote_retire) {
    return 'editorNoApproval'
  }
  if (allWritesOn && values.promote_retire) {
    return 'editorWithApproval'
  }
  return 'custom'
}

/** Liefert die Checkbox-Werte, die ein Preset-Klick setzen soll. */
export function applyPolicyPreset(preset: PolicyPreset): WriteCapValues {
  const off = Object.fromEntries(WRITE_CAP_FIELDS.map((field) => [field, false])) as WriteCapValues
  if (preset === 'readOnly') {
    return off
  }
  const on = Object.fromEntries(WRITE_CAP_FIELDS.map((field) => [field, true])) as WriteCapValues
  if (preset === 'editorWithApproval') {
    return on
  }
  // editorNoApproval: alle Writes an, promote_retire explizit aus.
  return { ...on, promote_retire: false }
}
