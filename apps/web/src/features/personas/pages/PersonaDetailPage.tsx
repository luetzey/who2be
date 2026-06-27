import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { VersionStatus } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { BranchStatus, type BranchAction } from '@/components/data/BranchStatus'
import { DataView } from '@/components/data/DataView'
import { FeedbackPanel } from '@/components/feedback/FeedbackPanel'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { VersionHistory } from '@/components/version'
import { usePersonaPlaybooks } from '@/hooks/usePersonaPlaybooks'
import { notify } from '@/lib/feedback'

import { DeletePersonaButton } from '../components/DeletePersonaButton'
import { ExportPersonaButton } from '../components/ExportPersonaButton'
import { PersonaEditorForm } from '../components/PersonaEditorForm'
import { SkillsComingSoon } from '../components/SkillsComingSoon'
import { PlaybookLinkItem } from '../components/PlaybookLinkItem'
import { usePersona } from '../hooks/usePersona'
import { usePersonaForm } from '../hooks/usePersonaForm'
import { statusLabel } from '../lib/status'

export function PersonaDetailPage() {
  const { t } = useTranslation('personas')
  const { id } = useParams<{ id: string }>()
  const { persona, versions, loading, error, reload } = usePersona(id)
  const { form, autoSave } = usePersonaForm(persona, reload)
  const links = usePersonaPlaybooks(id)
  const wsPath = useWorkspacePath()
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const [actionBusy, setActionBusy] = useState(false)

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
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/personas')}>
            <ArrowLeft className="h-4 w-4" />
            {t('detail.back')}
          </Link>
        </Button>

        <DataView loading={loading && persona === null} error={error}>
          {persona !== null ? (
            <Stack gap="lg">
              {(() => {
                const activeVersion = versions.find((v) => v.status === 'active')
                const draftVersion = versions.find((v) => v.status === 'draft')
                const reviewVersion = versions.find((v) => v.status === 'review')
                const inactiveCurrent =
                  activeVersion === undefined
                    ? versions.find(
                        (v) =>
                          v.version === persona.current_version &&
                          v.status === 'inactive',
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
                const actions: BranchAction[] = []
                if (draftVersion !== undefined) {
                  actions.push({
                    key: 'submit',
                    label: t('detail.branch.submit'),
                    variant: 'brand',
                    disabled: actionBusy,
                    onClick: () =>
                      void runTransition(
                        draftVersion.version,
                        'review',
                        t('detail.toast.submitted'),
                      ),
                  })
                }
                if (reviewVersion !== undefined) {
                  actions.push({
                    key: 'publish',
                    label: t('detail.branch.publish'),
                    variant: 'brand',
                    disabled: actionBusy || !canPromote,
                    title: canPromote ? undefined : t('statusBar.adminOnly'),
                    onClick: () =>
                      void runTransition(
                        reviewVersion.version,
                        'active',
                        t('detail.toast.activated'),
                      ),
                  })
                  actions.push({
                    key: 'reject',
                    label: t('detail.branch.reject'),
                    variant: 'destructive',
                    disabled: actionBusy,
                    onClick: () =>
                      void runTransition(
                        reviewVersion.version,
                        'draft',
                        t('detail.toast.rejected'),
                      ),
                  })
                }
                if (inactiveCurrent !== undefined) {
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

                return (
                  <Stack gap="md">
                    <PageHeader
                      title={persona.name}
                      description={description}
                      actions={<ExportPersonaButton persona={persona} />}
                    />
                    <BranchStatus
                      activeVersion={activeVersion?.version}
                      draftVersion={draftVersion?.version}
                      reviewVersion={reviewVersion?.version}
                      inactiveVersion={inactiveCurrent?.version}
                      currentVersion={persona.current_version}
                      saveState={autoSave}
                      actions={actions}
                    />
                  </Stack>
                )
              })()}
              <PersonaEditorForm
                form={form}
                formKey={`${persona.id}-${persona.current_version}`}
                initialProfileBlocks={persona.content.content?.blocks ?? []}
                personaId={persona.id}
                legacySystemPrompt={persona.content.system_prompt}
              />

              <SkillsComingSoon compact />

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

              {role !== 'viewer' ? (
                <FeedbackPanel
                  type="persona"
                  id={persona.id}
                  onRevise={() => {
                    window.scrollTo({ top: 0, behavior: 'smooth' })
                    notify.info(t('feedback:panel.reviseToast'))
                  }}
                />
              ) : null}

              <Card>
                <CardHeader>
                  <CardTitle>{t('detail.playbooks.title')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <Stack gap="sm">
                    <DataView
                      loading={links.loading}
                      error={links.error}
                      empty={!links.loading && links.playbooks.length === 0}
                      emptyTitle={t('detail.playbooks.empty')}
                    >
                      <ul className="flex flex-col gap-2">
                        {links.playbooks.map((playbook) => (
                          <PlaybookLinkItem
                            key={playbook.id}
                            id={playbook.id}
                            name={playbook.name}
                            checked={links.linkedIds.includes(playbook.id)}
                            onToggle={() => links.toggle(playbook.id)}
                          />
                        ))}
                      </ul>
                    </DataView>
                    <div className="flex justify-end">
                      <Button
                        type="button"
                        onClick={() => void links.save()}
                        disabled={links.saving || links.loading}
                      >
                        {t('detail.playbooks.save')}
                      </Button>
                    </div>
                  </Stack>
                </CardContent>
              </Card>

              {role !== 'viewer' ? (
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
                        <DeletePersonaButton persona={persona} />
                      </div>
                    </Stack>
                  </CardContent>
                </Card>
              ) : null}
            </Stack>
          ) : null}
        </DataView>
      </Stack>
    </Container>
  )
}
