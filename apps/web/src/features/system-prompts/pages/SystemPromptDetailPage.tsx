import { ClipboardCheck, Clock, GitBranch, ScrollText, SquarePen } from 'lucide-react'
import { Navigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { AttentionBanner } from '@/components/data/AttentionBanner'
import { DataView } from '@/components/data/DataView'
import { DetailHeader } from '@/components/data/DetailHeader'
import { LocaleBadge } from '@/components/data/LocaleBadge'
import { ManagedNotice } from '@/components/data/ManagedNotice'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Container } from '@/components/layout/Container'
import { EntityTestCases, TESTS_TAB } from '@/components/testcases/TestCasesTab'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { VersionHistory } from '@/components/version'
import { useVersionDeepLink } from '@/components/version/versionDeepLink'
import { EntityDuplicateButton } from '@/components/entity'
import { notify } from '@/lib/feedback'

import { SystemPromptEditorForm } from '../components/SystemPromptEditorForm'
import { SystemPromptStatusActionBar } from '../components/SystemPromptStatusActionBar'
import { useSystemPrompt } from '../hooks/useSystemPrompt'
import { useSystemPromptForm } from '../hooks/useSystemPromptForm'

// Tabs der Detailseite — Whitelist fuer den Deep-Link `?tab=` (Audit E1 = A).
const SYSTEM_PROMPT_TABS = ['edit', 'versions', TESTS_TAB] as const

export function SystemPromptDetailPage() {
  const { t } = useTranslation('systemPrompts')
  const { id } = useParams<{ id: string }>()
  const wsPath = useWorkspacePath()
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const { template, versions, loading, error, reload } = useSystemPrompt(id)
  const { form, onSubmit, saveError } = useSystemPromptForm(template, reload)
  const { tab, setTab, diffVersion } = useVersionDeepLink(SYSTEM_PROMPT_TABS, 'edit')
  // Vom System verwaltet (Builder-Template): Editor read-only, keine Status-
  // Aktionen (Backend sperrt mit 403 managed_aggregate).
  const locked = template?.is_managed === true
  // UUID der Review-Version fuer den Pruefbericht (Spec S11) — die Leiste
  // aktiviert immer `current_version`.
  const reviewVersionId = versions.find(
    (v) => v.version === template?.current_version && v.status === 'review',
  )?.id

  if (id === undefined) {
    return <Navigate to={wsPath('/system-prompts')} replace />
  }

  return (
    <Container>
      <DataView loading={loading && template === null} error={error}>
        {template !== null ? (
          <div className="flex flex-col gap-6">
            <DetailHeader
              icon={ScrollText}
              iconTone="tools"
              title={template.name}
              backHref={wsPath('/system-prompts')}
              backLabel={t('nav.backToList')}
              badges={
                <>
                  {/* #566: siehe SystemPromptsPage — derselbe Slug, zweite
                      Fundstelle. Gemessen bei 320px: 497px ohne Cap. */}
                  <Badge variant="outline" className="max-w-full font-mono break-all">
                    {template.slug}
                  </Badge>
                  <StatusBadge
                    status={template.current_status}
                    pendingDraft={template.has_pending_draft}
                  />
                  <Badge variant="secondary">v{template.current_version}</Badge>
                  <LocaleBadge locale={template.locale} />
                </>
              }
              description={template.content.description}
              actions={
                <EntityDuplicateButton
                  texts={{
                    success: t('duplicate.success'),
                    error: t('duplicate.error'),
                    viewerReadOnly: t('duplicate.viewerReadOnly'),
                  }}
                  label={t('duplicate.label')}
                  onDuplicate={() => api.duplicateSystemPrompt(template.id)}
                  detailPath={(newId) => wsPath(`/system-prompts/${newId}`)}
                  testId="duplicate-system-prompt"
                />
              }
            />

            {/* Managed-Lock, Review-Banner oder schlichte Status-Aktionsleiste —
                dieselbe Transition-Logik wie zuvor, nur neu eingekleidet. */}
            {locked ? (
              <ManagedNotice />
            ) : template.current_status === 'review' ? (
              <AttentionBanner
                variant="brand"
                icon={Clock}
                title={t('page.detail.bannerReviewTitle', {
                  version: template.current_version,
                })}
                description={t('reviewNotice')}
                actions={
                  <SystemPromptStatusActionBar
                    templateId={template.id}
                    version={template.current_version}
                    status={template.current_status}
                    onTransitioned={reload}
                    diffVersion={template.current_version}
                    testReportEntityType="system_prompt_template"
                    versionId={reviewVersionId}
                  />
                }
              />
            ) : template.current_status !== undefined ? (
              <SystemPromptStatusActionBar
                templateId={template.id}
                version={template.current_version}
                status={template.current_status}
                onTransitioned={reload}
              />
            ) : null}

            <Tabs value={tab} onValueChange={setTab}>
              <TabsList aria-label={t('common:tabs.detailViewAria')}>
                <TabsTrigger value="edit">
                  <SquarePen aria-hidden="true" />
                  {t('common:actions.edit')}
                </TabsTrigger>
                {/* Lernschleife B4b (Spec S10): ohne Zaehler (§2.3). */}
                <TabsTrigger value={TESTS_TAB}>
                  <ClipboardCheck aria-hidden="true" />
                  {t('learning:testCases.title')}
                </TabsTrigger>
                <TabsTrigger value="versions">
                  <GitBranch aria-hidden="true" />
                  {t('version:history.title')}
                </TabsTrigger>
              </TabsList>

              <TabsContent value="edit">
                <SystemPromptEditorForm
                  form={form}
                  onSubmit={onSubmit}
                  saveError={saveError}
                  locked={locked}
                />
              </TabsContent>

              <TabsContent value="versions">
                <VersionHistory
                  versions={versions}
                  canEdit={role === 'admin' || role === 'editor'}
                  onRestore={async (version) => {
                    await api.restoreSystemPromptTemplateVersion(template.id, version)
                    notify.success(t('page.detail.toast.restored', { version }))
                    reload()
                  }}
                  loadDiff={(version) => api.diffSystemPromptTemplateVersion(template.id, version)}
                  loadProvenance={(version) =>
                    api.provenanceSystemPromptTemplateVersion(template.id, version)
                  }
                  // Spec S11: Review-Version beim Oeffnen des Tabs aufgeklappt.
                  initialDiffVersion={
                    diffVersion ??
                    (template.current_status === 'review' ? template.current_version : undefined)
                  }
                  testReportEntityType="system_prompt_template"
                  testCasesSearch={`?tab=${TESTS_TAB}`}
                />
              </TabsContent>

              <TabsContent value={TESTS_TAB}>
                <EntityTestCases
                  type="system_prompt_template"
                  id={template.id}
                  name={template.name}
                />
              </TabsContent>
            </Tabs>
          </div>
        ) : null}
      </DataView>
    </Container>
  )
}
