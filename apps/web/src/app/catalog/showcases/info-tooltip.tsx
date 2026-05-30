import { InfoTooltip } from '@/components/ui/info-tooltip'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function InfoTooltipShowcase() {
  return (
    <ShowcaseSection
      id="info-tooltip"
      title="InfoTooltip"
      description="Kleiner Info-Icon-Button neben Section-Titel oder Label. Hilfetexte schweben hinter dem Icon statt im Layout zu liegen. Hover, Focus und Long-Press oeffnen den Tooltip; Escape schliesst."
    >
      <ShowcaseRow label="Mit kurzer Erklaerung">
        <span className="flex items-center gap-2">
          <span className="text-sm font-medium">Tags</span>
          <InfoTooltip>
            Stichwoerter zur Suche und Gruppierung. Enter zum Anlegen, Klick auf
            das X zum Entfernen.
          </InfoTooltip>
        </span>
      </ShowcaseRow>
      <ShowcaseRow label="Mit Codeblock im Content">
        <span className="flex items-center gap-2">
          <span className="text-sm font-medium">Profil</span>
          <InfoTooltip>
            <div className="space-y-2">
              <p>Strukturierte Beispiele schlagen Bullet-Listen.</p>
              <pre className="rounded bg-muted/50 p-2 font-mono text-xs whitespace-pre-wrap">
                {'Rolle: Senior-Coach.\nTonfall: ruhig, direkt.'}
              </pre>
            </div>
          </InfoTooltip>
        </span>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
