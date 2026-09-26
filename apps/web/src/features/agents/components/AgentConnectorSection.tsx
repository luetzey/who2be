import { Copy } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { config } from '@/config'
import { copyToClipboard } from '@/lib/clipboard'
import { notify } from '@/lib/feedback'

interface AgentConnectorSectionProps {
  agentId: string
  agentName: string
}

// Feld-/Button-Zeile der beiden Kopierfelder. Connector-Name und Server-URL
// sind lange, trennstellenfreie technische Bezeichner: in der einzeiligen
// `flex`-Zeile schrumpft das `Input` bei 320 px gemessen auf 95 px (URL) bzw.
// 77 px (Name), waehrend der Inhalt 521 bzw. 412 px breit ist — praktisch
// nichts davon ist lesbar. Das erzeugt zwar keinen Body-Scroll, ist aber
// Punkt 5 der Review-Checkliste in `docs/frontend/design-language.md` §4.4
// („keine abgeschnittenen Labels") und AK 2 von #570.
//
// `flex-col` unterhalb `md` stellt den Button unter das Feld; das Feld
// erreicht damit die volle Spaltenbreite (gemessen 238 px). Ab `md` stellt
// `md:flex-row md:items-center` die Desktop-Zeile wieder her (Feld 527 px).
// Der Button wird mobil bewusst voll breit und faellt ab `md` auf
// `md:w-auto` zurueck — kein `min-w-0` am `Input`: gemessen bringt es hier
// nichts, weil `Input` bereits `w-full` traegt und die Zeile ihn ohnehin
// staucht.
const FIELD_ROW = 'flex flex-col gap-2 md:flex-row md:items-center'
const FIELD_ROW_BUTTON = 'w-full md:w-auto'

/**
 * Kopierbare Verbindungsparameter fuer einen Remote-MCP-Connector (OAuth) dieses
 * Agenten. Die URL traegt den Agenten im Pfad (`/a/<id>`), damit sie pro Agent
 * eindeutig ist (Claude lehnt Duplikat-URLs ab) und den Agenten beim Consent
 * bindet. Der Pfad ist bewusst gewaehlt statt einer Query: Der LLM-Client nutzt
 * fuer den OAuth-`resource`-Parameter die kanonische PRM-Resource des
 * MCP-Servers und verwirft dabei die Query — mit `?agent=` kam der Hint nie
 * beim Consent an und der User musste den Agenten erneut im Dropdown waehlen.
 * Der Pfad ist Teil der Resource-Identitaet und ueberlebt. Kein Token — die
 * Autorisierung laeuft ueber den OAuth-Login.
 */
export function AgentConnectorSection({ agentId, agentName }: AgentConnectorSectionProps) {
  const { t } = useTranslation('agents')
  const connectorUrl = `${config.mcpUrl.replace(/\/+$/, '')}/a/${agentId}`
  const connectorName = t('connector.nameValue', { name: agentName })

  function copy(value: string) {
    void copyToClipboard(value)
      .then(() => notify.success(t('connector.copied')))
      .catch((cause: unknown) => {
        const message = cause instanceof Error ? cause.message : t('connector.error')
        notify.error(message)
      })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('connector.title')}</CardTitle>
      </CardHeader>
      <CardContent>
        <Stack gap="md">
          <p className="text-sm text-muted-foreground">{t('connector.description')}</p>

          <div className="flex flex-col gap-2">
            <Label htmlFor="connector-name">{t('connector.nameLabel')}</Label>
            <div className={FIELD_ROW}>
              <Input
                id="connector-name"
                readOnly
                value={connectorName}
                onFocus={(event) => event.currentTarget.select()}
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                className={FIELD_ROW_BUTTON}
                onClick={() => copy(connectorName)}
              >
                <Copy className="h-4 w-4" />
                {t('connector.copyName')}
              </Button>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="connector-url">{t('connector.urlLabel')}</Label>
            <div className={FIELD_ROW}>
              <Input
                id="connector-url"
                readOnly
                value={connectorUrl}
                className="font-mono text-xs"
                onFocus={(event) => event.currentTarget.select()}
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                className={FIELD_ROW_BUTTON}
                onClick={() => copy(connectorUrl)}
              >
                <Copy className="h-4 w-4" />
                {t('connector.copyUrl')}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">{t('connector.urlHint')}</p>
          </div>
        </Stack>
      </CardContent>
    </Card>
  )
}
