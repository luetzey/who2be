import { Clock, History, Layers, Share2, SquarePen, Users } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { VersionStatus } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { AttentionBanner } from '@/components/data/AttentionBanner'
import { SaveIndicator, type BranchAction } from '@/components/data/BranchStatus'
import { DataView } from '@/components/data/DataView'
import { DetailHeader } from '@/components/data/DetailHeader'
import { LocaleBadge } from '@/components/data/LocaleBadge'
import { ManagedNotice } from '@/components/data/ManagedNotice'
import { MetaPill } from '@/components/data/MetaPill'
import { StatusBadge } from '@/components/data/StatusBadge'
import { GiveFeedbackDialog } from '@/components/feedback/GiveFeedbackDialog'
import { Container } from '@/components/layout/Container'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Form } from '@/components/ui/form'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { statusLabel, VersionHistory } from '@/components/version'
import { EntityDeleteButton, EntityDuplicateButton, EntityExportButton } from '@/components/entity'
import { notify } from '@/lib/feedback'

import { PersonaModesPanel } from '../components/PersonaModesPanel'
import { PersonaPlaybooksCard } from '../components/PersonaPlaybooksCard'
import { PersonaProfileFields } from '../components/PersonaProfileFields'
import { usePersona } from '../hooks/usePersona'
import { usePersonaForm } from '../hooks/usePersonaForm'

export function PersonaDetailPage() {
  const { t } = useTranslation(['personas', 'common', 'playbooks', 'version'])
  const { id } = useParams<{ id: string }>()
  const { persona, versions, loading, error, reload } = usePersona(id)
  const { form, autoSave } = usePersonaForm(persona, reload)
  const wsPath = useWorkspacePath()
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const [actionBusy, setActionBusy] = useState(false)
  // Kontrollierte Tabs — der Modi-Info-Pill im „Bearbeiten"-Tab wechselt
  // programmatisch in den „Modi"-Tab.
  const [tab, setTab] = useState('edit')
  // Vom System verwaltet (Builder): Editor read-only, keine Status-/Lösch-
  // Aktionen. Das Backend sperrt Mutationen ohnehin (403 managed_aggregate).
  const locked = persona?.is_managed === true

  if (id === undefined) {
    return <Navigate to={wsPath('/personas')} replace />
  }

  const runTransition = async (
    version: number,
    to: VersionStatus,
    successMessage: string,
  ) => {
    if (persona === null) {
      return
    }
    setActionBusy(true)
    try {
      // Vor jeder Branch-Aktion erst den Auto-Save flushen — sonst wuerden
      // pending Edits verworfen, wenn der Server-Reload den Draft frisch
      // liefert.
      await autoSave.flush()
      await api.transitionPersonaVersion(persona.id, version, to)
      notify.success(successMessage)
      reload()
    } catch (cause) {
      notify.error(cause instanceof Error ? cause.message : t('detail.toast.actionFailed'))
    } finally {
      setActionBusy(false)
    }
  }

  return (
    <Container>
      <DataView loading={loading && persona === null} error={error}>
        {persona !== null ? (
          (() => {
            const activeVersion = versions.find((v) => v.status === 'active')
            const draftVersion = versions.find((v) => v.status === 'draft')
            const reviewVersion = versions.find((v) => v.status === 'review')
            const inactiveCurrent =
              activeVersion === undefined
                ? versions.find(
                    (v) =>
                      v.version === persona.current_version && v.status === 'inactive',
                  )
                : undefined

            const description =
              activeVersion !== undefined
                ? `${t('detail.description.active', { version: activeVersion.version })}${
                    draftVersion !== undefined
                      ? t('detail.description.activeDraft', { version: draftVersion.version })
                      : reviewVersion !== undefined
                        ? t('detail.description.activeReview', { version: reviewVersion.version })
                        : ''
                  }`
                : t('detail.description.currentVersion', {
                    version: persona.current_version,
                    status: statusLabel(persona.current_status ?? 'draft'),
                  })

            const canPromote = role === 'admin'
            // `locked` (vom System verwaltet) → keine Status-Aktionen.
            const actions: BranchAction[] = []
            if (!locked && draftVersion !== undefined) {
              actions.push({
                key: 'submit',
                label: t('detail.branch.submit'),
                variant: 'brand',
                disabled: actionBusy,
                onClick: () =>
                  void runTransition(draftVersion.version, 'review', t('detail.toast.submitted')),
              })
            }
            if (!locked && reviewVersion !== undefined) {
              actions.push({
                key: 'publish',
                label: t('detail.branch.publish'),
                variant: 'brand',
                disabled: actionBusy || !canPromote,
                title: canPromote ? undefined : t('statusBar.adminOnly'),
                onClick: () =>
                  void runTransition(reviewVersion.version, 'active', t('detail.toast.activated')),
              })
              actions.push({
                key: 'reject',
                label: t('detail.branch.reject'),
                variant: 'destructive',
                disabled: actionBusy,
                onClick: () =>
                  void runTransition(reviewVersion.version, 'draft', t('detail.toast.rejected')),
              })
            }
            if (!locked && inactiveCurrent !== undefined) {
              actions.push({
                key: 'reactivate',
                label: t('detail.branch.reactivate'),
                variant: 'outline',
                disabled: actionBusy,
                onClick: () =>
                  void runTransition(
                    inactiveCurrent.version,
                    'draft',
                    t('detail.toast.reactivated'),
                  ),
              })
            }

            const tags = persona.content.tags ?? []

            return (
              <Stack gap="lg">
                <DetailHeader
                  icon={Users}
                  iconTone="persona"
                  backHref={wsPath('/personas')}
                  backLabel={t('detail.back')}
                  title={persona.name}
                  badges={
                    <>
                      <Badge variant="secondary">v{persona.current_version}</Badge>
                      <LocaleBadge locale={persona.locale} />
                      <StatusBadge
                        status={persona.current_status}
                        pendingDraft={persona.has_pending_draft}
                      />
                      {tags.map((tag) => (
                        <MetaPill key={tag} tone="persona">
                          {tag}
                        </MetaPill>
                      ))}
                    </>
                  }
                  description={persona.content.description}
                  actions={
                    <>
                      {role === 'admin' || role === 'editor' ? (
                        <GiveFeedbackDialog
                          entityType="persona"
                          entityId={persona.id}
                          entityName={persona.name}
                          version={persona.current_version}
                        />
                      ) : null}
                      <EntityDuplicateButton
                        texts={{
                          success: t('duplicate.success'),
                          error: t('duplicate.error'),
                          viewerReadOnly: t('duplicate.viewerReadOnly'),
                        }}
                        label={t('duplicate.label')}
                        onDuplicate={() => api.duplicatePersona(persona.id)}
                        detailPath={(newId) => wsPath(`/personas/${newId}`)}
                        testId="duplicate-persona"
                      />
                      <EntityExportButton
                        entityKind="persona"
                        name={persona.name || persona.id}
                        onExport={(format) => api.exportPersona(persona.id, format)}
                        testIdPrefix="export-persona"
                      />
                    </>
                  }
                />

                {locked ? <ManagedNotice /> : null}

                {/* Status-Handlungsbedarf als Brand-Callout (ersetzt die alte
                    BranchStatus-Leiste, Design-Handoff „Persona-Detail"). */}
                {actions.length > 0 ? (
                  <AttentionBanner
                    variant="brand"
                    icon={Clock}
                    title={description}
                    actions={actions.map((action) => (
                      <Button
                        key={action.key}
                        type="button"
                        variant={action.variant}
                        onClick={action.onClick}
                        disabled={action.disabled}
                        title={action.title}
                      >
                        {action.label}
                      </Button>
                    ))}
                  />
                ) : null}

                {/* Ein gemeinsamer Form-Provider ueber alle Tabs: die Profil-
                    Felder („Bearbeiten") und der Modi-Editor („Modi") binden an
                    dieselbe react-hook-form-Instanz und teilen einen Auto-Save.
                    react-hook-form haelt den State zentral, auch wenn Radix den
                    inaktiven Tab-Inhalt unmountet. */}
                <Form {...form}>
                  <Tabs value={tab} onValueChange={setTab}>
                    <TabsList>
                      <TabsTrigger value="edit">
                        <SquarePen aria-hidden="true" />
                        {t('common:actions.edit')}
                      </TabsTrigger>
                      <TabsTrigger value="modes">
                        <Layers aria-hidden="true" />
                        {t('personas:detail.tabs.modes')}
                      </TabsTrigger>
                      <TabsTrigger value="playbooks">
                        <Share2 aria-hidden="true" />
                        {t('playbooks:list.title')}
                      </TabsTrigger>
                      <TabsTrigger value="versions">
                        <History aria-hidden="true" />
                        {t('version:history.title')}
                      </TabsTrigger>
                    </TabsList>

                    <TabsContent value="edit">
                      <Stack gap="sm">
                        <div className="flex justify-end">
                          <SaveIndicator state={autoSave} />
                        </div>
                        <Card>
                          <CardContent className="pt-6">
                            <PersonaProfileFields
                              form={form}
                              formKey={`${persona.id}-${persona.current_version}`}
                              initialProfileBlocks={persona.content.content?.blocks ?? []}
                              personaId={persona.id}
                              legacySystemPrompt={persona.content.system_prompt}
                              locked={locked}
                              onJumpToModes={() => setTab('modes')}
                            />
                          </CardContent>
                        </Card>
                      </Stack>
                    </TabsContent>

                    <TabsContent value="modes">
                      <Stack gap="sm">
                        <div className="flex justify-end">
                          <SaveIndicator state={autoSave} />
                        </div>
                        <PersonaModesPanel form={form} locked={locked} />
                      </Stack>
                    </TabsContent>

                    <TabsContent value="playbooks">
                      {/* WP-E: Anzeige-Modus default; der Checkbox-Picker liegt im
                          Bearbeiten-Modus der Karte. Viewer + managed nur Anzeige. */}
                      <PersonaPlaybooksCard
                        personaId={persona.id}
                        canEdit={role !== 'viewer' && !locked}
                      />
                    </TabsContent>

                    <TabsContent value="versions">
                      <Stack gap="lg">
                        <VersionHistory
                          versions={versions}
                          canEdit={role === 'admin' || role === 'editor'}
                          onRestore={async (version) => {
                            await autoSave.flush()
                            await api.restorePersonaVersion(persona.id, version)
                            notify.success(t('detail.toast.restored', { version }))
                            reload()
                          }}
                          loadDiff={(version) => api.diffPersonaVersion(persona.id, version)}
                          loadProvenance={(version) =>
                            api.provenancePersonaVersion(persona.id, version)
                          }
                        />

                        {role !== 'viewer' && !locked ? (
                          <Card className="border-destructive/40">
                            <CardHeader>
                              <CardTitle className="text-destructive">
                                {t('delete.dangerZoneTitle')}
                              </CardTitle>
                            </CardHeader>
                            <CardContent>
                              <Stack gap="sm">
                                <p className="text-sm text-muted-foreground">
                                  {t('delete.dangerZoneDescription')}
                                </p>
                                <div>
                                  <EntityDeleteButton
                                    name={persona.name}
                                    texts={{
                                      dialogTitle: t('delete.dialogTitle'),
                                      success: t('delete.success'),
                                      viewerReadOnly: t('delete.viewerReadOnly'),
                                      blockedMessage: t('delete.blockedMessage'),
                                    }}
                                    onDelete={() => api.deletePersona(persona.id)}
                                    listPath={wsPath('/personas')}
                                    testIdPrefix="delete-persona"
                                  />
                                </div>
                              </Stack>
                            </CardContent>
                          </Card>
                        ) : null}
                      </Stack>
                    </TabsContent>
                  </Tabs>
                </Form>
              </Stack>
            )
          })()
        ) : null}
      </DataView>
    </Container>
  )
}
