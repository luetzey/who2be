import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

// Crawler-Signal der Web-App (Audit S1). Der X-Robots-Tag-Header der
// Caddyfile ist die erste Linie; dieses Meta-Tag und die robots.txt sind die
// zweite fuer Deployments ohne Caddy (Dokploy/Traefik, Self-Hosting). Der
// Header selbst wird in deploy/hetzner/tests/test_headers_ci.sh geprueft.
//
// Google Search Central, „Block Search indexing with noindex": „For the
// noindex rule to be effective, the page or resource must not be blocked by a
// robots.txt file". Deshalb prueft der Test beides zusammen: noindex im
// Dokument UND keine Sperre in robots.txt.

const WEB_ROOT = resolve(__dirname, '..', '..')
const indexHtml = readFileSync(resolve(WEB_ROOT, 'index.html'), 'utf8')
const robotsTxt = readFileSync(resolve(WEB_ROOT, 'public', 'robots.txt'), 'utf8')

describe('Crawler-Signal', () => {
  it('index.html traegt <meta name="robots"> mit noindex und nofollow im <head>', () => {
    const head = indexHtml.slice(0, indexHtml.indexOf('</head>'))
    const tag = /<meta\s+name="robots"\s+content="([^"]*)"/i.exec(head)

    expect(tag).not.toBeNull()
    const rules = (tag?.[1] ?? '').split(',').map((r) => r.trim().toLowerCase())
    expect(rules).toContain('noindex')
    expect(rules).toContain('nofollow')
  })

  it('robots.txt ist eine Textdatei und sperrt keine Seite', () => {
    const rules = robotsTxt
      .split('\n')
      .map((line) => line.replace(/#.*/, '').trim())
      .filter(Boolean)

    expect(rules).toContain('User-agent: *')
    // `Disallow: /` (oder jede andere Disallow-Zeile) wuerde Crawler vor dem
    // noindex aussperren — die Seite koennte dann als nackte URL im Index landen.
    expect(rules.filter((r) => /^disallow\s*:\s*\S/i.test(r))).toEqual([])
    expect(robotsTxt).not.toMatch(/<html/i)
  })
})
