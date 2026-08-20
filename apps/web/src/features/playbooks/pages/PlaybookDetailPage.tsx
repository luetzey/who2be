import { ArrowLeft, ChevronRight, Users } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { LocaleBadge } from '@/components/data/LocaleBadge'
import { ManagedNotice } from '@/components/data/ManagedNotice'
import { GiveFeedbackDialog } from '@/components/feedback/GiveFeedbackDialog'
import { StatusActionBar, VersionHistory } from '@/components/version'
import { Container } from '@/components/layout/Container'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EntityDeleteButton, EntityExportButton } from '@/components/entity'
import { usePlaybookComposes } from '@/hooks/usePlaybookComposes'
import { usePlaybookResourceLinks } from '@/hooks/usePlaybookResourceLinks'
import { usePlaybookUsages } from '@/hooks/usePlaybookUsages'
import { cn } from '@/lib/utils'
import { notify } from '@/lib/feedback'

import { ComposedByList } from '../components/ComposedByList'
import { LinkedBlocksList } from '../components/LinkedBlocksList'
import {
  PlaybookDetailTabs,
  playbookTabId,
  playbookTabPanelId,
  type PlaybookDetailTab,
} from '../components/PlaybookDetailTabs'
import { PlaybookEditorForm } from '../components/PlaybookEditorForm'
import { PlaybookTypeIcon } from '../components/PlaybookTypeIcon'
import { ReviewBanner } from '../components/ReviewBanner'
import { SubPlaybookFlow } from '../components/SubPlaybookFlow'
import { usePlaybook } from '../hooks/usePlaybook'
import { usePlaybookForm } from '../hooks/usePlaybookForm'

// Avatar-Initialen fuer die „Verwendet in"-Liste: erste Buchstaben der
// ersten beiden Woerter („Coach Carla" → „CC").
function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter((word) => word !== '')
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('')
}

export function PlaybookDetailPage() {
  const { t } = useTranslation('playbooks')
  const { id } = useParams<{ id: string }>()
  const { playbook, versions, loading, error, reload } = usePlaybook(id)
  const { form, autoSave, initialBodyBlocks } = usePlaybookForm(playbook, reload)
  const resourceLinks = usePlaybookResourceLinks(id)
  const usages = usePlaybookUsages(id)
  const composition = usePlaybookComposes(id)
  const wsPath = useWorkspacePath()
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const [activeTab, setActiveTab] = useState<PlaybookDetailTab>('edit')
  const [dangerOpen, setDangerOpen] = useState(false)
  // Vom System verwaltet (Builder-Playbook): Editor read-only, keine Status-/
  // Lösch-Aktionen (Backend sperrt mit 403 managed_aggregate).
  const locked = playbook?.is_managed === true

  if (id === undefined) {
    return <Navigate to={wsPath('/playbooks')} replace />
  }

  const activeVersion = versions.find((v) => v.status === 'active')
  const draftVersion = versions.find((v) => v.status === 'draft')
  const reviewVersion = versions.find((v) => v.status === 'review')
  const inactiveCurrent =
    activeVersion === undefined && playbook !== null
      ? versions.find(
          (v) => v.version === playbook.current_version && v.status === 'inactive',
        )
      : undefined

  // Zentrale StatusActionBar (Issue #391) ersetzt die frühere Inline-
  // Transition-Logik (`runTransition` + manuelles `BranchAction[]`).
  // Promotable-Version wie in ResourceDetailPage/ToolDetailPage: das Backend
  // garantiert, dass nie Draft UND Review gleichzeitig existieren.
  const promotableVersion = !locked ? (reviewVersion ?? draftVersion) : undefined
  const inactiveTarget = !locked ? inactiveCurrent : undefined
  const hasBranchActions = promotableVersion !== undefined || inactiveTarget !== undefined

  // Sichtbare Button-Texte bleiben ueber `labels` die bestehenden
  // `actions.*`-Keys; Toasts/Fehlerpfad/Admin-Gate uebernimmt die Bar
  // (identische Texte in common:statusBar.* wie zuvor in playbooks:toast.*).
  const branchLabels = {
    submit: t('actions.draftSubmit'),
    promote: t('actions.publish'),
    reject: t('actions.rejectDraft'),
    reactivate: t('actions.reactivateDraft'),
  }

  // Banner nur, wenn es einen Branch-Zustand oder Aktionen zu zeigen gibt —
  // eine rein aktive Version traegt das Hero-Status-Chip allein.
  const showBanner =
    draftVersion !== undefined ||
    reviewVersion !== undefined ||
    inactiveCurrent !== undefined ||
    hasBranchActions

  const tabPanelProps = (tab: PlaybookDetailTab) => ({
    role: 'tabpanel' as const,
    id: playbookTabPanelId(tab),
    'aria-labelledby': playbookTabId(tab),
    hidden: activeTab !== tab,
  })

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/playbooks')}>
            <ArrowLeft className="h-4 w-4" />
            {t('detail.back')}
          </Link>
        </Button>

        <DataView loading={loading && playbook === null} error={error}>
          {playbook !== null ? (
            <Stack gap="md">
              <header className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3">
                    <PlaybookTypeIcon type={playbook.type} />
                    <h1 className="text-2xl font-semibold tracking-tight">
                      {playbook.name}
                    </h1>
                    {playbook.current_status !== undefined ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground">
                        <span
                          className="inline-block size-2 rounded-full"
                          style={{
                            backgroundColor: `var(--status-${playbook.current_status})`,
                          }}
                          aria-hidden="true"
                        />
                        {t(`common:status.${playbook.current_status}`)} · v
                        {playbook.current_version}
                      </span>
                    ) : null}
                    <LocaleBadge locale={playbook.locale} />
                  </div>
                  {playbook.content.description !== '' ? (
                    <p className="mt-2 text-sm text-muted-foreground">
                      {playbook.content.description}
                    </p>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {role === 'admin' || role === 'editor' ? (
                    <GiveFeedbackDialog
                      entityType="playbook"
                      entityId={playbook.id}
                      entityName={playbook.name}
                      version={playbook.current_version}
                    />
                  ) : null}
                  <EntityExportButton
                    entityKind="playbook"
                    name={playbook.name || playbook.id}
                    onExport={(format) => api.exportPlaybook(playbook.id, format)}
                    testIdPrefix="export-playbook"
                  />
                </div>
              </header>

              {locked ? <ManagedNotice /> : null}

              {showBanner ? (
                <ReviewBanner
                  activeVersion={activeVersion?.version}
                  draftVersion={draftVersion?.version}
                  reviewVersion={reviewVersion?.version}
                  inactiveVersion={inactiveCurrent?.version}
                  saveState={autoSave}
                  actions={
                    hasBranchActions ? (
                      <>
                        {promotableVersion !== undefined ? (
                          <StatusActionBar
                            status={promotableVersion.status ?? 'draft'}
                            labels={branchLabels}
                            onTransition={async (to) => {
                              await autoSave.flush()
                              return api.transitionPlaybookVersion(
                                playbook.id,
                                promotableVersion.version,
                                to,
                              )
                            }}
                            onTransitioned={reload}
                          />
                        ) : null}
                        {inactiveTarget !== undefined ? (
                          <StatusActionBar
                            status="inactive"
                            labels={branchLabels}
                            onTransition={async (to) => {
                              await autoSave.flush()
                              return api.transitionPlaybookVersion(
                                playbook.id,
                                inactiveTarget.version,
                                to,
                              )
                            }}
                            onTransitioned={reload}
                          />
                        ) : null}
                      </>
                    ) : undefined
                  }
                />
              ) : null}

              <PlaybookDetailTabs active={activeTab} onChange={setActiveTab} />

              {/* Panels bleiben gemountet (hidden), damit Editor-/Form-State
                  beim Tab-Wechsel nicht verloren geht. */}
              <div {...tabPanelProps('edit')}>
                <Stack gap="md">
                  <PlaybookEditorForm
                    form={form}
                    formKey={`${playbook.id}-${playbook.current_version}`}
                    initialBodyBlocks={initialBodyBlocks}
                    locked={locked}
                  />

                  {role !== 'viewer' && !locked ? (
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
                            <EntityDeleteButton
                              name={playbook.name}
                              texts={{
                                dialogTitle: t('delete.dialogTitle'),
                                success: t('delete.success'),
                                viewerReadOnly: t('delete.viewerReadOnly'),
                                blockedMessage: t('delete.blockedMessage'),
                              }}
                              onDelete={() => api.deletePlaybook(playbook.id)}
                              listPath={wsPath('/playbooks')}
                              testIdPrefix="delete-playbook"
                            />
                          </div>
                        </div>
                      ) : null}
                    </section>
                  ) : null}
                </Stack>
              </div>

              <div {...tabPanelProps('relations')}>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Card className="sm:col-span-2">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Users className="size-4 text-muted-foreground" aria-hidden="true" />
                        {t('detail.usedInTitle')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <DataView
                        loading={usages.loading}
                        error={usages.error}
                        empty={!usages.loading && usages.usages.length === 0}
                        emptyTitle={t('detail.usedInEmpty')}
                        emptyDescription={t('detail.usedInEmptyDescription')}
                      >
                        <p className="mb-3 text-xs text-muted-foreground">
                          {t('detail.usedInDescription')}
                        </p>
                        <ul className="flex flex-col gap-1">
                          {usages.usages.map((usage) => (
                            <li key={usage.persona_id}>
                              <Link
                                to={wsPath(`/personas/${usage.persona_id}`)}
                                className="flex items-center gap-2 rounded-sm py-1 text-sm text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                              >
                                <span
                                  className="flex size-6 shrink-0 items-center justify-center rounded-full bg-pill-persona text-xs font-semibold text-pill-persona-fg"
                                  aria-hidden="true"
                                >
                                  {initials(usage.persona_name)}
                                </span>
                                <span className="truncate">{usage.persona_name}</span>
                              </Link>
                            </li>
                          ))}
                        </ul>
                      </DataView>
                    </CardContent>
                  </Card>

                  <Card className="sm:col-span-2">
                    <CardHeader>
                      <CardTitle>{t('detail.subPlaybooksTitle')}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Stack gap="sm">
                        <DataView loading={composition.loading} error={composition.error}>
                          {composition.children.length > 0 ? (
                            <p className="text-xs text-muted-foreground">
                              {t('detail.subPlaybooksFlowDescription')}
                            </p>
                          ) : null}
                          <SubPlaybookFlow children={composition.children} wsPath={wsPath} />
                        </DataView>
                        <p className="text-xs text-muted-foreground">
                          {t('detail.subPlaybooksBodyNote')}
                        </p>
                      </Stack>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>{t('detail.composedByTitle')}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ComposedByList parents={composition.parents} />
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>{t('detail.resourceLinksTitle')}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Stack gap="sm">
                        <DataView
                          loading={resourceLinks.loading}
                          error={resourceLinks.error}
                        >
                          <LinkedBlocksList links={resourceLinks.links} disabled />
                        </DataView>
                        <p className="text-xs text-muted-foreground">
                          {t('detail.resourceLinksBodyNote')}
                        </p>
                      </Stack>
                    </CardContent>
                  </Card>
                </div>
              </div>

              <div {...tabPanelProps('versions')}>
                <VersionHistory
                  versions={versions}
                  canEdit={role === 'admin' || role === 'editor'}
                  onRestore={async (version) => {
                    await api.restorePlaybookVersion(playbook.id, version)
                    notify.success(t('detail.restoreSuccess', { version }))
                    reload()
                  }}
                  loadDiff={(version) => api.diffPlaybookVersion(playbook.id, version)}
                  loadProvenance={(version) =>
                    api.provenancePlaybookVersion(playbook.id, version)
                  }
                />
              </div>
            </Stack>
          ) : null}
        </DataView>
      </Stack>
    </Container>
  )
}
