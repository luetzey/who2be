import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import i18n from '@/i18n'
import { axe } from '@/test/a11y'

const { mockConfig } = vi.hoisted(() => ({
  mockConfig: {
    notice: { de: '', en: '' },
    noticeLevel: 'info' as 'info' | 'warning',
  },
}))

vi.mock('@/config', () => ({ config: mockConfig }))

import { NOTICE_DISMISSED_KEY, NoticeBanner } from './NoticeBanner'

afterEach(async () => {
  mockConfig.notice = { de: '', en: '' }
  mockConfig.noticeLevel = 'info'
  window.sessionStorage.clear()
  await i18n.changeLanguage('de')
})

describe('NoticeBanner', () => {
  it('rendert ohne Text nichts', () => {
    const { container } = render(<NoticeBanner />)

    expect(container).toBeEmptyDOMElement()
  })

  it('zeigt Freitext als reinen Text — Markup wird nicht interpretiert', () => {
    const hostile = '<img src=x onerror="alert(1)"><b>fett</b> [Link](javascript:alert(1))'
    mockConfig.notice = { de: hostile, en: '' }

    const { container } = render(<NoticeBanner />)

    const banner = screen.getByTestId('notice-banner')
    expect(banner).toHaveTextContent(hostile)
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('b')).toBeNull()
    expect(container.querySelector('a')).toBeNull()
  })

  it('behaelt Zeilenumbrueche als Text bei (pre-line)', () => {
    mockConfig.notice = { de: 'Zeile 1\nZeile 2', en: '' }

    render(<NoticeBanner />)

    const paragraph = screen.getByText(/Zeile 1/)
    expect(paragraph.textContent).toBe('Zeile 1\nZeile 2')
    expect(paragraph).toHaveClass('whitespace-pre-line')
  })

  it('waehlt die aktive Sprache und faellt von EN auf DE zurueck', async () => {
    mockConfig.notice = { de: 'Wartung heute', en: 'Maintenance today' }
    await i18n.changeLanguage('en')

    const { unmount } = render(<NoticeBanner />)
    expect(screen.getByTestId('notice-banner')).toHaveTextContent('Maintenance today')
    unmount()

    mockConfig.notice = { de: 'Wartung heute', en: '' }
    render(<NoticeBanner />)
    expect(screen.getByTestId('notice-banner')).toHaveTextContent('Wartung heute')
  })

  it('nutzt role=status fuer info und role=alert fuer warning', () => {
    mockConfig.notice = { de: 'Hinweis', en: '' }

    const { unmount } = render(<NoticeBanner />)
    expect(screen.getByRole('status')).toHaveTextContent('Hinweis')
    expect(screen.queryByRole('alert')).toBeNull()
    unmount()

    mockConfig.noticeLevel = 'warning'
    render(<NoticeBanner />)
    expect(screen.getByRole('alert')).toHaveTextContent('Hinweis')
  })

  it('ist ohne dismissible nicht wegklickbar', () => {
    mockConfig.notice = { de: 'Hinweis', en: '' }

    render(<NoticeBanner />)

    expect(screen.queryByRole('button', { name: 'Hinweis ausblenden' })).toBeNull()
  })

  it('laesst sich pro Sitzung wegklicken und bleibt beim erneuten Rendern weg', () => {
    mockConfig.notice = { de: 'Neustart um 23 Uhr', en: '' }

    const { unmount } = render(<NoticeBanner dismissible />)
    fireEvent.click(screen.getByRole('button', { name: 'Hinweis ausblenden' }))

    expect(screen.queryByTestId('notice-banner')).toBeNull()
    expect(window.sessionStorage.getItem(NOTICE_DISMISSED_KEY)).toBe('Neustart um 23 Uhr')
    unmount()

    render(<NoticeBanner dismissible />)
    expect(screen.queryByTestId('notice-banner')).toBeNull()
  })

  it('zeigt einen neuen Text wieder, auch wenn der alte weggeklickt war', () => {
    window.sessionStorage.setItem(NOTICE_DISMISSED_KEY, 'Alter Hinweis')
    mockConfig.notice = { de: 'Neuer Hinweis', en: '' }

    render(<NoticeBanner dismissible />)

    expect(screen.getByTestId('notice-banner')).toHaveTextContent('Neuer Hinweis')
  })

  it('hat keine axe-Violations (info, wegklickbar)', async () => {
    mockConfig.notice = { de: 'Wartung ab 22 Uhr', en: '' }

    const { container } = render(<NoticeBanner dismissible />)

    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations (warning)', async () => {
    mockConfig.notice = { de: 'Neustart in 10 Minuten', en: '' }
    mockConfig.noticeLevel = 'warning'

    const { container } = render(<NoticeBanner />)

    expect(await axe(container)).toHaveNoViolations()
  })
})
