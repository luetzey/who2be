/**
 * Pruefung der Locale-Dateien: Paritaet, doppelte Schluessel, Waisen.
 *
 * ## Warum es das gibt
 *
 * `de.json` und `en.json` sind *Sammeldateien*: jeder PR, der eine Zeichenkette
 * anfasst, schreibt in dieselben zwei Dateien. In einer Welle dieses Repos hat
 * git dort **ohne Konfliktmarker** falsch zusammengefuehrt — danach standen
 * `auth.signup.captcha` und `auth.captcha` nebeneinander, zwei konkurrierende
 * Schluessel fuer dieselbe Sache. Einer davon war tot; die Oberflaeche las den
 * anderen. Aufgefallen ist es nur durch einen Cherry-pick-Gegencheck.
 *
 * Fuer CHANGELOG-artige Sammeldateien gibt es das Fragment-Muster
 * (`changelog.d/`). Fuer Sprachschluesseldateien gibt es kein etabliertes
 * Aequivalent — die Datei *ist* der Namensraum, ein Verzeichnis daraus zu
 * machen verschiebt das Problem nur in einen Zusammenbau-Schritt. Statt der
 * Umstrukturierung steht hier deshalb eine **Pruefung**: sie kann den stillen
 * Fehlmerge nicht verhindern, aber sie macht ihn sichtbar, bevor er in den
 * Baum gelangt.
 *
 * ## Die drei Pruefungen
 *
 * 1. {@link findParityGaps} — Schluesselgleichheit ueber **alle** Namespaces,
 *    in beiden Richtungen. (`localeParity.test.ts` deckt nur `common.errors`
 *    ab, wo der Key zusaetzlich ein Wire-Wert ist; das bleibt bestehen und
 *    traegt seine eigene, engere Begruendung.)
 * 2. {@link findDuplicateKeys} — doppelte Schluessel im **Rohtext**.
 *    `JSON.parse` behaelt still den letzten Treffer, ein Duplikat ist danach
 *    unsichtbar. Deshalb ein eigener Tokenizer ueber den Dateiinhalt.
 * 3. {@link findOrphanKeys} — Schluessel, die im Code nirgends referenziert
 *    werden. **Das ist die Pruefung, die den Captcha-Fall faengt:** beide
 *    Schluessel sind in beiden Dateien vorhanden (Paritaet gruen) und keiner
 *    ist doppelt (Duplikat-Pruefung gruen) — nur referenziert wird eben einer
 *    nicht.
 *
 * ## Bewusste Grenzen
 *
 * Die Waisen-Erkennung liest Code textuell, nicht typisiert. Sie ist deshalb
 * absichtlich **konservativ**: im Zweifel gilt ein Schluessel als benutzt.
 * - Ein dynamischer Aufruf (`` t(`common:status.${s}`) ``) macht den ganzen
 *   Teilbaum unter dem Praefix als benutzt.
 * - Ein Literal gilt als Treffer, wenn es *Suffix* eines Schluesselpfads auf
 *   Punkt-Grenze ist. Grund: `useTranslation('auth')` plus `t('signup.title')`
 *   adressiert `auth.signup.title`, und der aktive Namespace steht nicht am
 *   Aufruf. Ein Suffix-Treffer kann dadurch einen gleichnamigen Schluessel in
 *   einem anderen Namespace mit freisprechen — das nimmt diese Pruefung in
 *   Kauf. Sie ist ein Gate gegen tote Schluessel, kein Beweis der Benutzung.
 */

export type LocaleTree = { [key: string]: string | LocaleTree }

/** Ein Befund der Waisen-Pruefung: der Schluessel und die Datei, in der er steht. */
export interface OrphanFinding {
  readonly key: string
  readonly locale: string
}

/** Ein Befund der Paritaets-Pruefung. */
export interface ParityFinding {
  readonly key: string
  /** Locale, in der der Schluessel **fehlt**. */
  readonly missingIn: string
}

/** Ein Befund der Duplikat-Pruefung. */
export interface DuplicateFinding {
  readonly key: string
  readonly locale: string
  /** Zeilennummern (1-basiert) der doppelten Vorkommen. */
  readonly lines: readonly number[]
}

/** Alle Blattschluessel eines Locale-Baums als punktgetrennte Pfade. */
export function flattenKeys(tree: LocaleTree, prefix = ''): string[] {
  const out: string[] = []
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (value !== null && typeof value === 'object') {
      out.push(...flattenKeys(value as LocaleTree, path))
    } else {
      out.push(path)
    }
  }
  return out
}

/**
 * Schluessel, die in genau einer der beiden Locales vorkommen.
 *
 * Beide Richtungen: `de` ist Default **und** Fallback, ein Loch dort trifft
 * jede Sprache; ein Loch in `en` faellt nur englischen Oberflaechen auf und
 * wird deshalb erst recht nicht von allein bemerkt.
 */
export function findParityGaps(
  a: { locale: string; tree: LocaleTree },
  b: { locale: string; tree: LocaleTree },
): ParityFinding[] {
  const keysA = new Set(flattenKeys(a.tree))
  const keysB = new Set(flattenKeys(b.tree))

  const findings: ParityFinding[] = []
  for (const key of keysA) {
    if (!keysB.has(key)) findings.push({ key, missingIn: b.locale })
  }
  for (const key of keysB) {
    if (!keysA.has(key)) findings.push({ key, missingIn: a.locale })
  }
  return findings.sort((x, y) => x.key.localeCompare(y.key))
}

/**
 * Doppelt vergebene Schluessel im Rohtext einer Locale-Datei.
 *
 * `JSON.parse` wirft bei einem doppelten Schluessel keinen Fehler — der letzte
 * Treffer gewinnt still. Nach einem Fehlmerge kann derselbe Schluessel also
 * zweimal in der Datei stehen, und der geparste Baum sieht makellos aus.
 *
 * Der Tokenizer laeuft deshalb ueber den Text: er zaehlt Verschachtelungstiefe
 * und Pfad mit, erkennt Zeichenketten samt Escapes und unterscheidet einen
 * Schluessel (Zeichenkette vor `:`) von einem Wert.
 */
export function findDuplicateKeys(raw: string, locale: string): DuplicateFinding[] {
  /** Pfadsegmente der offenen Objekte, jeweils mit ihren bisherigen Schluesseln. */
  const stack: { path: string; seen: Map<string, number[]> }[] = []
  const duplicates = new Map<string, number[]>()

  let i = 0
  let line = 1
  let pendingKey: { name: string; line: number } | null = null
  /** In einem Array zaehlen Zeichenketten als Werte, nicht als Schluessel. */
  const containers: ('object' | 'array')[] = []

  const currentPath = (name: string): string => {
    const prefix = stack.length > 0 ? stack[stack.length - 1].path : ''
    return prefix ? `${prefix}.${name}` : name
  }

  while (i < raw.length) {
    const ch = raw[i]

    if (ch === '\n') {
      line += 1
      i += 1
      continue
    }

    if (ch === '"') {
      const startLine = line
      let text = ''
      i += 1
      while (i < raw.length && raw[i] !== '"') {
        if (raw[i] === '\\') {
          text += raw[i] + (raw[i + 1] ?? '')
          i += 2
          continue
        }
        if (raw[i] === '\n') line += 1
        text += raw[i]
        i += 1
      }
      i += 1 // schliessendes Anfuehrungszeichen

      // Zeichenkette in einem Array oder direkt nach `:` -> Wert, kein Schluessel.
      const inArray = containers[containers.length - 1] === 'array'
      let j = i
      while (j < raw.length && /\s/.test(raw[j])) j += 1
      if (!inArray && raw[j] === ':') {
        pendingKey = { name: text, line: startLine }
        const frame = stack[stack.length - 1]
        if (frame) {
          const hits = frame.seen.get(text)
          if (hits) {
            hits.push(startLine)
            duplicates.set(currentPath(text), hits)
          } else {
            frame.seen.set(text, [startLine])
          }
        }
      }
      continue
    }

    if (ch === '{') {
      containers.push('object')
      stack.push({
        path: pendingKey ? currentPath(pendingKey.name) : '',
        seen: new Map(),
      })
      pendingKey = null
      i += 1
      continue
    }

    if (ch === '}') {
      containers.pop()
      stack.pop()
      pendingKey = null
      i += 1
      continue
    }

    if (ch === '[') {
      containers.push('array')
      pendingKey = null
      i += 1
      continue
    }

    if (ch === ']') {
      containers.pop()
      i += 1
      continue
    }

    if (ch === ',') pendingKey = null
    i += 1
  }

  return [...duplicates.entries()]
    .map(([key, lines]) => ({ key, locale, lines: [...lines].sort((a, b) => a - b) }))
    .sort((a, b) => a.key.localeCompare(b.key))
}

/** Was eine Code-Durchsicht an Schluessel-Referenzen gefunden hat. */
export interface KeyUsage {
  /** Vollstaendig aufgeloeste Literale, z. B. `auth.signup.title`. */
  readonly literals: ReadonlySet<string>
  /** Praefixe dynamischer Aufrufe, z. B. `common.status` aus `` t(`common:status.${s}`) ``. */
  readonly prefixes: ReadonlySet<string>
}

/** `common:status.active` und `common.status.active` bezeichnen denselben Schluessel. */
function normalise(key: string): string {
  return key.replace(':', '.')
}

/**
 * Schluessel-Referenzen aus einer Quelldatei.
 *
 * Erfasst wird, womit dieses Repo tatsaechlich uebersetzt:
 * - `t('key')` / `t("key")`, auch als `i18n.t(...)`
 * - `` t(`ns:pfad.${x}`) `` — der statische Teil vor dem ersten `${` als Praefix
 * - `i18nKey="key"` der `<Trans>`-Komponente
 * - **jedes** Zeichenketten-Literal, das die Form eines Schluesselpfads hat.
 *   Das ist die breiteste der Regeln und sie ist Absicht: dieses Repo reicht
 *   Schluessel regelmaessig als Daten herum und uebersetzt sie erst spaeter —
 *   als `labelKey`-Feld (`t(item.labelKey)`), als Record-Tabelle
 *   (`const LABEL = { added: 'diff.added' }` + `t(LABEL[op])`) oder als
 *   Array-Eintrag. Eine Regel, die nur `t('…')` kennt, haelt all das faelsch-
 *   lich fuer tot. Ein Literal wie `'node.edgeSupports'` kann daneben auch
 *   etwas anderes bezeichnen — dann spricht es hoechstens einen Schluessel zu
 *   viel frei, und das ist die richtige Richtung fuer ein Gate gegen tote
 *   Schluessel.
 *
 * Ausgeschlossen sind Formen, die sicher keine Schluessel sind: Dateinamen und
 * Erweiterungen, Pfade, URLs, Platzhalter und alles mit Leerzeichen.
 */
export function extractKeyUsage(source: string): KeyUsage {
  const literals = new Set<string>()
  const prefixes = new Set<string>()

  const quoted = /\bt\(\s*['"]([^'"]+)['"]/g
  const trans = /\bi18nKey\s*=\s*['"{]?\s*['"]([^'"]+)['"]/g
  for (const pattern of [quoted, trans]) {
    for (const match of source.matchAll(pattern)) {
      literals.add(normalise(match[1]))
    }
  }

  // Jedes Literal, das wie ein Schluesselpfad aussieht: mindestens zwei
  // Segmente aus Wortzeichen, durch `.` getrennt, optional ein `ns:`-Praefix.
  for (const match of source.matchAll(/['"]([A-Za-z][\w]*(?::[\w]+)?(?:\.[\w]+)+)['"]/g)) {
    const candidate = match[1]
    // Dateiendungen und Versionsnummern sehen aehnlich aus.
    if (/\.(ts|tsx|js|jsx|json|css|svg|png|md|html)$/.test(candidate)) continue
    if (/^\d|\.\d/.test(candidate)) continue
    literals.add(normalise(candidate))
  }

  // Template-Literal: alles vor dem ersten `${` ist der statische Praefix.
  for (const match of source.matchAll(/\bt\(\s*`([^`]*?)\$\{/g)) {
    const prefix = normalise(match[1]).replace(/\.$/, '')
    if (prefix) prefixes.add(prefix)
  }
  // Template-Literal ohne Platzhalter ist ein gewoehnliches Literal.
  for (const match of source.matchAll(/\bt\(\s*`([^`$]+)`/g)) {
    literals.add(normalise(match[1]))
  }

  return { literals, prefixes }
}

/** Vereinigt mehrere Durchsichten zu einer Gesamtsicht. */
export function mergeUsage(usages: readonly KeyUsage[]): KeyUsage {
  const literals = new Set<string>()
  const prefixes = new Set<string>()
  for (const usage of usages) {
    for (const literal of usage.literals) literals.add(literal)
    for (const prefix of usage.prefixes) prefixes.add(prefix)
  }
  return { literals, prefixes }
}

/** Ob `candidate` auf Punkt-Grenze ein Suffix von `key` ist (oder gleich). */
function isSuffixOnDotBoundary(key: string, candidate: string): boolean {
  if (key === candidate) return true
  return key.endsWith(`.${candidate}`)
}

/** Ob `prefix` auf Punkt-Grenze am Anfang von `key` steht. */
function isPrefixOnDotBoundary(key: string, prefix: string): boolean {
  return key === prefix || key.startsWith(`${prefix}.`)
}

/**
 * Ob `prefix` irgendwo auf Punkt-Grenze *beginnt* — auch mitten im Pfad.
 *
 * Noetig, weil ein dynamischer Aufruf denselben blinden Fleck hat wie ein
 * statisches Literal: `` t(`form.policy.capField.${name}`) `` unter
 * `useTranslation('agents')` adressiert `agents.form.policy.capField.*`, und
 * der aktive Namespace steht nicht am Aufruf.
 */
function coversAsPrefix(key: string, prefix: string): boolean {
  return isPrefixOnDotBoundary(key, prefix) || key.includes(`.${prefix}.`)
}

/**
 * i18next-Plural-Suffixe (`_one`, `_other`, …) abschneiden.
 *
 * Der Code ruft `t('card.pendingMemories', { count })` auf; i18next waehlt
 * daraus zur Laufzeit `card.pendingMemories_one` oder `_other`. Im Code steht
 * also nie die Suffix-Form — ohne diese Normalisierung waere jeder
 * pluralisierte Schluessel eine Waise.
 *
 * Suffix-Liste: die CLDR-Pluralkategorien plus `_zero` (i18next-Sonderfall).
 */
const PLURAL_SUFFIX = /_(zero|one|two|few|many|other)$/

function withoutPluralSuffix(key: string): string {
  return key.replace(PLURAL_SUFFIX, '')
}

/**
 * Schluessel, auf die der Code nirgends verweist.
 *
 * Ein Schluessel gilt als benutzt, wenn eines zutrifft:
 * - ein Literal ist exakt der Schluessel oder ein Suffix davon auf Punkt-Grenze,
 * - ein Literal ist ein *Praefix* des Schluessels (Gruppen-Zugriff wie
 *   `t('form.policy', { returnObjects: true })`),
 * - ein dynamischer Praefix deckt ihn ab (auch ab einer inneren Punkt-Grenze).
 *
 * Plural-Suffixe (`_one`, `_other`) werden vorher abgeschnitten — im Code
 * steht die Grundform, i18next waehlt die Variante erst zur Laufzeit.
 *
 * `ignorePrefixes` nimmt Teilbaeume heraus, deren Schluessel per Konstruktion
 * nicht im Code stehen — `common.errors` etwa traegt Wire-Werte der API als
 * Schluessel (ADR-0051), die zur Laufzeit aus der Serverantwort kommen.
 */
export function findOrphanKeys(
  tree: LocaleTree,
  usage: KeyUsage,
  locale: string,
  ignorePrefixes: readonly string[] = [],
): OrphanFinding[] {
  const literals = [...usage.literals].map(withoutPluralSuffix)
  const prefixes = [...usage.prefixes]

  return flattenKeys(tree)
    .filter((key) => !ignorePrefixes.some((p) => isPrefixOnDotBoundary(key, p)))
    .filter((key) => {
      const base = withoutPluralSuffix(key)
      return (
        !literals.some(
          (literal) =>
            isSuffixOnDotBoundary(base, literal) || isPrefixOnDotBoundary(base, literal),
        ) && !prefixes.some((prefix) => coversAsPrefix(base, prefix))
      )
    })
    .map((key) => ({ key, locale }))
    .sort((a, b) => a.key.localeCompare(b.key))
}

/**
 * Teilbaeume, deren Schluessel bewusst nicht im Code auftauchen.
 *
 * `common.errors`: der Schluessel IST der `reason`-Wire-Wert der API-Antwort
 * (ADR-0051). `translateServerError` loest ihn zur Laufzeit aus der Antwort
 * auf — im Code steht nie ein Literal. Die Paritaet dieses Teilbaums haelt
 * `localeParity.test.ts` mit eigener Begruendung.
 */
export const ORPHAN_IGNORE_PREFIXES: readonly string[] = ['common.errors']
