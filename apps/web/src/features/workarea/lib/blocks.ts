// Zerlegt das anker-annotierte Markdown eines Artifacts in Bloecke.
//
// Der Server rendert doc-Artifacts als Markdown, in dem jeder Block seinen
// stabilen Anker traegt (ADR-0021: `<artifact_id>#<block_id>`). Das Format
// kommt aus `services/wa_blocks.py::render_markdown(with_anchors=True)`:
// Bloecke sind durch eine Leerzeile getrennt, und der Anker steht als SUFFIX —
// bei Code-Bloecken auf eigener Zeile nach der schliessenden Fence (im Code
// selbst waere er Teil des Inhalts), sonst am Ende der letzten Zeile.
//
// Deshalb wird zeilenweise geparst statt an `\n\n` gesplittet: der Rumpf eines
// Code-Blocks darf Leerzeilen enthalten, ein Split wuerde ihn zerreissen. Ein
// Block endet genau dort, wo seine Anker-Annotation steht.
//
// Der Block-Text wird danach BEWUSST als Rohtext gerendert, nicht als
// formatiertes Markdown: der Inhalt stammt von Agenten und aus eingelesenen
// Fremdquellen (HTML-/PDF-Ingest). Ein Markdown→HTML-Renderer waere eine neue
// Abhaengigkeit und eine Injektionsflaeche fuer genau die Inhalte, die hier am
// wenigsten vertrauenswuerdig sind. Fuer eine Kontroll-Ansicht ist Rohtext das
// ehrlichere Format — man sieht, was wirklich gespeichert ist.

/** Ein Block des gerenderten Artifacts. */
export interface ArtifactBlock {
  /** Serverseitig vergebene Block-Kennung; null bei Text ohne Annotation. */
  blockId: string | null
  /** Roher Block-Text ohne die Anker-Annotation. */
  text: string
}

// Anker auf eigener Zeile (Code-Bloecke): die Zeile ist NUR die Annotation.
const STANDALONE_ANCHOR = /^\[#([A-Za-z0-9_-]+)\]$/
// Anker am Zeilenende (alle anderen Bloecke): Text, Leerzeichen, Annotation.
const TRAILING_ANCHOR = /^(.*)\s\[#([A-Za-z0-9_-]+)\]$/

function push(blocks: ArtifactBlock[], lines: string[], blockId: string | null): void {
  const text = lines.join('\n').trim()
  // Ein Block ohne Anker UND ohne Text traegt nichts bei (Trennleerzeilen).
  if (blockId === null && text === '') return
  blocks.push({ blockId, text })
}

/**
 * Zerlegt annotiertes Artifact-Markdown in Bloecke.
 *
 * Text nach dem letzten Anker (oder Inhalt ganz ohne Annotationen — etwa ein
 * leeres Artifact oder ein kuenftig geaendertes Render-Format) landet in einem
 * Block mit `blockId: null`. Er ist damit sichtbar, aber nicht
 * anker-adressierbar; lieber ein nicht verlinkbarer Block als verschluckter
 * Inhalt.
 */
export function parseAnchoredMarkdown(markdown: string): ArtifactBlock[] {
  const blocks: ArtifactBlock[] = []
  let pending: string[] = []

  for (const line of markdown.split('\n')) {
    const standalone = STANDALONE_ANCHOR.exec(line)
    if (standalone !== null) {
      push(blocks, pending, standalone[1])
      pending = []
      continue
    }
    const trailing = TRAILING_ANCHOR.exec(line)
    if (trailing !== null) {
      push(blocks, [...pending, trailing[1]], trailing[2])
      pending = []
      continue
    }
    pending.push(line)
  }
  push(blocks, pending, null)

  return blocks
}

/** Baut den vollstaendigen Anker `<artifact_id>#<block_id>` (ADR-0021). */
export function buildAnchor(artifactId: string, blockId: string): string {
  return `${artifactId}#${blockId}`
}

/**
 * Zerlegt einen Anker in Artifact- und Block-Teil; `null`, wenn er keiner ist.
 *
 * Auch fuer KB-Belege nutzbar: `source_ref` der Form
 * `artifact:<uuid>#<block>` traegt denselben Trenner.
 */
export function splitAnchor(anchor: string): { artifactId: string; blockId: string } | null {
  const index = anchor.indexOf('#')
  if (index <= 0 || index === anchor.length - 1) return null
  return { artifactId: anchor.slice(0, index), blockId: anchor.slice(index + 1) }
}
