import { Copy } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { config } from '@/config'
import { copyToClipboard } from '@/lib/clipboard'
import { notify } from '@/lib/feedback'
import { MCP_CONFIG_FORMATS, buildMcpConfig, type McpConfigFormat } from '@/lib/mcpConfig'

interface McpConfigCopyProps {
  /** Der frisch erzeugte/rotierte Token — der HTTP-MCP-Server nutzt ihn pro Request. */
  token: string
}

/**
 * Ein-Klick-MCP-Konfiguration fuer den frisch erzeugten Token. Formate: JSON
 * (mcpServers), Claude-Code-CLI, URL+Header, Prompt-Snippet. Lebt nur im
 * Reveal-Moment (Token danach nicht mehr verfuegbar).
 */
export function McpConfigCopy({ token }: McpConfigCopyProps) {
  const { t } = useTranslation('tokens')
  const [format, setFormat] = useState<McpConfigFormat>('json')
  const mcpUrl = config.mcpUrl

  const content =
    format === 'prompt'
      ? t('mcp.promptTemplate', { url: mcpUrl, token })
      : buildMcpConfig(format, { mcpUrl, token })

  return (
    <Stack gap="sm">
      <div className="flex flex-col gap-2">
        <Label htmlFor="mcp-config-format">{t('mcp.label')}</Label>
        <Select
          id="mcp-config-format"
          value={format}
          onChange={(event) => setFormat(event.target.value as McpConfigFormat)}
        >
          {MCP_CONFIG_FORMATS.map((entry) => (
            <option key={entry.id} value={entry.id}>
              {t(entry.labelKey)}
            </option>
          ))}
        </Select>
      </div>
      <Textarea
        readOnly
        aria-label={t('mcp.ariaLabel')}
        value={content}
        rows={7}
        className="font-mono text-xs"
        onFocus={(event) => event.currentTarget.select()}
      />
      <div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => {
            void copyToClipboard(content).catch((cause: unknown) => {
              const message = cause instanceof Error ? cause.message : t('common:error.generic')
              notify.error(message)
            })
          }}
        >
          <Copy className="h-4 w-4" />
          {t('mcp.copyButton')}
        </Button>
      </div>
    </Stack>
  )
}
