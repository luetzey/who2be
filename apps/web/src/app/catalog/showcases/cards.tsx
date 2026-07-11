import { Bot, Clock, FileText, Layers, ScrollText, TriangleAlert, User } from 'lucide-react'

import { AttentionBanner } from '@/components/data/AttentionBanner'
import { DetailHeader } from '@/components/data/DetailHeader'
import { EntityCard } from '@/components/data/EntityCard'
import { EntityIcon } from '@/components/data/EntityIcon'
import { MetaPill } from '@/components/data/MetaPill'
import { UsedByList } from '@/components/data/UsedByList'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function CardsShowcase() {
  return (
    <ShowcaseSection
      id="cards"
      title="Karten- und Detail-Komponenten"
      description="EntityIcon, MetaPill, EntityCard, AttentionBanner, DetailHeader, UsedByList — die geteilte Basis fuer Listen- und Detail-Pages."
    >
      <ShowcaseRow label="EntityIcon (Toene / Groessen)">
        <EntityIcon icon={ScrollText} tone="tools" size="lg" />
        <EntityIcon icon={Bot} tone="catalog" />
        <EntityIcon icon={FileText} tone="resource" />
        <EntityIcon icon={User} tone="persona" size="sm" />
      </ShowcaseRow>

      <ShowcaseRow label="MetaPill">
        <MetaPill icon={User} iconTone="persona">
          Coach Carla
        </MetaPill>
        <MetaPill tone="resource">policy</MetaPill>
        <MetaPill icon={TriangleAlert} tone="destructive">
          Persona fehlt
        </MetaPill>
      </ShowcaseRow>

      <ShowcaseRow label="EntityCard (schlicht)">
        <div className="w-full">
          <EntityCard
            icon={ScrollText}
            iconTone="tools"
            title="Support-Base"
            href="#"
            badges={
              <>
                <Badge variant="outline">support-base</Badge>
                <Badge variant="secondary">v3</Badge>
              </>
            }
            description="Grund-Prompt fuer 1:1-Support-Gespraeche."
            meta={<MetaPill icon={User} iconTone="persona">Verwendet von 6 Agents</MetaPill>}
          />
        </div>
      </ShowcaseRow>

      <ShowcaseRow label="EntityCard (mit Split-Action)">
        <div className="w-full">
          <EntityCard
            icon={Bot}
            iconTone="catalog"
            title="Carla Bot"
            href="#"
            description="Customer-Support-Agent fuer 1:1-Gespraeche."
            actions={<Button variant="brand" size="sm">Kopieren</Button>}
          />
        </div>
      </ShowcaseRow>

      <ShowcaseRow label="EntityCard (Expander)">
        <div className="w-full">
          <EntityCard
            icon={FileText}
            iconTone="resource"
            title="Rueckerstattungs-Policy"
            href="#"
            description="Regeln und Fristen fuer Rueckerstattungen."
            expandIcon={Layers}
            expandLabel="2 Sub-Resources"
            expandSummary="Fristen-Tabelle · Sonderfaelle"
            defaultOpen
            expandable={
              <UsedByList
                aria-label="Sub-Resources"
                items={[
                  { id: 's1', name: 'Fristen-Tabelle', href: '#', icon: FileText, iconTone: 'resource', meta: 'Aktiv · v1' },
                  { id: 's2', name: 'Sonderfaelle', href: '#', icon: FileText, iconTone: 'resource', meta: 'Aktiv · v1' },
                ]}
              />
            }
          />
        </div>
      </ShowcaseRow>

      <ShowcaseRow label="AttentionBanner">
        <div className="flex w-full flex-col gap-3">
          <AttentionBanner
            icon={Clock}
            title="Version 3 liegt zur Review"
            description="Von Max Berger eingereicht · wartet auf Freigabe durch einen Admin."
            actions={
              <>
                <Button variant="brand" size="sm">Aktivieren</Button>
                <Button variant="outline" size="sm">Zurueck zu Entwurf</Button>
              </>
            }
          />
          <AttentionBanner
            icon={TriangleAlert}
            variant="destructive"
            title="Entwurf unvollstaendig"
            description="Verknuepfte Persona fehlt — noch nicht aktivierbar."
          />
        </div>
      </ShowcaseRow>

      <ShowcaseRow label="DetailHeader">
        <div className="w-full">
          <DetailHeader
            icon={ScrollText}
            iconTone="tools"
            title="Support-Base"
            backHref="#"
            backLabel="System-Prompts"
            badges={
              <Badge variant="outline">support-base</Badge>
            }
            description="Grund-Prompt fuer 1:1-Support-Gespraeche."
            actions={<Button variant="outline" size="sm">Duplizieren</Button>}
          />
        </div>
      </ShowcaseRow>

      <ShowcaseRow label="UsedByList">
        <div className="w-full max-w-md">
          <UsedByList
            aria-label="Verlinkt in"
            items={[
              { id: 'pb1', name: 'Coach', href: '#', icon: Layers, iconTone: 'playbook', meta: '2 Bloecke' },
              { id: 'pb2', name: 'Onboarding-Flow', href: '#', icon: Layers, iconTone: 'playbook', meta: '3 Bloecke' },
            ]}
          />
        </div>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
