import { Download } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import '../i18n'

import type { InvoiceListItem, InvoiceListResponse } from '@/api/client'
import { useApi } from '@/api/useApi'
import { EmptyState, ErrorAlert, LoadingState } from '@/components/data'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from '@/components/ui'
import i18n from '@/i18n'
import { formatDate, uiLocale } from '@/lib/dates'
import { downloadFile } from '@/lib/download'

interface UseInvoicesResult {
  data: InvoiceListResponse | null
  loading: boolean
  error: string | null
}

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

/**
 * Laedt die ausgestellten Rechnungen der Organisation (ADR-0061 R3). Der
 * Endpoint ist admin-only; das Panel rendert die Karte nur fuer Admins.
 */
function useInvoices(): UseInvoicesResult {
  const api = useApi()
  const [data, setData] = useState<InvoiceListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .listInvoices()
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(describeError(cause))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [api])

  return { data, loading, error }
}

function formatAmount(invoice: InvoiceListItem, unknown: string): string {
  if (invoice.amount_value === null) return unknown
  const value = Number(invoice.amount_value)
  if (Number.isNaN(value)) return unknown
  return new Intl.NumberFormat(uiLocale(), { style: 'currency', currency: invoice.currency }).format(
    value,
  )
}

/**
 * Rechnungs-Karte im Billing-Bereich: Nummer, Datum, Betrag, Status und der
 * PDF-Download aus dem eigenen Archiv. Eine Quelle je Zeile ist `status` der
 * API: nur `archived` hat einen Download-Knopf. Ein laufender Download sperrt
 * alle Knoepfe (kein Doppel-Abruf).
 */
export function InvoiceListCard() {
  const { t } = useTranslation('billing')
  const api = useApi()
  const { data, loading, error } = useInvoices()
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  // Der State kommt erst nach dem naechsten Render an; der Ref sperrt sofort.
  const busy = useRef(false)

  const download = useCallback(
    async (invoice: InvoiceListItem) => {
      if (busy.current) return
      busy.current = true
      setDownloadingId(invoice.id)
      setDownloadError(null)
      try {
        const blob = await api.downloadInvoicePdf(invoice.id)
        downloadFile(blob, `${invoice.invoice_number}.pdf`)
      } catch {
        setDownloadError(t('invoices.downloadFailed'))
      } finally {
        busy.current = false
        setDownloadingId(null)
      }
    },
    [api, t],
  )

  const invoices = data?.invoices ?? []

  return (
    <Card>
      <CardHeader>
        <CardTitle className="min-w-0 truncate">{t('invoices.title')}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <LoadingState />
        ) : error ? (
          <ErrorAlert message={error} />
        ) : invoices.length === 0 ? (
          <EmptyState
            title={t('invoices.emptyTitle')}
            description={t('invoices.emptyDescription')}
          />
        ) : (
          <ul aria-label={t('invoices.listLabel')} className="divide-y" data-testid="invoice-list">
            {invoices.map((invoice) => (
              <li
                key={invoice.id}
                className="flex min-w-0 flex-col gap-2 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 space-y-0.5">
                  <p className="font-medium break-all">
                    <span className="sr-only">{t('invoices.number')}: </span>
                    {invoice.invoice_number}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    <span className="sr-only">{t('invoices.date')}: </span>
                    <time dateTime={invoice.issued_at}>{formatDate(invoice.issued_at)}</time>
                    <span aria-hidden="true"> · </span>
                    <span className="sr-only">, {t('invoices.amount')}: </span>
                    <span className="tabular-nums">
                      {formatAmount(invoice, t('invoices.amountUnknown'))}
                    </span>
                  </p>
                </div>
                <div className="flex shrink-0 items-center justify-between gap-2 sm:justify-end">
                  <Badge variant={invoice.status === 'archived' ? 'secondary' : 'outline'}>
                    <span className="sr-only">{t('invoices.status')}: </span>
                    {invoice.status === 'archived'
                      ? t('invoices.statusArchived')
                      : t('invoices.statusIssued')}
                  </Badge>
                  {invoice.status === 'archived' ? (
                    <Button
                      variant="outline"
                      className="h-10"
                      disabled={downloadingId !== null}
                      aria-label={t('invoices.downloadLabel', { number: invoice.invoice_number })}
                      onClick={() => void download(invoice)}
                    >
                      <Download aria-hidden="true" />
                      {downloadingId === invoice.id
                        ? t('invoices.downloading')
                        : t('invoices.download')}
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
        {downloadError ? <ErrorAlert message={downloadError} /> : null}
      </CardContent>
    </Card>
  )
}
