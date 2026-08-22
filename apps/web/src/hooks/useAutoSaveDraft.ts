import { useCallback, useEffect, useRef, useState } from 'react'
import i18n from '@/i18n'

// Auto-Save-Hook (Phase 3-Runde-3 Track 2). Wartet `debounceMs` nach dem
// letzten Wertewechsel, ruft dann `patchFn(values)`. Flusht bei `unmount`,
// `beforeunload` und `window`-blur, damit ein Tab-Schliesser keinen
// ungespeicherten Stand verliert.
//
// Werte werden vor dem Vergleich JSON-serialisiert; nur veraenderte
// Snapshots loesen einen Server-Call aus. `isReady` haelt das erste
// `form.reset(...)` davon ab, einen leeren PATCH abzuschicken — die
// Detail-Pages setzen es auf `true`, sobald die Entity geladen ist.

export type AutoSaveStatus = 'idle' | 'saving' | 'saved' | 'error'

export interface AutoSaveState {
  status: AutoSaveStatus
  lastSavedAt: Date | null
  errorMessage: string | null
}

export interface UseAutoSaveDraftOptions<T> {
  values: T
  isReady: boolean
  patchFn: (values: T) => Promise<unknown>
  debounceMs?: number
  // Welle 4 (Folge-Fix): Detail-Pages wollen nach jedem erfolgreichen
  // Auto-Save den Versions-/Status-Snapshot vom Server nachholen, damit
  // der gerade angelegte Draft direkt in der BranchStatus + Versionsliste
  // auftaucht. `onSaved` wird genau einmal pro erfolgreicher Save-Runde
  // gefeuert, nach `lastSavedSnapshotRef`-Update.
  onSaved?: () => void
}

export interface UseAutoSaveDraftResult extends AutoSaveState {
  flush: () => Promise<void>
}

const DEFAULT_DEBOUNCE_MS = 1500

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.autoSaveFailed')
}

export function useAutoSaveDraft<T>({
  values,
  isReady,
  patchFn,
  debounceMs = DEFAULT_DEBOUNCE_MS,
  onSaved,
}: UseAutoSaveDraftOptions<T>): UseAutoSaveDraftResult {
  const [state, setState] = useState<AutoSaveState>({
    status: 'idle',
    lastSavedAt: null,
    errorMessage: null,
  })

  // Refs halten "lebende" Werte ausserhalb der Render-Closure — sonst sehen
  // Timeout/Listener veraltete props. `lastSavedSnapshot` startet mit der
  // initialen Serialisierung, sobald `isReady=true` wird; dadurch wird der
  // erste Render-Pass nicht als Aenderung gewertet.
  const valuesRef = useRef(values)
  const isReadyRef = useRef(isReady)
  const patchFnRef = useRef(patchFn)
  const onSavedRef = useRef(onSaved)
  const lastSavedSnapshotRef = useRef<string | null>(null)
  const pendingSnapshotRef = useRef<string | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const inFlightRef = useRef<Promise<void> | null>(null)

  valuesRef.current = values
  isReadyRef.current = isReady
  patchFnRef.current = patchFn
  onSavedRef.current = onSaved

  const runSave = useCallback(async (): Promise<void> => {
    if (!isReadyRef.current) {
      return
    }
    const snapshot = pendingSnapshotRef.current
    if (snapshot === null || snapshot === lastSavedSnapshotRef.current) {
      return
    }
    // Serialisieren am Save-Eintritt: spaetere Aenderungen waehrend des
    // Server-Calls werden in der naechsten Runde gesichert.
    const captured = valuesRef.current
    setState((prev) => ({ ...prev, status: 'saving', errorMessage: null }))
    try {
      await patchFnRef.current(captured)
      lastSavedSnapshotRef.current = snapshot
      setState({
        status: 'saved',
        lastSavedAt: new Date(),
        errorMessage: null,
      })
      // Nach erfolgreichem Save: Detail-Page-Refetch triggern (Status/Version
      // im UI aktualisieren). Out-of-band, damit ein onSaved-Fehler den
      // Save-Status nicht ueberschreibt.
      onSavedRef.current?.()
    } catch (cause) {
      setState((prev) => ({
        status: 'error',
        lastSavedAt: prev.lastSavedAt,
        errorMessage: describeError(cause),
      }))
    }
  }, [])

  const scheduleSave = useCallback(
    (snapshot: string) => {
      pendingSnapshotRef.current = snapshot
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current)
      }
      timeoutRef.current = setTimeout(() => {
        timeoutRef.current = null
        inFlightRef.current = runSave().finally(() => {
          inFlightRef.current = null
        })
      }, debounceMs)
    },
    [debounceMs, runSave],
  )

  const flush = useCallback(async (): Promise<void> => {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    if (inFlightRef.current !== null) {
      await inFlightRef.current
    }
    if (
      pendingSnapshotRef.current !== null &&
      pendingSnapshotRef.current !== lastSavedSnapshotRef.current
    ) {
      await runSave()
    }
  }, [runSave])

  // Werte-Watcher: serialisiert und vergleicht. Beim ersten "Ready"-Frame
  // ankert er den Snapshot, damit `form.reset(...)` keinen Save ausloest.
  useEffect(() => {
    if (!isReady) {
      return
    }
    const snapshot = JSON.stringify(values)
    if (lastSavedSnapshotRef.current === null) {
      lastSavedSnapshotRef.current = snapshot
      pendingSnapshotRef.current = snapshot
      return
    }
    if (snapshot === lastSavedSnapshotRef.current) {
      return
    }
    scheduleSave(snapshot)
  }, [values, isReady, scheduleSave])

  // Browser-Events: window-blur (Tab-Switch) + beforeunload (Schliesser).
  // `beforeunload` darf nicht awaiten — wir feuern den PATCH und hoffen
  // (Beacon-API waere sauberer, aber 1500 ms vorher wurde das Timeout
  // schon gestartet, daher reicht das fuer den Smoke).
  useEffect(() => {
    const onBlur = () => {
      void flush()
    }
    const onBeforeUnload = () => {
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
      if (
        pendingSnapshotRef.current !== null &&
        pendingSnapshotRef.current !== lastSavedSnapshotRef.current
      ) {
        // Best-effort feuern; die Promise wird nicht awaited.
        void runSave()
      }
    }
    window.addEventListener('blur', onBlur)
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => {
      window.removeEventListener('blur', onBlur)
      window.removeEventListener('beforeunload', onBeforeUnload)
    }
  }, [flush, runSave])

  // Cleanup beim Unmount: ausstehendes Timeout flushen.
  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
        if (
          pendingSnapshotRef.current !== null &&
          pendingSnapshotRef.current !== lastSavedSnapshotRef.current
        ) {
          void runSave()
        }
      }
    }
  }, [runSave])

  return { ...state, flush }
}
