import Markdown, { type MarkdownToJSX } from 'markdown-to-jsx'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { safeHelpHref } from '@/help/helpIndex'

import { useHelpPath } from '../publicHelp'

/*
 * Markdown-Darstellung des Hilfe-Dialekts (ADR-0058), geteilt von den
 * Hilfe-Seiten und der Startliste auf dem Dashboard. Eigene Datei, damit das
 * Dashboard die Hilfe-Seiten nicht mitlaedt.
 */

const LINK = 'font-medium text-brand underline-offset-4 hover:underline'

function HelpLink({ href, children }: { href?: string; children?: ReactNode }) {
  // In der oeffentlichen Hilfe `/help/…`, sonst `/w/<id>/help/…`.
  const wsPath = useHelpPath()
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
