import { ChevronDown, Clipboard } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { AgentRenderFormat } from '@/api/types'
import { useApi } from '@/api/useApi'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { copyToClipboard } from '@/lib/clipboard'
import { notify } from '@/lib/feedback'

interface CopyPromptButtonProps {
  agentId: string
  /** Wird true, wenn der Agent deaktiviert ist — Render-Endpoint wirft 409. */
  disabled?: boolean
}

/**
 * Split-Button: Primary kopiert den Plain-Prompt, das Dropdown bietet
 * Markdown- und HTML-Varianten. Das Render-Ergebnis landet via
 * `copyToClipboard` in der Zwischenablage — der Wrapper deckt
 * Non-Secure-Contexts (selbst-gehostete HTTP-Origins ohne TLS) mit einem
 * Textarea-/execCommand-Fallback ab, sonst crasht `navigator.clipboard`
 * mit `undefined`. Unresolved Placeholders triggern einen sekundaeren
 * Hinweis-Toast.
 */
export function CopyPromptButton({ agentId, disabled = false }: CopyPromptButtonProps) {
  const { t } = useTranslation('agents')
  const api = useApi()
  const [busy, setBusy] = useState<AgentRenderFormat | null>(null)

  const copy = async (format: AgentRenderFormat) => {
    setBusy(format)
    try {
      const result = await api.renderAgentPrompt(agentId, format)
      await copyToClipboard(result.content)
      notify.success(t(`copy.success.${format}`))
      if (result.unresolved_placeholders.length > 0) {
        notify.info(
          t('copy.unresolvedHint', {
            count: result.unresolved_placeholders.length,
            list: result.unresolved_placeholders.join(', '),
          }),
        )
      }
    } catch (cause: unknown) {
      const message = cause instanceof Error ? cause.message : t('copy.error')
      notify.error(message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="inline-flex" data-testid="copy-prompt-button">
      <Button
        type="button"
        variant="brand"
        disabled={disabled || busy !== null}
        onClick={() => void copy('plain')}
        className="rounded-r-none"
        data-testid="copy-prompt-primary"
      >
        <Clipboard className="h-4 w-4" />
        {t('copy.plain')}
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="brand"
            disabled={disabled || busy !== null}
            aria-label={t('copy.formatSelect')}
            // `w-10 md:w-auto`: der Dropdown-Teil traegt nur ein Chevron;
            // `px-2` um ein 16-px-Icon ergibt gemessen 33 px Breite bei 40 px
            // Hoehe. Das haelt zwar den Floor aus
            // `docs/frontend/design-language.md` §11 (>= 32 px, dort die
            // einzige Quelle), bleibt in der Breite aber unter den 40 px, die
            // AK 4 von #570 unterhalb `md` verlangt. `w-10` macht daraus
            // 40x40 px; ab `md` gibt `md:w-auto` die Desktop-Dichte frei.
            className="w-10 rounded-l-none border-l border-l-primary-foreground/30 px-2 md:w-auto"
            data-testid="copy-prompt-dropdown-trigger"
          >
            <ChevronDown className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onSelect={() => void copy('markdown')}
            data-testid="copy-prompt-option-markdown"
          >
            {t('copy.markdown')}
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => void copy('html')}
            data-testid="copy-prompt-option-html"
          >
            {t('copy.html')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
