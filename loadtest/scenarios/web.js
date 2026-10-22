// Web-Strecken: T3 Lesemix, T4 Schreibstrecke, T5 Suche, T6 Ingest
// (ADR-0062 §8, Bericht §4.3).
//
//   PROFILE=smoke   je Strecke 1 VU bzw. 1 Suche/s, 30 s (Kurzmodus)
//   PROFILE=load    T3 20 → 100 VUs, T4 5 → 20 Redakteure, T5 5 → 30 req/s
//   PROFILE=ingest  T6: 1 → 5 parallele Uploads a 20 MiB, daneben 10 Lese-VUs
//
// Schreibende Redakteure brauchen je ein eigenes JWT: das Schreiblimit gilt
// je Token (30/min). Die Seed-Datei bringt `editors` je Workspace mit; mehr
// Redakteure als Seed-Eintraege teilen sich Tokens und laufen ins Limit
// (sichtbar als `rate_limited`, nicht als Fehler).
//
// T6: Ziel ist kein OOM im api-Container (Deckel 1g) und ein Lesemix daneben
// unter dem Doppelten der Basislinie (`READ_P95_LIMIT`, Default 600 ms =
// 2 × 300 ms). Container-Speicher waehrend des Laufs mitschreiben (README).
// Ohne konfigurierten Blob-Store zaehlt der Ingest als `skipped`.

import {
  SUMMARY_TREND_STATS,
  ingestFlow,
  readMix,
  searchFlow,
  selectProfile,
  sloThresholds,
  writeFlow,
} from '../lib/common.js'

const DURATION = __ENV.DURATION || '30s'
const PROFILE = __ENV.PROFILE || 'smoke'

const PROFILES = {
  smoke: {
    t3_read: { executor: 'constant-vus', exec: 'read', vus: 1, duration: DURATION },
    t4_write: { executor: 'constant-vus', exec: 'write', vus: 1, duration: DURATION },
    t5_search: {
      // Suche hat keine Denkzeit (Arrival-Rate): im Kurzmodus 1 Suche/s.
      executor: 'constant-arrival-rate',
      exec: 'search',
      rate: 1,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: 1,
    },
    t6_ingest: { executor: 'constant-vus', exec: 'ingest', vus: 1, duration: DURATION },
  },
  load: {
    t3_read: {
      executor: 'ramping-vus',
      exec: 'read',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 20 },
        { duration: '4m', target: 20 },
        { duration: '2m', target: 100 },
        { duration: '5m', target: 100 },
        { duration: '1m', target: 0 },
      ],
    },
    t4_write: {
      executor: 'ramping-vus',
      exec: 'write',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 5 },
        { duration: '4m', target: 5 },
        { duration: '2m', target: 20 },
        { duration: '5m', target: 20 },
        { duration: '1m', target: 0 },
      ],
    },
    t5_search: {
      executor: 'ramping-arrival-rate',
      exec: 'search',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 20,
      maxVUs: 120,
      stages: [
        { duration: '5m', target: 5 },
        { duration: '2m', target: 30 },
        { duration: '5m', target: 30 },
        { duration: '1m', target: 0 },
      ],
    },
  },
  ingest: {
    t6_ingest: {
      executor: 'ramping-vus',
      exec: 'ingest',
      startVUs: 1,
      stages: [
        { duration: '3m', target: 1 },
        { duration: '1m', target: 5 },
        { duration: '5m', target: 5 },
        { duration: '30s', target: 0 },
      ],
    },
    t6_read: { executor: 'constant-vus', exec: 'read', vus: 10, duration: '10m' },
  },
}

// Ingest selbst hat kein SLO; bei T6 zaehlt die Wirkung auf den Lesemix.
function thresholdsFor(profile) {
  if (profile !== 'ingest') return sloThresholds(['read', 'write', 'activate', 'search'])
  const extra =
    __ENV.THRESHOLDS === 'off'
      ? {}
      : { 'http_req_duration{kind:read}': [`p(95)<${__ENV.READ_P95_LIMIT || 600}`] }
  return sloThresholds([], extra)
}

export const options = {
  scenarios: selectProfile(PROFILES),
  thresholds: thresholdsFor(PROFILE),
  summaryTrendStats: SUMMARY_TREND_STATS,
}

export function read() {
  readMix()
}

export function write() {
  writeFlow()
}

export function search() {
  searchFlow()
}

export function ingest() {
  ingestFlow()
}
