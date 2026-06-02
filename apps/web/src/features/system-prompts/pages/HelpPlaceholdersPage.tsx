import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

import { PlaceholderHelpContent } from '../components/PlaceholderHelp'

/**
 * Ausfuehrliche Hilfe-Seite zu den verfügbaren Placeholdern (Doku-Link-Ziel des
 * Placeholder-Popovers, Track B Punkt 12).
 */
export function HelpPlaceholdersPage() {
  const wsPath = useWorkspacePath()
  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/system-prompts')}>
            <ArrowLeft className="h-4 w-4" />
            System-Prompts
          </Link>
        </Button>
        <PageHeader
          title="Placeholder-Referenz"
          description="Welche Placeholder dir im System-Prompt-Editor zur Verfügung stehen und was sie beim MCP-Read einfügen."
        />
        <Card>
          <CardContent className="pt-6">
            <PlaceholderHelpContent />
          </CardContent>
        </Card>
      </Stack>
    </Container>
  )
}
