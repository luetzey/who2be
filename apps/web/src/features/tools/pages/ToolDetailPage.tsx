import { ChevronRight, Clock, GitBranch, Pencil, Plug, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { VersionStatus } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { AttentionBanner } from '@/components/data/AttentionBanner'
import { BranchStatus } from '@/components/data/BranchStatus'
import { DataView } from '@/components/data/DataView'
import { DetailHeader } from '@/components/data/DetailHeader'
import { LocaleBadge } from '@/components/data/LocaleBadge'
import { ManagedNotice } from '@/components/data/ManagedNotice'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Container } from '@/components/layout/Container'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { StatusActionBar, statusLabel, VersionHistory } from '@/components/version'
import { cn } from '@/lib/utils'
import { notify } from '@/lib/feedback'

import { DeleteToolButton } from '../components/DeleteToolButton'
import { ExportToolButton } from '../components/ExportToolButton'
import { ToolEditorForm } from '../components/ToolEditorForm'
import { useTool } from '../hooks/useTool'
import { useToolForm } from '../hooks/useToolForm'

export function ToolDetailPage() {
  const { t } = useTranslation('tools')
  const { id } = useParams<{ id: string }>()
  const { tool, versions, loading, error, reload } = useTool(id)
  const { form, autoSave, initialUsageNotesBlocks } = useToolForm(tool, reload)
  const wsPath = useWorkspacePath()
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const [dangerOpen, setDangerOpen] = useState(false)
  // Vom System verwaltet: Editor read-only, keine Status-/Lösch-Aktionen
  // (Backend sperrt Mutationen mit 403 managed_aggregate).
  const locked = tool?.is_managed === true
  const canEdit = (role === 'admin' || role === 'editor') && !locked

  if (id === undefined) {
    return <Navigate to={wsPath('/tools')} replace />
  }

  const draftVersion = versions.find((v) => v.status === 'draft')
  const reviewVersion = versions.find((v) => v.status === 'review')
  const activeVersion = versions.find((v) => v.status === 'active')
  const inactiveCurrent =
    activeVersion === undefined
      ? versions.find(
          (v) => v.version === tool?.current_version && v.status === 'inactive',
        )
      : undefined

  const promotableVersion = reviewVersion ?? draftVersion

  const description =
    tool === null
      ? ''
      : activeVersion !== undefined
        ? `${t('detail.activeVersion', { version: activeVersion.version })}${
            draftVersion !== undefined
              ? ` · ${t('detail.workingOnDraft', { version: draftVersion.version })}`
              : reviewVersion !== undefined
                ? ` · ${t('detail.inReview', { version: reviewVersion.version })}`
                : ''
          }`
        : t('detail.currentVersion', {
            version: tool.current_version,
            status: statusLabel(tool.current_status ?? 'draft'),
          })

  const bannerText = (status: VersionStatus, version: number) => {
    if (status === 'review') {
      return {
        title: t('detail.bannerReviewTitle', { version }),
        desc: t('detail.bannerReviewDescription'),
      }
    }
    if (status === 'inactive') {
      return {
        title: t('detail.bannerInactiveTitle', { version }),
        desc: t('detail.bannerInactiveDescription'),
      }
    }
    return {
      title: t('detail.bannerDraftTitle', { version }),
      desc: t('detail.bannerDraftDescription'),
    }
  }

  const tags = tool?.content.tags ?? []

  return (
    <Container>
      <DataView loading={loading && tool === null} error={error}>
        {tool !== null ? (
          <Stack gap="lg">
            <Stack gap="sm">
              <DetailHeader
                backHref={wsPath('/tools')}
                backLabel={t('list.title')}
                icon={Plug}
                iconTone="tools"
                title={tool.name}
                badges={
                  <>
                    <Badge variant="outline" className="font-mono text-xs">
                      {tool.alias}
                    </Badge>
                    <StatusBadge
                      status={tool.current_status}
                      pendingDraft={tool.has_pending_draft}
                    />
                    <LocaleBadge locale={tool.locale} />
                    {tags.map((tag) => (
                      <Badge key={tag} variant="secondary" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                  </>
                }
                description={description}
                actions={<ExportToolButton tool={tool} />}
              />

              {locked ? <ManagedNotice /> : null}

              <BranchStatus
                activeVersion={activeVersion?.version}
                draftVersion={draftVersion?.version}
                reviewVersion={reviewVersion?.version}
                inactiveVersion={inactiveCurrent?.version}
                currentVersion={tool.current_version}
                saveState={autoSave}
                actions={[]}
              />

              {!locked && promotableVersion !== undefined
                ? (() => {
                    const status = promotableVersion.status ?? 'draft'
                    const text = bannerText(status, promotableVersion.version)
                    return (
                      <AttentionBanner
                        variant="brand"
                        icon={Clock}
                        title={text.title}
                        description={text.desc}
                        actions={
                          <StatusActionBar
                            status={status}
                            onTransition={(to) =>
                              api.transitionExternalToolVersion(
                                tool.id,
                                promotableVersion.version,
                                to,
                              )
                            }
                            onTransitioned={reload}
                          />
                        }
                      />
                    )
                  })()
                : null}

              {!locked && inactiveCurrent !== undefined
                ? (() => {
                    const text = bannerText('inactive', inactiveCurrent.version)
                    return (
                      <AttentionBanner
                        variant="brand"
                        icon={RotateCcw}
                        title={text.title}
                        description={text.desc}
                        actions={
                          <StatusActionBar
                            status="inactive"
                            onTransition={(to) =>
                              api.transitionExternalToolVersion(
                                tool.id,
                                inactiveCurrent.version,
                                to,
                              )
                            }
                            onTransitioned={reload}
                          />
                        }
                      />
                    )
                  })()
                : null}
            </Stack>

            <Tabs defaultValue="edit">
              <TabsList aria-label="Detail-Ansicht">
                <TabsTrigger value="edit">
                  <Pencil aria-hidden="true" />
                  {t('tabs.edit')}
                </TabsTrigger>
                <TabsTrigger value="versions">
                  <GitBranch aria-hidden="true" />
                  {t('tabs.versions')}
                </TabsTrigger>
              </TabsList>

              <TabsContent value="edit">
                <Stack gap="md">
                  <ToolEditorForm
                    form={form}
                    formKey={`${tool.id}-${tool.current_version}`}
                    initialUsageNotesBlocks={initialUsageNotesBlocks}
                    alias={tool.alias}
                    locked={locked}
                  />

                  {canEdit ? (
                    <section
                      className="rounded-xl border border-destructive/30"
                      aria-label={t('delete.dangerZoneTitle')}
                    >
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-expanded={dangerOpen}
                        onClick={() => setDangerOpen((open) => !open)}
                        className="h-auto w-full justify-start gap-2 px-4 py-3 text-sm font-medium text-destructive hover:text-destructive"
                      >
                        <ChevronRight
                          className={cn(
                            'size-4 transition-transform duration-[var(--duration-fast)] ease-standard',
                            dangerOpen && 'rotate-90',
                          )}
                          aria-hidden="true"
                        />
                        {t('delete.dangerZoneTitle')}
                      </Button>
                      {dangerOpen ? (
                        <div className="flex flex-col gap-3 px-4 pb-4">
                          <p className="text-sm text-muted-foreground">
                            {t('delete.dangerZoneDescription')}
                          </p>
                          <div>
                            <DeleteToolButton tool={tool} />
                          </div>
                        </div>
                      ) : null}
                    </section>
                  ) : null}
                </Stack>
              </TabsContent>

              <TabsContent value="versions">
                <VersionHistory
                  versions={versions}
                  canEdit={canEdit}
                  onRestore={async (version) => {
                    await autoSave.flush()
                    await api.restoreExternalToolVersion(tool.id, version)
                    notify.success(t('detail.restoredAsDraft', { version }))
                    reload()
                  }}
                  loadProvenance={(version) =>
                    api.provenanceExternalToolVersion(tool.id, version)
                  }
                />
              </TabsContent>
            </Tabs>
          </Stack>
        ) : null}
      </DataView>
    </Container>
  )
}
