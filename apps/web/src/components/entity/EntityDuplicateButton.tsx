import { Copy } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { Button } from '@/components/ui/button'
import { notify } from '@/lib/feedback'

export interface EntityDuplicateButtonTexts {
  /** Erfolgs-Toast nach dem Duplizieren, z. B. "Persona dupliziert." */
  success: string
  /** Fallback-Fehlertext, falls die Mutation ohne `Error`-Message scheitert. */
  error: string
  /** Tooltip-Text fuer Viewer (Button ist dann disabled). */
  viewerReadOnly: string
}

interface EntityDuplicateButtonProps<T extends { id: string }> {
  texts: EntityDuplicateButtonTexts
  /** Sichtbarer Button-Text, z. B. "Duplizieren". */
  label: string
  /** Fuehrt die Deep-Copy-Mutation aus und liefert die neu angelegte Kopie. */
  onDuplicate: () => Promise<T>
  /** Baut den Detail-Pfad der Kopie aus ihrer ID (bereits workspace-praefixiert). */
  detailPath: (id: string) => string
  /** `data-testid`-Wert des Buttons (kein Praefix — ein Trigger, kein Dialog). */
  testId: string
}

/**
 * Generischer Duplizieren-Button: ruft die Deep-Copy-Mutation auf und navigiert
 * bei Erfolg zur Kopie. Ausgegraut fuer Viewer — das Backend lehnt die Mutation
 * sonst ohnehin ab (403).
 */
export function EntityDuplicateButton<T extends { id: string }>({
  texts,
  label,
  onDuplicate,
  detailPath,
  testId,
}: EntityDuplicateButtonProps<T>) {
  const navigate = useNavigate()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const [busy, setBusy] = useState(false)

  const disabled = isViewer || busy
  const title = isViewer ? texts.viewerReadOnly : undefined

  const onCopy = async () => {
    setBusy(true)
    try {
      const created = await onDuplicate()
      notify.success(texts.success)
      navigate(detailPath(created.id))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : texts.error)
      setBusy(false)
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      disabled={disabled}
      title={title}
      onClick={() => void onCopy()}
      data-testid={testId}
    >
      <Copy className="h-4 w-4" />
      {label}
    </Button>
  )
}
