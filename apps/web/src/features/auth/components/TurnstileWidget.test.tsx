import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TurnstileWidget } from './TurnstileWidget'

// Deckt den Script-Ladepfad ab, den die SignupPage-Tests bewusst
// ueberspringen (dort ist `window.turnstile` vorab gestubbt). Hier wird
// stattdessen das `<script>`-Element beobachtet und sein load/error-Event von
// Hand ausgeloest — kein Request geht nach draussen.

function scriptEl(): HTMLScriptElement | null {
  return document.getElementById('cf-turnstile-script') as HTMLScriptElement | null
}

function stubApi() {
  const api = {
    render: vi.fn<(el: HTMLElement, options: Record<string, unknown>) => string>(
      () => 'widget-1',
    ),
    reset: vi.fn(),
    remove: vi.fn(),
  }
  return api
}

beforeEach(() => {
  vi.resetModules()
})

afterEach(() => {
  delete (window as { turnstile?: unknown }).turnstile
  scriptEl()?.remove()
  vi.restoreAllMocks()
})

describe('TurnstileWidget', () => {
  it('fuegt das Cloudflare-Script genau einmal ein, auch bei zwei Instanzen', async () => {
    render(
      <>
        <TurnstileWidget siteKey="k" action="signup" onToken={vi.fn()} onExpire={vi.fn()} />
        <TurnstileWidget siteKey="k" action="signup" onToken={vi.fn()} onExpire={vi.fn()} />
      </>,
    )

    await waitFor(() => {
      expect(scriptEl()).not.toBeNull()
    })
    expect(document.querySelectorAll('script[id="cf-turnstile-script"]')).toHaveLength(1)
    // `render=explicit` ist nicht kosmetisch: ohne den Parameter sucht
    // Turnstile selbst nach `.cf-turnstile`-Elementen und rendert doppelt.
    expect(scriptEl()?.src).toContain('render=explicit')
  })

  it('rendert das Widget, sobald das Script geladen ist', async () => {
    const api = stubApi()

    render(
      <TurnstileWidget siteKey="site-key-1" action="login" onToken={vi.fn()} onExpire={vi.fn()} />,
    )
    await waitFor(() => {
      expect(scriptEl()).not.toBeNull()
    })

    // Cloudflare setzt `window.turnstile`, bevor es `load` feuert.
    ;(window as { turnstile?: unknown }).turnstile = api
    scriptEl()?.dispatchEvent(new Event('load'))

    await waitFor(() => {
      expect(api.render).toHaveBeenCalledTimes(1)
    })
    expect(api.render.mock.calls[0][1]).toMatchObject({
      sitekey: 'site-key-1',
      // `action` kommt jetzt vom Aufrufer — vier Masken teilen sich einen
      // Site-Key, ohne sie waere die Turnstile-Auswertung eine Sammelspalte.
      action: 'login',
    })
  })

  it('meldet onExpire, wenn das Script nicht laedt (Adblocker, Netz, CSP)', async () => {
    const onExpire = vi.fn()

    render(<TurnstileWidget siteKey="k" action="signup" onToken={vi.fn()} onExpire={onExpire} />)
    await waitFor(() => {
      expect(scriptEl()).not.toBeNull()
    })

    scriptEl()?.dispatchEvent(new Event('error'))

    // Fail-closed: ohne Token bleibt der Submit der Signup-Seite gesperrt,
    // statt in einen unverstaendlichen GoTrue-Fehler zu laufen.
    await waitFor(() => {
      expect(onExpire).toHaveBeenCalled()
    })
  })

  it('raeumt das Widget beim Unmount ab', async () => {
    const api = stubApi()
    const { unmount } = render(
      <TurnstileWidget siteKey="k" action="signup" onToken={vi.fn()} onExpire={vi.fn()} />,
    )
    await waitFor(() => {
      expect(scriptEl()).not.toBeNull()
    })
    ;(window as { turnstile?: unknown }).turnstile = api
    scriptEl()?.dispatchEvent(new Event('load'))
    await waitFor(() => {
      expect(api.render).toHaveBeenCalled()
    })

    unmount()

    expect(api.remove).toHaveBeenCalledWith('widget-1')
  })

  it('rendert nicht mehr, wenn vor dem load-Event unmountet wurde', async () => {
    const api = stubApi()
    const { unmount } = render(
      <TurnstileWidget siteKey="k" action="signup" onToken={vi.fn()} onExpire={vi.fn()} />,
    )
    await waitFor(() => {
      expect(scriptEl()).not.toBeNull()
    })

    unmount()
    ;(window as { turnstile?: unknown }).turnstile = api
    scriptEl()?.dispatchEvent(new Event('load'))

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(api.render).not.toHaveBeenCalled()
  })

  it('nimmt den Kurzschluss, wenn window.turnstile schon da ist', async () => {
    const api = stubApi()
    ;(window as { turnstile?: unknown }).turnstile = api

    render(<TurnstileWidget siteKey="k" action="resend" onToken={vi.fn()} onExpire={vi.fn()} />)

    await waitFor(() => {
      expect(api.render).toHaveBeenCalledTimes(1)
    })
    expect(api.render.mock.calls[0][1]).toMatchObject({ action: 'resend' })
    expect(scriptEl()).toBeNull()
    expect(screen.getByTestId('turnstile-widget')).toBeInTheDocument()
  })
})
