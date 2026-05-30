import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// Mantine-Baseline fuer BlockNote-Insel (ADR-0022) — MUSS vor globals.css
// stehen. Sonst fehlen Slash-Menu-Layout (Item-Body/Title/Subtitle/Section),
// Group-Label und Block-Render-Defaults, und unsere scoped Overrides haben
// nichts zu ueberschreiben (Phase 3-fixes Runde 2, Track 2 + 4).
import '@blocknote/mantine/style.css'

import { App } from './App'
import './styles/globals.css'

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('Root-Element #root nicht gefunden')
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
