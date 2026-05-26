import { toast } from 'sonner'

interface NotifyOptions {
  description?: string
  duration?: number
}

export const notify = {
  success(message: string, options?: NotifyOptions): void {
    toast.success(message, options)
  },
  error(message: string, options?: NotifyOptions): void {
    toast.error(message, options)
  },
  info(message: string, options?: NotifyOptions): void {
    toast.info(message, options)
  },
} as const

export type Notify = typeof notify
