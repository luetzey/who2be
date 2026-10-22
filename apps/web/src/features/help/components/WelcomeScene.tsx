import type { CSSProperties, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

/*
 * Szenen der Begruessung (Onboarding P6, Spec §3.1, Prototyp `sceneWelcome`/
 * `sceneSuccess`). Reine Dekoration: `aria-hidden`, der Text daneben sagt
 * alles (Spec §8). Die Bewegung steht in `globals.css` (`w2b-anim-scene-*`)
 * und laeuft nur ohne „Bewegung reduzieren“; die Grundstile dort sind der
 * Endzustand, den reduzierte Bewegung sofort zeigt. Die SVG skaliert ueber
 * `viewBox` mit (390 px Vollbild).
 */

const BOX = { width: 140, height: 80, rx: 14 }

function Box({ x, y, title, subtitle, brand = false, className }: {
  x: number
  y: number
  title: ReactNode
  subtitle: string
  brand?: boolean
  className?: string
}) {
  return (
    <g className={className}>
      <rect
        x={x}
        y={y}
        {...BOX}
        className={brand ? 'w2b-scene-box w2b-scene-box-brand' : 'w2b-scene-box'}
      />
      <text x={x + BOX.width / 2} y={y + 36} className="w2b-scene-title">
        {title}
      </text>
      <text x={x + BOX.width / 2} y={y + 58} className="w2b-scene-sub">
        {subtitle}
      </text>
    </g>
  )
}

const WORDMARK = (
  <>
    Who<tspan className="w2b-scene-two">2</tspan>Be
  </>
)

/** Steckbrief-Karte wandert von Who2Be zu „Claude & Co.“, dann springt der Haken auf. */
export function WelcomeScene() {
  const { t } = useTranslation('help')
  return (
    <div className="w2b-scene" aria-hidden="true" data-testid="welcome-scene">
      <svg viewBox="0 0 520 170" className="block h-auto w-full" focusable="false">
        <path className="w2b-anim-scene-path" d="M160 85 Q260 25 360 85" />
        <Box x={20} y={45} title={WORDMARK} subtitle={t('welcome.scene.source')} brand />
        <Box
          x={360}
          y={45}
          title={t('welcome.scene.client')}
          subtitle={t('welcome.scene.clientSub')}
          className="w2b-anim-scene-arrive"
        />
        <g className="w2b-anim-scene-card">
          <rect x={-24} y={-16} width={48} height={32} rx={6} />
          <circle cx={-12} cy={-5} r={5} />
          <path d="M-3 -7h18M-3 -1h12M-16 7h32" />
        </g>
        <g className="w2b-anim-scene-ok">
          <circle cx={488} cy={48} r={13} />
          <path d="M482 48l4 4 8-8" />
        </g>
      </svg>
    </div>
  )
}

const BURST_ANGLES = [0, 60, 120, 180, 240, 300]

/** Linie zeichnet sich zwischen den Kaesten, Haken springt in die Mitte, Punkte fliegen. */
export function SuccessScene({ agentName, clientName }: { agentName: string; clientName: string }) {
  const { t } = useTranslation('help')
  return (
    <div className="w2b-scene" aria-hidden="true" data-testid="success-scene">
      <svg viewBox="0 0 520 150" className="block h-auto w-full" focusable="false">
        <path className="w2b-anim-scene-line" d="M160 75 H360" />
        <Box x={20} y={35} title={WORDMARK} subtitle={agentName} brand />
        <Box
          x={360}
          y={35}
          title={clientName}
          subtitle={t('welcome.scene.connected')}
          className="w2b-scene-box-ok"
        />
        <g className="w2b-anim-scene-burst">
          {BURST_ANGLES.map((angle) => (
            <circle
              key={angle}
              cx={260}
              cy={75}
              r={3.5}
              style={{ '--w2b-burst-angle': `${angle}deg` } as CSSProperties}
            />
          ))}
        </g>
        <g className="w2b-anim-scene-mid">
          <circle cx={260} cy={75} r={20} />
          <path d="M250 75l7 7 13-13" />
        </g>
      </svg>
    </div>
  )
}
