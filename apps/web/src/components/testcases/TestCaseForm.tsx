import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type {
  Agent,
  TestCaseCreateInput,
  TestCaseRead,
  TestCheckKind,
  VersionedEntityType,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { notify } from '@/lib/feedback'

// Laengen-Deckel aus `who2be_models.test_case` (CHECKs der Migration 0089).
// Clientseitig nur als Vorab-Hinweis; die Quelle der Wahrheit ist der Server.
const TEST_CASE_LIMITS = { title: 200, input: 8_000, expected: 2_000 } as const

const CHECK_KINDS: readonly TestCheckKind[] = [
  'human_rule',
  'must_contain',
  'must_not_contain',
]

interface TestCaseFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Fester Agent (Aufrufort Agent-Detail). Ohne: Auswahl aus `agents`. */
  agentId?: string
  /** Waehlbare Agenten, wenn `agentId` fehlt (Aufrufort Element-Detail). */
  agents?: readonly Agent[]
  /** Fester Element-Bezug, vorbelegt vom Aufrufort (Element-Detail). */
  entity?: { type: VersionedEntityType; id: string }
  /**
   * Gesetzt = "Neue Fassung anlegen": Felder vorbelegt, Anlage mit
   * `supersedes_id` (der Server archiviert den alten in derselben
   * Transaktion). Bezug (Agent/Element) uebernimmt die neue Fassung.
   */
  supersedes?: TestCaseRead | null
  onSaved: (created: TestCaseRead) => void
}

interface Values {
  agentId: string
  title: string
  input: string
  expected: string
  checkKind: TestCheckKind
  pattern: string
}

type Errors = Partial<Record<keyof Values, string>>

function initialValues(props: TestCaseFormProps): Values {
  const base = props.supersedes
  return {
    agentId: base?.agent_id ?? props.agentId ?? '',
    title: base?.title ?? '',
    input: base?.input ?? '',
    expected: base?.expected_behavior ?? '',
    checkKind: base?.check_kind ?? 'human_rule',
    pattern: base?.check_pattern ?? '',
  }
}

/**
 * Formular "Prüffall anlegen" bzw. "Neue Fassung anlegen" (Spec S10, B4).
 * Dialog ab `sm`, auf schmalen Viewports Vollbild (gleiche Radix-Dialog-
 * Semantik: Fokusfalle, Escape, Fokus zurueck zum Ausloeser).
 *
 * Der Prueffall-Inhalt ist unveraenderlich (ADR-0053 3.2): es gibt kein
 * Bearbeiten, nur eine neue Fassung mit `supersedes_id`.
 */
export function TestCaseForm(props: TestCaseFormProps) {
  const { open, onOpenChange, supersedes } = props
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        // Unter `sm` Vollbild-Sheet (Spec S10): volle Hoehe/Breite, keine
        // Rundung; ab `sm` der normale zentrierte Dialog.
        className="h-[100dvh] max-h-[100dvh] w-screen max-w-none rounded-none sm:h-auto sm:max-h-[calc(100vh-2rem)] sm:w-[calc(100vw-2rem)] sm:max-w-xl sm:rounded-lg"
        data-testid="test-case-form"
      >
        {/* Radix entmountet den Inhalt beim Schliessen; `key` sorgt zusaetzlich
            dafuer, dass jede neue Fassung frisch vorbelegt startet. */}
        <TestCaseFormBody key={supersedes?.id ?? 'new'} {...props} />
      </DialogContent>
    </Dialog>
  )
}

function TestCaseFormBody(props: TestCaseFormProps) {
  const { onOpenChange, agentId, agents, entity, supersedes, onSaved } = props
  const { t } = useTranslation('learning')
  const api = useApi()
  const formId = useId()
  const [values, setValues] = useState<Values>(() => initialValues(props))
  const [errors, setErrors] = useState<Errors>({})
  const [busy, setBusy] = useState(false)

  const set = <K extends keyof Values>(key: K, value: Values[K]) => {
    setValues((prev) => ({ ...prev, [key]: value }))
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  const needsPattern = values.checkKind !== 'human_rule'
  const fixedAgent = agentId !== undefined || supersedes != null

  const validate = (): Errors => {
    const next: Errors = {}
    const required = t('testCases.form.validation.required')
    const tooLong = (max: number) => t('testCases.form.validation.tooLong', { max })
    if (values.agentId === '') next.agentId = t('testCases.form.validation.agentRequired')
    if (values.title.trim() === '') next.title = required
    else if (values.title.trim().length > TEST_CASE_LIMITS.title)
      next.title = tooLong(TEST_CASE_LIMITS.title)
    if (values.input.trim() === '') next.input = required
    else if (values.input.trim().length > TEST_CASE_LIMITS.input)
      next.input = tooLong(TEST_CASE_LIMITS.input)
    if (values.expected.trim() === '') next.expected = required
    else if (values.expected.trim().length > TEST_CASE_LIMITS.expected)
      next.expected = tooLong(TEST_CASE_LIMITS.expected)
    if (needsPattern && values.pattern.trim() === '') next.pattern = required
    return next
  }

  const onSubmit = async () => {
    const found = validate()
    if (Object.values(found).some(Boolean)) {
      setErrors(found)
      return
    }
    const target = supersedes
      ? supersedes.entity_type !== null && supersedes.entity_id !== null
        ? { type: supersedes.entity_type, id: supersedes.entity_id }
        : undefined
      : entity
    const payload: TestCaseCreateInput = {
      agent_id: values.agentId,
      entity_type: target?.type ?? null,
      entity_id: target?.id ?? null,
      title: values.title.trim(),
      input: values.input.trim(),
      expected_behavior: values.expected.trim(),
      check_kind: values.checkKind,
      check_pattern: needsPattern ? values.pattern.trim() : null,
      origin_case_id: supersedes?.origin_case_id ?? null,
      origin_measure_id: supersedes?.origin_measure_id ?? null,
      supersedes_id: supersedes?.id ?? null,
    }
    setBusy(true)
    try {
      const created = await api.createTestCase(payload)
      notify.success(
        supersedes ? t('testCases.form.toast.superseded') : t('testCases.form.toast.created'),
      )
      onOpenChange(false)
      onSaved(created)
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('testCases.form.toast.error'))
    } finally {
      setBusy(false)
    }
  }

  const field = (key: keyof Values) => ({
    id: `${formId}-${key}`,
    'aria-invalid': errors[key] ? true : undefined,
    'aria-describedby': `${formId}-${key}-help${errors[key] ? ` ${formId}-${key}-error` : ''}`,
  })

  const help = (key: keyof Values, text: string) => (
    <>
      <p id={`${formId}-${key}-help`} className="text-xs text-muted-foreground">
        {text}
      </p>
      {errors[key] ? (
        <p id={`${formId}-${key}-error`} className="text-xs text-destructive">
          {errors[key]}
        </p>
      ) : null}
    </>
  )

  return (
    <>
        <DialogHeader>
          <DialogTitle>
            {supersedes ? t('testCases.form.titleSupersede') : t('testCases.form.titleCreate')}
          </DialogTitle>
          <DialogDescription>
            {supersedes
              ? t('testCases.form.descriptionSupersede', { title: supersedes.title })
              : t('testCases.form.description')}
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex min-w-0 flex-col gap-4"
          noValidate
          onSubmit={(event) => {
            event.preventDefault()
            void onSubmit()
          }}
        >
          {!fixedAgent ? (
            <div className="flex flex-col gap-1">
              <Label htmlFor={`${formId}-agentId`}>{t('testCases.form.fields.agent')}</Label>
              <Select
                {...field('agentId')}
                value={values.agentId}
                onChange={(event) => set('agentId', event.target.value)}
              >
                <option value="">{t('testCases.form.fields.agentPlaceholder')}</option>
                {(agents ?? []).map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </Select>
              {help('agentId', t('testCases.form.help.agent'))}
            </div>
          ) : null}

          <div className="flex flex-col gap-1">
            <Label htmlFor={`${formId}-title`}>{t('testCases.form.fields.title')}</Label>
            <Input
              {...field('title')}
              value={values.title}
              maxLength={TEST_CASE_LIMITS.title}
              onChange={(event) => set('title', event.target.value)}
            />
            {help('title', t('testCases.form.help.title'))}
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor={`${formId}-input`}>{t('testCases.form.fields.input')}</Label>
            <Textarea
              {...field('input')}
              rows={4}
              value={values.input}
              maxLength={TEST_CASE_LIMITS.input}
              onChange={(event) => set('input', event.target.value)}
            />
            {help('input', t('testCases.form.help.input'))}
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor={`${formId}-expected`}>{t('testCases.form.fields.expected')}</Label>
            <Textarea
              {...field('expected')}
              rows={3}
              value={values.expected}
              maxLength={TEST_CASE_LIMITS.expected}
              onChange={(event) => set('expected', event.target.value)}
            />
            {help('expected', t('testCases.form.help.expected'))}
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor={`${formId}-checkKind`}>{t('testCases.form.fields.checkKind')}</Label>
            <Select
              {...field('checkKind')}
              value={values.checkKind}
              onChange={(event) => set('checkKind', event.target.value as TestCheckKind)}
            >
              {CHECK_KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {t(`testCases.checkKind.${kind}`)}
                </option>
              ))}
            </Select>
            {help('checkKind', t('testCases.form.help.checkKind'))}
          </div>

          {needsPattern ? (
            <div className="flex flex-col gap-1">
              <Label htmlFor={`${formId}-pattern`}>{t('testCases.form.fields.pattern')}</Label>
              <Input
                {...field('pattern')}
                value={values.pattern}
                onChange={(event) => set('pattern', event.target.value)}
              />
              {help('pattern', t('testCases.form.help.pattern'))}
            </div>
          ) : null}

          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={busy}>
                {t('common:actions.cancel')}
              </Button>
            </DialogClose>
            <Button type="submit" variant="brand" disabled={busy} aria-busy={busy || undefined}>
              {supersedes ? t('testCases.form.submitSupersede') : t('testCases.form.submitCreate')}
            </Button>
          </DialogFooter>
        </form>
    </>
  )
}
