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
  if (raw.includes('://')) {
    return '/'
  }
  return raw
}
