import { AlertCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

interface ErrorAlertProps {
  message: string
  title?: string
}

export function ErrorAlert({ message, title }: ErrorAlertProps) {
  const { t } = useTranslation('data')
  const resolvedTitle = title ?? t('error.title')
  return (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertTitle>{resolvedTitle}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}
