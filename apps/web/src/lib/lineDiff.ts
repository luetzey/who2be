/**
 * Zeilenbasierter Diff (LCS) fuer die git-artige Versions-Diff-Ansicht (WP-C).
 *
 * Reine Utility ohne Dependencies: vergleicht zwei Klartexte zeilenweise
 * (klassisches LCS-DP mit Backtracking) und gruppiert die Aenderungen in
 * Hunks mit begrenztem Kontext — dieselbe Struktur wie `git diff --unified`.
 * Die Textmengen sind serverseitig gedeckelt (Content-Limits ~50k Zeichen),
 * das O(n*m)-DP bleibt damit unkritisch.
 */

export type DiffLineKind = 'context' | 'added' | 'removed'

export interface DiffLine {
  kind: DiffLineKind
  text: string
  /** 1-basierte Zeilennummer im Vorher-Text; null bei added. */
  beforeLine: number | null
  /** 1-basierte Zeilennummer im Nachher-Text; null bei removed. */
  afterLine: number | null
}

export interface DiffHunk {
  /** 1-basierter Start im Vorher-Text (0, wenn der Hunk keine Vorher-Zeilen hat). */
  beforeStart: number
  beforeCount: number
  /** 1-basierter Start im Nachher-Text (0, wenn der Hunk keine Nachher-Zeilen hat). */
  afterStart: number
  afterCount: number
  lines: DiffLine[]
}

/** `''` hat null Zeilen (nicht eine leere) — sonst diffen leere Texte gegeneinander. */
function splitLines(text: string): string[] {
  return text === '' ? [] : text.split('\n')
}

/** Vollstaendige Zeilen-Op-Liste (context/removed/added) via LCS-Backtracking. */
function diffOps(before: string[], after: string[]): DiffLine[] {
  const n = before.length
  const m = after.length
  // dp[i][j] = LCS-Laenge von before[i..] und after[j..].
  const width = m + 1
  const dp = new Int32Array((n + 1) * width)
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i * width + j] =
        before[i] === after[j]
          ? dp[(i + 1) * width + j + 1] + 1
          : Math.max(dp[(i + 1) * width + j], dp[i * width + j + 1])
    }
  }
  const ops: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (before[i] === after[j]) {
      ops.push({ kind: 'context', text: before[i], beforeLine: i + 1, afterLine: j + 1 })
      i++
      j++
    } else if (dp[(i + 1) * width + j] >= dp[i * width + j + 1]) {
      ops.push({ kind: 'removed', text: before[i], beforeLine: i + 1, afterLine: null })
      i++
    } else {
      ops.push({ kind: 'added', text: after[j], beforeLine: null, afterLine: j + 1 })
      j++
    }
  }
  while (i < n) {
    ops.push({ kind: 'removed', text: before[i], beforeLine: i + 1, afterLine: null })
    i++
  }
  while (j < m) {
    ops.push({ kind: 'added', text: after[j], beforeLine: null, afterLine: j + 1 })
    j++
  }
  return ops
}

/** Schneidet einen Hunk aus der Op-Liste und berechnet die Header-Zahlen. */
function toHunk(ops: DiffLine[], start: number, end: number): DiffHunk {
  const lines = ops.slice(start, end + 1)
  const beforeLines = lines.filter((line) => line.beforeLine !== null)
  const afterLines = lines.filter((line) => line.afterLine !== null)
  return {
    beforeStart: beforeLines.length > 0 ? (beforeLines[0].beforeLine ?? 0) : 0,
    beforeCount: beforeLines.length,
    afterStart: afterLines.length > 0 ? (afterLines[0].afterLine ?? 0) : 0,
    afterCount: afterLines.length,
    lines,
  }
}

/**
 * Unified-Zeilen-Diff `before → after` als Hunk-Liste.
 *
 * Identische Texte (auch beide leer) liefern `[]`. `context` steuert, wie
 * viele unveraenderte Zeilen um jede Aenderung erhalten bleiben; Aenderungen,
 * deren Kontextfenster sich beruehren, verschmelzen zu einem Hunk (wie git).
 */
export function computeLineDiff(before: string, after: string, context = 3): DiffHunk[] {
  if (before === after) {
    return []
  }
  const ops = diffOps(splitLines(before), splitLines(after))
  const changed = ops.map((op) => op.kind !== 'context')
  const hunks: DiffHunk[] = []
  let index = changed.indexOf(true)
  while (index !== -1) {
    const start = Math.max(0, index - context)
    // Hunk verlaengern, solange die naechste Aenderung im 2*context-Fenster liegt.
    let lastChange = index
    for (let k = index + 1; k < ops.length; k++) {
      if (changed[k]) {
        if (k - lastChange > context * 2) {
          break
        }
        lastChange = k
      }
    }
    const end = Math.min(ops.length - 1, lastChange + context)
    hunks.push(toHunk(ops, start, end))
    index = changed.indexOf(true, end + 1)
  }
  return hunks
}

/** Git-Stil-Hunk-Header, z. B. `@@ -3,4 +3,5 @@`. */
export function formatHunkHeader(hunk: DiffHunk): string {
  return `@@ -${hunk.beforeStart},${hunk.beforeCount} +${hunk.afterStart},${hunk.afterCount} @@`
}
