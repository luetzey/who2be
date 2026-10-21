import Markdown, { type MarkdownToJSX } from 'markdown-to-jsx'
import { ArrowLeft, BookOpen, Check, Copy, GraduationCap, Search } from 'lucide-react'
import { type ReactNode, useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  listTutorials,
  patchTutorial,
  restartTutorial,
  type Tutorial,
  type TutorialStep,
  type TutorialStepState,
} from '@/api/client'
import { useAuthToken } from '@/auth/useAuthToken'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspaceId } from '@/auth/useWorkspaceId'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
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
import {
  findPage,
  findTutorial,
  HELP_SECTIONS,
  type HelpBlock,
  type HelpEntry,
  type HelpIndex,
  helpIndex as defaultIndex,
  type HelpPage,
  type HelpSection,
  type HelpTutorial,
  safeHelpHref,
  SEARCH_MIN_LENGTH,
  searchHelp,
  toHelpLocale,
} from '@/help/helpIndex'
import { copyToClipboard } from '@/lib/clipboard'
import { formatDate } from '@/lib/dates'
import { notify } from '@/lib/feedback'
import { useListData } from '@/hooks/useListData'
import i18n from '@/i18n'

/*
 * Hilfe-Bereich (Onboarding P4): Startseite mit Tutorials, Suche und
 * Nachschlagen, Artikelseite, Tutorial-Seite. Inhalte kommen aus
 * `@/help/helpIndex` (Markdown-Dateien), Tutorial-Schritte und Fortschritt
 * nur vom Server (`useTutorials`). IDs aus der URL werden ausschliesslich
 * gegen diese beiden Quellen aufgeloest.
 */

const LINK = 'font-medium text-brand underline-offset-4 hover:underline'
// Kartentitel unter einer h2-Abschnittsüberschrift: echte h3 mit dem Aussehen von CardTitle
// (CardTitle rendert h2, card.tsx).
const CARD_HEADING = 'text-lg leading-none font-semibold tracking-tight'

// --- Tutorials am Konto (Daten) -------------------------------------------------

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

interface TutorialsState {
  tutorials: Tutorial[]
  loading: boolean
  error: string | null
  reload: () => void
  /** ID des Tutorials bzw. Schritts, dessen Aenderung gerade laeuft. */
  pending: string | null
  restart: (tutorialId: string) => Promise<Tutorial | null>
  setStep: (tutorialId: string, stepId: string, state: TutorialStepState) => Promise<void>
}

/**
 * Tutorials des Kontos mit Fortschritt (`GET /v1/me/tutorials`, ADR-0060).
 *
 * Eine Quelle pro Ansicht: Schritte, Typen und Zustaende kommen nur vom
 * Server; Antworten auf Aenderungen ersetzen das Tutorial in der Liste. Eine
 * laufende Aenderung sperrt weitere (`pending`), damit kein Doppel-Submit
 * entsteht.
 */
function useTutorials(): TutorialsState {
  const token = useAuthToken()
  const workspaceId = useWorkspaceId()
  const loader = useCallback(() => listTutorials(token, workspaceId), [token, workspaceId])
  const list = useListData<Tutorial>(loader)
  // Antworten auf Aenderungen ueberdecken den geladenen Stand, bis neu geladen
  // wird — gebunden an den Workspace, dessen Signale sie enthalten.
  const [updated, setUpdated] = useState<{ workspaceId: string; items: Record<string, Tutorial> }>({
    workspaceId,
    items: {},
  })
  const [pending, setPending] = useState<string | null>(null)
  const busy = useRef(false)

  const tutorials = useMemo(() => {
    const items = updated.workspaceId === workspaceId ? updated.items : {}
    return list.data.map((item) => items[item.id] ?? item)
  }, [list.data, updated, workspaceId])
  const { reload: reloadList } = list
  const reload = useCallback(() => {
    setUpdated({ workspaceId, items: {} })
    reloadList()
  }, [reloadList, workspaceId])

  const replace = useCallback(
    (next: Tutorial) => {
      setUpdated((current) => ({
        workspaceId,
        items: { ...(current.workspaceId === workspaceId ? current.items : {}), [next.id]: next },
      }))
    },
    [workspaceId],
  )

  const run = useCallback(
    async (key: string, action: () => Promise<Tutorial>): Promise<Tutorial | null> => {
      if (busy.current) return null
      busy.current = true
      setPending(key)
      try {
        const next = await action()
        replace(next)
        return next
      } catch (cause) {
        notify.error(describeError(cause))
        return null
      } finally {
        busy.current = false
        setPending(null)
      }
    },
    [replace],
  )

  const restart = useCallback(
    (tutorialId: string) => run(tutorialId, () => restartTutorial(token, workspaceId, tutorialId)),
    [run, token, workspaceId],
  )

  const setStep = useCallback(
    async (tutorialId: string, stepId: string, state: TutorialStepState) => {
      await run(stepId, () =>
        patchTutorial(token, workspaceId, tutorialId, { step_id: stepId, state }),
      )
    },
    [run, token, workspaceId],
  )

  return { tutorials, loading: list.loading, error: list.error, reload, pending, restart, setStep }
}

/** Erledigte bzw. uebersprungene Schritte (alles, was nicht mehr offen ist). */
function finishedSteps(tutorial: Tutorial): number {
  return tutorial.steps.filter((step) => step.state !== 'open').length
}

/** Begonnen = ein Schritt ausser dem Startvorsprung ist nicht mehr offen. */
function isStarted(tutorial: Tutorial): boolean {
  return tutorial.steps.some((step) => step.type !== 'head_start' && step.state !== 'open')
}

// --- Markdown -----------------------------------------------------------------

function HelpLink({ href, children }: { href?: string; children?: ReactNode }) {
  const wsPath = useWorkspacePath()
  const safe = href === undefined ? null : safeHelpHref(href)
  if (safe === null) return <span>{children}</span>
  if (/^https?:\/\//i.test(safe)) {
    // RR7-`Link` rendert absolute URLs als normalen externen Link.
    return (
      <Link to={safe} reloadDocument target="_blank" rel="noopener noreferrer" className={LINK}>
        {children}
      </Link>
    )
  }
  if (safe.startsWith('#')) {
    return (
      <Link to={{ hash: safe }} className={LINK}>
        {children}
      </Link>
    )
  }
  // Interne Ziele sind workspace-relativ geschrieben (`/help/<slug>#<anker>`).
  return (
    <Link to={wsPath(safe)} className={LINK}>
      {children}
    </Link>
  )
}

function NoImage() {
  return null
}

const MARKDOWN_OPTIONS: MarkdownToJSX.Options = {
  // Raw-HTML aus: Tags bleiben Text, werden nie zu Elementen.
  disableParsingRawHTML: true,
  disableAutoLink: true,
  disableFrontmatter: true,
  enforceAtxHeadings: true,
  forceBlock: true,
  wrapper: null,
  sanitizer: (value, _tag, attribute) => (attribute === 'href' ? safeHelpHref(value) : null),
  overrides: {
    a: { component: HelpLink },
    // Im Dialekt verboten (Inhaltstest), hier zusaetzlich wirkungslos.
    img: { component: NoImage },
    p: { props: { className: 'leading-relaxed' } },
    ul: { props: { className: 'list-disc space-y-1 pl-6' } },
    ol: { props: { className: 'list-decimal space-y-1 pl-6' } },
    code: { props: { className: 'rounded bg-muted px-1 py-0.5 font-mono text-sm break-words' } },
    pre: {
      props: {
        className:
          'overflow-x-auto rounded-md border border-dashed bg-muted/40 p-3 font-mono text-sm whitespace-pre-wrap [&_code]:bg-transparent [&_code]:p-0',
      },
    },
    blockquote: { props: { className: 'border-l-2 pl-4 text-muted-foreground' } },
  },
}

/**
 * Markdown des Hilfe-Dialekts als React-Elemente (kein
 * `dangerouslySetInnerHTML`). Ueberschriften setzt der Aufrufer selbst.
 */
export function HelpMarkdown({ children }: { children: string }) {
  if (children.trim() === '') return null
  return (
    <div className="space-y-3 text-base">
      <Markdown options={MARKDOWN_OPTIONS}>{children}</Markdown>
    </div>
  )
}

function BlockHeading({ block }: { block: HelpBlock }) {
  const Tag = block.level === 2 ? 'h2' : 'h3'
  return (
    <Tag
      id={block.id}
      className={
        block.level === 2
          ? 'scroll-mt-20 text-xl font-semibold tracking-tight'
          : 'scroll-mt-20 text-lg font-semibold'
      }
    >
      {block.title}
    </Tag>
  )
}

// --- Gemeinsames --------------------------------------------------------------

function useHelpLocale() {
  const { i18n } = useTranslation()
  return toHelpLocale(i18n.resolvedLanguage ?? i18n.language)
}

function useSectionLabel(): (section: HelpSection) => string {
  const { t } = useTranslation('help')
  const labels: Record<HelpSection, string> = {
    'erste-schritte': t('sections.firstSteps'),
    bausteine: t('sections.buildingBlocks'),
    'agenten-verbessern': t('sections.improveAgents'),
    'konto-und-team': t('sections.accountAndTeam'),
  }
  return (section) => labels[section]
}

/** Seiten, die die aktuelle Rolle sehen darf (`audience: admin` nur fuer admin). */
function useVisiblePages(index: HelpIndex): HelpPage[] {
  const locale = useHelpLocale()
  const role = useCurrentWorkspaceRole()
  return index.pages.filter(
    (page) => page.locale === locale && (page.audience === 'all' || role === 'admin'),
  )
}

function BackToHelp() {
  const { t } = useTranslation('help')
  const wsPath = useWorkspacePath()
  return (
    <Button asChild variant="ghost" size="sm" className="self-start">
      <Link to={wsPath('/help')}>
        <ArrowLeft className="size-4" aria-hidden="true" />
        {t('nav.back')}
      </Link>
    </Button>
  )
}

function ProgressBar({ done, total, label }: { done: number; total: number; label: string }) {
  const percent = total > 0 ? Math.round((done / total) * 100) : 0
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
      <div
        className="h-full bg-primary transition-[width] duration-[var(--duration-base)] ease-standard"
        style={{ width: `${percent}%` }}
        role="progressbar"
        aria-valuenow={done}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-label={label}
      />
    </div>
  )
}

interface RestartDialogProps {
  open: boolean
  title: string
  busy: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}

function RestartDialog({ open, title, busy, onOpenChange, onConfirm }: RestartDialogProps) {
  const { t } = useTranslation('help')
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('tutorial.restart.title', { title })}</DialogTitle>
          <DialogDescription>{t('tutorial.restart.body')}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">{t('tutorial.restart.cancel')}</Button>
          </DialogClose>
          <Button onClick={onConfirm} disabled={busy}>
            {t('tutorial.restart.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --- Startseite -----------------------------------------------------------------

interface TutorialCardProps {
  tutorial: Tutorial
  text: HelpTutorial
  busy: boolean
  onRestart: () => void
}

function TutorialCard({ tutorial, text, busy, onRestart }: TutorialCardProps) {
  const { t } = useTranslation('help')
  const wsPath = useWorkspacePath()
  const done = finishedSteps(tutorial)
  const total = tutorial.steps.length
  const started = isStarted(tutorial)
  const to = wsPath(`/help/tutorials/${tutorial.id}`)
  return (
    <Card data-testid={`tutorial-card-${tutorial.id}`}>
      <CardHeader className="gap-1">
        <h3 className={CARD_HEADING}>{text.title}</h3>
        <p className="text-sm text-muted-foreground">{text.description}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          {tutorial.completed
            ? t('tutorial.progress.completed', { total })
            : t('tutorial.progress.label', { done, total, minutes: text.durationMinutes })}
        </p>
        <ProgressBar done={done} total={total} label={t('tutorial.progress.aria', { title: text.title })} />
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          {tutorial.completed ? (
            <Button variant="outline" onClick={onRestart} disabled={busy}>
              {t('tutorial.actions.restart')}
            </Button>
          ) : (
            <>
              <Button asChild>
                <Link to={to}>{started ? t('tutorial.actions.resume') : t('tutorial.actions.start')}</Link>
              </Button>
              {started ? (
                <Button variant="ghost" onClick={onRestart} disabled={busy}>
                  {t('tutorial.actions.restart')}
                </Button>
              ) : null}
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function TutorialsSection({ index }: { index: HelpIndex }) {
  const { t } = useTranslation('help')
  const locale = useHelpLocale()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const { tutorials, loading, error, reload, pending, restart } = useTutorials()
  const [confirm, setConfirm] = useState<{ id: string; title: string } | null>(null)

  // Nur Tutorials, fuer die es Text in dieser Sprache gibt (Paritaetstest
  // sichert das ab; ohne Text zeigt die Liste lieber nichts als eine ID).
  const items = tutorials.flatMap((tutorial) => {
    const text = findTutorial(index, locale, tutorial.id)
    return text === null ? [] : [{ tutorial, text }]
  })

  async function onConfirm() {
    if (confirm === null) return
    const result = await restart(confirm.id)
    if (result !== null) {
      setConfirm(null)
      notify.success(t('tutorial.restart.done'))
      void navigate(wsPath(`/help/tutorials/${result.id}`))
    }
  }

  return (
    <section aria-labelledby="help-tutorials-title" className="space-y-3">
      <h2 id="help-tutorials-title" className="text-xl font-semibold tracking-tight">
        {t('home.tutorials.title')}
      </h2>
      {loading ? (
        <LoadingState rows={2} />
      ) : error !== null ? (
        <div className="space-y-2">
          <ErrorAlert title={t('home.tutorials.error')} message={error} />
          <Button variant="outline" size="sm" onClick={reload}>
            {t('home.tutorials.retry')}
          </Button>
        </div>
      ) : items.length === 0 ? (
        <EmptyState icon={GraduationCap} title={t('home.tutorials.empty')} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map(({ tutorial, text }) => (
            <TutorialCard
              key={tutorial.id}
              tutorial={tutorial}
              text={text}
              busy={pending !== null}
              onRestart={() => setConfirm({ id: tutorial.id, title: text.title })}
            />
          ))}
        </div>
      )}
      <RestartDialog
        open={confirm !== null}
        title={confirm?.title ?? ''}
        busy={pending !== null}
        onOpenChange={(open) => {
          if (!open) setConfirm(null)
        }}
        onConfirm={() => void onConfirm()}
      />
    </section>
  )
}

function entryPath(entry: HelpEntry): string {
  return entry.kind === 'tutorial' ? `/help/tutorials/${entry.slug}` : `/help/${entry.slug}`
}

function SearchResults({ query, index }: { query: string; index: HelpIndex }) {
  const { t } = useTranslation('help')
  const locale = useHelpLocale()
  const wsPath = useWorkspacePath()
  const visible = new Set(useVisiblePages(index).map((page) => page.slug))
  const hits = searchHelp(index, locale, query).filter(
    (entry) => entry.kind === 'tutorial' || visible.has(entry.slug),
  )
  return (
    <section aria-labelledby="help-search-results" className="space-y-3">
      <h2 id="help-search-results" className="sr-only">
        {t('home.search.resultsTitle')}
      </h2>
      <p role="status" className="text-sm text-muted-foreground">
        {hits.length === 0
          ? t('home.search.none')
          : t('home.search.count', { count: hits.length, query: query.trim() })}
      </p>
      {hits.length > 0 ? (
        <ul className="divide-y rounded-lg border bg-card">
          {hits.map((entry) => (
            <li key={`${entry.kind}-${entry.slug}`} className="p-4">
              <Link to={wsPath(entryPath(entry))} className={LINK}>
                {entry.title}
              </Link>
              <p className="text-sm text-muted-foreground">{entry.description}</p>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}

function ReferenceSection({ index }: { index: HelpIndex }) {
  const { t } = useTranslation('help')
  const wsPath = useWorkspacePath()
  const sectionLabel = useSectionLabel()
  const pages = useVisiblePages(index)
  const groups = HELP_SECTIONS.map((section) => ({
    section,
    pages: pages.filter((page) => page.section === section),
  })).filter((group) => group.pages.length > 0)
  return (
    <section aria-labelledby="help-reference-title" className="space-y-3">
      <h2 id="help-reference-title" className="text-xl font-semibold tracking-tight">
        {t('home.reference.title')}
      </h2>
      {groups.length === 0 ? (
        <EmptyState icon={BookOpen} title={t('home.reference.empty')} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {groups.map((group) => (
            <Card key={group.section}>
              <CardHeader>
                <h3 className={CARD_HEADING}>{sectionLabel(group.section)}</h3>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {group.pages.map((page) => (
                    <li key={page.slug}>
                      <Link to={wsPath(`/help/${page.slug}`)} className={LINK}>
                        {page.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </section>
  )
}

export function HelpHomePage({ index = defaultIndex }: { index?: HelpIndex }) {
  const { t } = useTranslation('help')
  const wsPath = useWorkspacePath()
  const searchId = useId()
  const [query, setQuery] = useState('')
  const searching = query.trim().length >= SEARCH_MIN_LENGTH
  return (
    <Container>
      <Stack gap="lg">
        <PageHeader title={t('home.title')} description={t('home.description')} />
        <div className="space-y-2">
          <Label htmlFor={searchId}>{t('home.search.label')}</Label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              id={searchId}
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t('home.search.placeholder')}
              className="h-11 pl-9"
              autoComplete="off"
            />
          </div>
        </div>
        {searching ? (
          <SearchResults query={query} index={index} />
        ) : (
          <>
            <TutorialsSection index={index} />
            <ReferenceSection index={index} />
          </>
        )}
        <p className="text-sm text-muted-foreground">
          {t('home.footer.prefix')}{' '}
          <Link to={wsPath('/feedback/report')} className={LINK}>
            {t('home.footer.link')}
          </Link>
        </p>
      </Stack>
    </Container>
  )
}

// --- Artikelseite ------------------------------------------------------------

function NotFound({ message }: { message: string }) {
  const { t } = useTranslation('help')
  const wsPath = useWorkspacePath()
  return (
    <Container>
      <Stack gap="md">
        <BackToHelp />
        <EmptyState
          icon={BookOpen}
          title={message}
          action={
            <Button asChild variant="outline">
              <Link to={wsPath('/help')}>{t('nav.overview')}</Link>
            </Button>
          }
        />
      </Stack>
    </Container>
  )
}

/** Meldet den Besuch einer Seite an alle offenen `page_visited`-Schritte (einmal). */
function usePageVisit(path: string | null) {
  const { tutorials, setStep } = useTutorials()
  const reported = useRef<string | null>(null)
  useEffect(() => {
    if (path === null || reported.current === path) return
    const open = tutorials.flatMap((tutorial) =>
      tutorial.steps
        .filter((step) => step.type === 'page_visited' && step.page === path && step.state === 'open')
        .map((step) => ({ tutorialId: tutorial.id, stepId: step.id })),
    )
    if (tutorials.length === 0) return
    reported.current = path
    void (async () => {
      for (const { tutorialId, stepId } of open) await setStep(tutorialId, stepId, 'done')
    })()
  }, [path, tutorials, setStep])
}

function HelpNav({ pages, current }: { pages: HelpPage[]; current: string }) {
  const { t } = useTranslation('help')
  const wsPath = useWorkspacePath()
  const sectionLabel = useSectionLabel()
  const groups = HELP_SECTIONS.map((section) => ({
    section,
    pages: pages.filter((page) => page.section === section),
  })).filter((group) => group.pages.length > 0)
  const list = (
    <ul className="space-y-4 text-sm">
      {groups.map((group) => (
        <li key={group.section}>
          <p className="mb-1 text-xs font-semibold text-muted-foreground uppercase">
            {sectionLabel(group.section)}
          </p>
          <ul className="space-y-1">
            {group.pages.map((page) => {
              const active = page.slug === current
              return (
                <li key={page.slug}>
                  <Link
                    to={wsPath(`/help/${page.slug}`)}
                    aria-current={active ? 'page' : undefined}
                    className={
                      active
                        ? 'block rounded-md bg-muted px-2 py-1 font-medium'
                        : 'block rounded-md px-2 py-1 text-muted-foreground hover:bg-muted hover:text-foreground'
                    }
                  >
                    {page.title}
                  </Link>
                </li>
              )
            })}
          </ul>
        </li>
      ))}
    </ul>
  )
  return (
    <>
      <details className="rounded-lg border bg-card p-3 md:hidden">
        <summary className="cursor-pointer text-sm font-medium">{t('article.allPages')}</summary>
        <nav aria-label={t('article.allPages')} className="mt-3">
          {list}
        </nav>
      </details>
      <nav aria-label={t('article.allPages')} className="hidden w-56 shrink-0 md:block">
        {list}
      </nav>
    </>
  )
}

/** Lesezeit in Minuten (200 Woerter je Minute, mindestens 1). */
function readingMinutes(markdown: string): number {
  return Math.max(1, Math.ceil(markdown.split(/\s+/).filter(Boolean).length / 200))
}

function ArticleBody({ page, pages }: { page: HelpPage; pages: HelpPage[] }) {
  const { t } = useTranslation('help')
  const wsPath = useWorkspacePath()
  const sectionLabel = useSectionLabel()
  usePageVisit(`/help/${page.slug}`)
  const ordered = HELP_SECTIONS.flatMap((section) => pages.filter((p) => p.section === section))
  const next = ordered[ordered.indexOf(page) + 1] as HelpPage | undefined

  async function copyForAgents() {
    try {
      await copyToClipboard(`# ${page.title}\n\n${page.body}\n`)
      notify.success(t('article.copied'))
    } catch (cause) {
      notify.error(cause instanceof Error ? cause.message : t('article.copyFailed'))
    }
  }

  return (
    <Container>
      <Stack gap="lg">
        <nav aria-label={t('article.breadcrumb')} className="text-sm text-muted-foreground">
          <ol className="flex flex-wrap items-center gap-1">
            <li>
              <Link to={wsPath('/help')} className={LINK}>
                {t('home.title')}
              </Link>
            </li>
            <li aria-hidden="true">›</li>
            <li>{sectionLabel(page.section)}</li>
          </ol>
        </nav>
        <PageHeader
          title={page.title}
          description={t('article.meta', {
            date: formatDate(page.updated),
            minutes: readingMinutes(page.body),
          })}
          actions={
            <Button variant="outline" onClick={() => void copyForAgents()}>
              <Copy className="size-4" aria-hidden="true" />
              {t('article.copyForAgents')}
            </Button>
          }
        />
        <div className="flex flex-col gap-6 md:flex-row md:gap-8">
          <HelpNav pages={pages} current={page.slug} />
          <article className="max-w-[680px] min-w-0 flex-1 space-y-6 text-[15px] leading-[1.65]">
            <HelpMarkdown>{page.intro}</HelpMarkdown>
            {page.blocks.map((block) => (
              <section key={block.id} className="space-y-3">
                <BlockHeading block={block} />
                <HelpMarkdown>{block.body}</HelpMarkdown>
              </section>
            ))}
            {next !== undefined ? (
              <p className="border-t pt-4 text-sm">
                <Link to={wsPath(`/help/${next.slug}`)} className={LINK}>
                  {t('article.next', { title: next.title })}
                </Link>
              </p>
            ) : null}
          </article>
          {page.blocks.length > 1 ? (
            <nav aria-label={t('article.onThisPage')} className="hidden w-56 shrink-0 lg:block">
              <p className="mb-2 text-xs font-semibold text-muted-foreground uppercase">
                {t('article.onThisPage')}
              </p>
              <ul className="space-y-1 text-sm">
                {page.blocks
                  .filter((block) => block.level === 2)
                  .map((block) => (
                    <li key={block.id}>
                      <Link to={{ hash: `#${block.id}` }} className={LINK}>
                        {block.title}
                      </Link>
                    </li>
                  ))}
              </ul>
            </nav>
          ) : null}
        </div>
      </Stack>
    </Container>
  )
}

export function HelpArticlePage({ index = defaultIndex }: { index?: HelpIndex }) {
  const { t } = useTranslation('help')
  const { slug = '' } = useParams<{ slug: string }>()
  const locale = useHelpLocale()
  const visible = useVisiblePages(index)
  const page = findPage(index, locale, slug)
  if (page === null || !visible.includes(page)) return <NotFound message={t('article.notFound')} />
  return <ArticleBody page={page} pages={visible} />
}

// --- Tutorial-Seite ----------------------------------------------------------------

function StepStateBadge({ step }: { step: TutorialStep }) {
  const { t } = useTranslation('help')
  if (step.state === 'done') {
    return (
      <Badge variant="secondary" className="gap-1">
        <Check className="size-3" aria-hidden="true" />
        {t('tutorial.state.done')}
      </Badge>
    )
  }
  if (step.state === 'skipped') return <Badge variant="outline">{t('tutorial.state.skipped')}</Badge>
  return <Badge variant="outline">{t('tutorial.state.open')}</Badge>
}

interface StepActionsProps {
  step: TutorialStep
  busy: boolean
  onSet: (state: TutorialStep['state']) => void
}

function StepActions({ step, busy, onSet }: StepActionsProps) {
  const { t } = useTranslation('help')
  const wsPath = useWorkspacePath()
  if (step.type === 'head_start') return null
  const actions: ReactNode[] = []
  if (step.state === 'open') {
    if (step.type === 'page_visited' && step.page) {
      actions.push(
        <Button key="visit" asChild variant="outline" size="sm">
          <Link to={wsPath(step.page)}>{t('tutorial.actions.openPage')}</Link>
        </Button>,
      )
    }
    if (step.type === 'manual') {
      actions.push(
        <Button key="done" size="sm" onClick={() => onSet('done')} disabled={busy}>
          {t('tutorial.actions.markDone')}
        </Button>,
      )
    }
    actions.push(
      <Button key="skip" variant="ghost" size="sm" onClick={() => onSet('skipped')} disabled={busy}>
        {t('tutorial.actions.skip')}
      </Button>,
    )
  } else if (step.state === 'skipped' || !step.automatic) {
    actions.push(
      <Button key="reopen" variant="ghost" size="sm" onClick={() => onSet('open')} disabled={busy}>
        {t('tutorial.actions.reopen')}
      </Button>,
    )
  }
  if (step.automatic && step.state === 'open') {
    actions.unshift(
      <p key="auto" className="w-full text-sm text-muted-foreground">
        {t('tutorial.automaticHint')}
      </p>,
    )
  }
  return <div className="flex flex-wrap items-center gap-2">{actions}</div>
}

interface TutorialBodyProps {
  tutorial: Tutorial
  text: HelpTutorial
  state: TutorialsState
}

function TutorialBody({ tutorial, text, state }: TutorialBodyProps) {
  const { t } = useTranslation('help')
  const { pending, restart, setStep } = state
  const [confirmOpen, setConfirmOpen] = useState(false)
  const done = finishedSteps(tutorial)
  const total = tutorial.steps.length
  const blocks = useMemo(() => new Map(text.blocks.map((block) => [block.id, block])), [text])

  async function onConfirm() {
    const result = await restart(tutorial.id)
    if (result !== null) {
      setConfirmOpen(false)
      notify.success(t('tutorial.restart.done'))
    }
  }

  return (
    <Container>
      <Stack gap="lg">
        <BackToHelp />
        <PageHeader
          title={text.title}
          description={text.description}
          actions={
            <Button variant="outline" onClick={() => setConfirmOpen(true)} disabled={pending !== null}>
              {t('tutorial.actions.restart')}
            </Button>
          }
        />
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {tutorial.completed
              ? t('tutorial.progress.completed', { total })
              : t('tutorial.progress.label', { done, total, minutes: text.durationMinutes })}
          </p>
          <ProgressBar done={done} total={total} label={t('tutorial.progress.aria', { title: text.title })} />
        </div>
        <HelpMarkdown>{text.intro}</HelpMarkdown>
        <ol className="space-y-4">
          {tutorial.steps.map((step, position) => {
            const block = blocks.get(step.id)
            return (
              <li key={step.id}>
                <Card>
                  <CardContent className="space-y-3 pt-6">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <h2 id={step.id} className="scroll-mt-20 text-lg font-semibold">
                        <span className="sr-only">{t('tutorial.stepNumber', { number: position + 1 })} </span>
                        {block?.title ?? step.id}
                      </h2>
                      <StepStateBadge step={step} />
                    </div>
                    {block !== undefined ? <HelpMarkdown>{block.body}</HelpMarkdown> : null}
                    <StepActions
                      step={step}
                      busy={pending !== null}
                      onSet={(state) => void setStep(tutorial.id, step.id, state)}
                    />
                  </CardContent>
                </Card>
              </li>
            )
          })}
        </ol>
      </Stack>
      <RestartDialog
        open={confirmOpen}
        title={text.title}
        busy={pending !== null}
        onOpenChange={setConfirmOpen}
        onConfirm={() => void onConfirm()}
      />
    </Container>
  )
}

// Ein Hook-Aufruf pro Tutorial-Seite; der Body bekommt dieselbe Instanz.

export function HelpTutorialPage({ index = defaultIndex }: { index?: HelpIndex }) {
  const { t } = useTranslation('help')
  const { tutorialId = '' } = useParams<{ tutorialId: string }>()
  const locale = useHelpLocale()
  const state = useTutorials()
  if (state.loading) {
    return (
      <Container>
        <LoadingState rows={4} />
      </Container>
    )
  }
  if (state.error !== null) {
    return (
      <Container>
        <Stack gap="md">
          <BackToHelp />
          <ErrorAlert title={t('home.tutorials.error')} message={state.error} />
          <Button variant="outline" size="sm" className="self-start" onClick={state.reload}>
            {t('home.tutorials.retry')}
          </Button>
        </Stack>
      </Container>
    )
  }
  const tutorial = state.tutorials.find((item) => item.id === tutorialId)
  const text = tutorial === undefined ? null : findTutorial(index, locale, tutorial.id)
  if (tutorial === undefined || text === null) return <NotFound message={t('tutorial.notFound')} />
  return <TutorialBody tutorial={tutorial} text={text} state={state} />
}
