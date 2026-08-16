import { ArrowDownLeft, ArrowUpRight, Network } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useParams } from 'react-router-dom'

import type { EdgeType, KbNode } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { DetailHeader } from '@/components/data/DetailHeader'
import { MetaPill } from '@/components/data/MetaPill'
import { Container } from '@/components/layout/Container'
import { Stack } from '@/components/layout/Stack'
import { Card, CardContent } from '@/components/ui/card'

import { StatusBadge, TierBadge } from '../components/KbBadges'
import { useKbNode } from '../hooks/useKbNode'

const EDGE_LABEL: Record<EdgeType, string> = {
  supports: 'node.edgeSupports',
  contradicts: 'node.edgeContradicts',
  supersedes: 'node.edgeSupersedes',
  derived_from: 'node.edgeDerivedFrom',
  belongs_to: 'node.edgeBelongsTo',
  co_occurs_with: 'node.edgeCoOccursWith',
}

// Beleg-Referenz → Ziel. Nur `artifact:<uuid>[#block]` wird verlinkt: es fuehrt
// in den eigenen Arbeitsbereich.
//
// `url:<u>` bleibt bewusst UNVERLINKTER Text — dieselbe Ueberlegung wie beim
// Rohtext-Rendering der Artifacts: die Referenz stammt von einem Agenten bzw.
// aus einem Ingest, also aus der am wenigsten vertrauenswuerdigen Quelle dieser
// Ansicht. Ein automatisch klickbares Ziel daraus zu machen, waere ein
// Ein-Klick-Weg von der Verwaltungsoberflaeche auf eine fremdbestimmte Adresse.
// Als voller Text ist die URL sichtbar und bewusst kopierbar — und damit fuer
// den Betreiber sogar informativer. `sha256:<h>` ist ohnehin Text: die
// Binaerdatei hat keine eigene Ansicht, die Pruefsumme IST der Beleg.
function resolveSource(
  sourceRef: string,
  wsPath: (path: string) => string,
): { kind: 'internal' | 'text'; href?: string } {
  if (sourceRef.startsWith('artifact:')) {
    const rest = sourceRef.slice('artifact:'.length)
    const [artifactId, blockId] = rest.split('#')
    if (artifactId === '') return { kind: 'text' }
    // Ohne Area-Kontext (der Beleg kennt sie nicht) faellt die Metadaten-Zeile
    // weg — Inhalt und Anker, worum es beim Beleg geht, bleiben erreichbar.
    const fragment = blockId !== undefined && blockId !== '' ? `#${blockId}` : ''
    return { kind: 'internal', href: wsPath(`/workarea/artifacts/${artifactId}${fragment}`) }
  }
  return { kind: 'text' }
}

function formatOccurred(node: KbNode, locale: string, unknownLabel: string): string {
  if (node.occurred_precision === 'unknown') return unknownLabel
  const date = new Date(node.occurred_at)
  return node.occurred_precision === 'day'
    ? date.toLocaleDateString(locale)
    : date.toLocaleString(locale)
}

export function KbNodeDetailPage() {
  const { t, i18n } = useTranslation('workarea')
  const wsPath = useWorkspacePath()
  const { nodeId } = useParams<{ nodeId: string }>()
  const { node, neighbors, loading, error } = useKbNode(nodeId ?? '')

  if (nodeId === undefined) return <Navigate to={wsPath('/workarea/kb')} replace />

  const source = node !== null ? resolveSource(node.source_ref, wsPath) : null

  return (
    <Container>
      <DataView loading={loading && node === null} error={error}>
        {node !== null && source !== null ? (
          <Stack gap="lg">
            <DetailHeader
              backHref={wsPath('/workarea/kb')}
              backLabel={t('node.back')}
              icon={Network}
              iconTone="resource"
              title={t('node.title')}
              badges={
                <>
                  <TierBadge tier={node.tier} />
                  <StatusBadge status={node.status} />
                </>
              }
            />
            <Card>
              <CardContent className="flex flex-col gap-4 pt-6">
                <p className="text-sm">{node.content}</p>
                <div className="flex flex-wrap gap-2">
                  <MetaPill tone="date">
                    {t('node.occurred', {
                      date: formatOccurred(node, i18n.language, t('node.occurredUnknown')),
                    })}
                  </MetaPill>
                  <MetaPill tone="muted">
                    {t('node.derivationDepth', { depth: node.derivation_depth })}
                  </MetaPill>
                  {node.created_by !== null ? (
                    <MetaPill tone="muted">
                      {t('node.createdBy', { actor: node.created_by })}
                    </MetaPill>
                  ) : null}
                </div>
              </CardContent>
            </Card>

            {/* Der Beleg steht bewusst als eigene Karte und nicht als Fussnote:
                die Belegpflicht ist die tragende Eigenschaft der Knowledge Base
                — ohne Quelle entsteht hier serverseitig gar kein Node. */}
            <Card>
              <CardContent className="flex flex-col gap-2 pt-6">
                <h2 className="text-sm font-semibold tracking-tight">{t('node.sourceTitle')}</h2>
                <p className="text-xs text-muted-foreground">{t('node.sourceHelp')}</p>
                {source.kind === 'internal' && source.href !== undefined ? (
                  <Link to={source.href} className="text-sm hover:underline">
                    {t('node.sourceOpen')}
                  </Link>
                ) : null}
                <p className="text-sm break-all text-muted-foreground">{node.source_ref}</p>
                {node.content_ref !== null ? (
                  <p className="text-xs text-muted-foreground">
                    {t('node.contentRef', { ref: node.content_ref })}
                  </p>
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardContent className="flex flex-col gap-3 pt-6">
                <h2 className="text-sm font-semibold tracking-tight">{t('node.neighborsTitle')}</h2>
                {neighbors.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{t('node.neighborsEmpty')}</p>
                ) : (
                  <ul className="flex flex-col gap-3">
                    {neighbors.map((neighbor) => (
                      <li
                        key={`${neighbor.edge_type}-${neighbor.direction}-${neighbor.node.id}`}
                        className="flex flex-col gap-1 rounded-md border p-3"
                      >
                        <span className="flex flex-wrap items-center gap-2">
                          {neighbor.direction === 'out' ? (
                            <ArrowUpRight className="size-4 text-muted-foreground" />
                          ) : (
                            <ArrowDownLeft className="size-4 text-muted-foreground" />
                          )}
                          <span className="text-xs font-medium">
                            {t(EDGE_LABEL[neighbor.edge_type])}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {neighbor.direction === 'out'
                              ? t('node.directionOut')
                              : t('node.directionIn')}
                          </span>
                          {/* Bei `co_occurs_with` traegt der Server IMMER die
                              Fallzahl mit — eine Korrelation ohne n ist eine
                              Behauptung, keine Aussage (Spec-Akzeptanz O). */}
                          {neighbor.co_n !== null ? (
                            <MetaPill tone="muted">{t('node.coN', { count: neighbor.co_n })}</MetaPill>
                          ) : null}
                          <TierBadge tier={neighbor.node.tier} />
                        </span>
                        <Link
                          to={wsPath(`/workarea/kb/${neighbor.node.id}`)}
                          className="text-sm hover:underline"
                        >
                          {neighbor.node.content}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </Stack>
        ) : null}
      </DataView>
    </Container>
  )
}
