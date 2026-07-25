import { useEffect, useRef, useState } from 'react'

import { useWorkspaceContentLocale } from './useWorkspaceContentLocale'

export interface ContentLocaleField {
  locale: string
  setLocale: (next: string) => void
}

/**
 * Sprachfeld-State fuer Create-Formulare (Persona/Playbook/Resource/Tool/
 * System-Prompt, ADR-0045 „Ein Element, eine Sprache"): startet auf der
 * Workspace-Content-Sprache (`useWorkspaceContentLocale`, kommt asynchron
 * nach) und respektiert danach jede manuelle Auswahl — der nachgeladene
 * Workspace-Default ueberschreibt eine bereits getroffene User-Wahl nicht
 * mehr.
 */
export function useContentLocaleField(): ContentLocaleField {
  const workspaceLocale = useWorkspaceContentLocale()
  const [locale, setLocaleState] = useState<string>(workspaceLocale)
  const touchedRef = useRef(false)

  useEffect(() => {
    if (!touchedRef.current) {
      setLocaleState(workspaceLocale)
    }
  }, [workspaceLocale])

  function setLocale(next: string): void {
    touchedRef.current = true
    setLocaleState(next)
  }

  return { locale, setLocale }
}
