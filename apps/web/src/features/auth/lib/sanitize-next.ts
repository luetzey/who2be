// Open-Redirect-Schutz: ein gueltiger `next` ist ein In-App-Pfad — beginnt
// mit genau einem `/`, enthaelt keinen Protocol-Marker. Browser interpretieren
// `//evil.com` und `https://evil.com` als externe URL, das wollen wir nach dem
// Login nicht aufrufen.
export function sanitizeNext(raw: string | null): string {
  if (raw === null || raw === '') {
    return '/'
  }
  if (!raw.startsWith('/') || raw.startsWith('//')) {
    return '/'
  }
  // Backslashes verbieten: manche Browser normalisieren `\` zu `/`, sodass
  // `/\evil.com` als protocol-relative `//evil.com` interpretiert wird — der
  // `startsWith('//')`-Check oben greift dann nicht. In-App-Pfade brauchen nie
  // einen Backslash, daher folgenlos.
  if (raw.includes('\\')) {
    return '/'
  }
  if (raw.includes('://')) {
    return '/'
  }
  return raw
}
