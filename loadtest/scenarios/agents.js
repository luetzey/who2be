// Agenten und Gesamtsystem: T1 Basislinie, T2 MCP-Agenten, T7 Dauerlast,
// T8 Spitze, T9 Bruchpunkt, T10 Teilausfall, T11 Limits
// (ADR-0062 §8, Bericht §4.3). Die Web-Strecken einzeln: scenarios/web.js.
//
//   PROFILE=smoke      1 VU je Strecke + Gesundheit + ein Schreib-Burst, 30 s
//   PROFILE=baseline   T1: 1 VU je Strecke, 5 min → Referenz-p50/p95 je `name`
//   PROFILE=load       T2: 10 → 50 → 100 parallele MCP-Sessions, je 5 min
//   PROFILE=soak       T7: SOAK_VUS (Default 25 = 50 % von 50) gemischt, 1 h
//   PROFILE=spike      T8: 0 → 200 Sessions in 30 s, 2 min halten, Erholung
//   PROFILE=breakpoint T9: Rampe bis Abbruch bei 5xx > 5 % oder p95 > 2 s
//   PROFILE=outage     T10: Lesemix 20 VUs + 10 Agenten, 10 min; waehrenddessen
//                      von Hand `api`, danach `db` neu starten (README)
//   PROFILE=limits     T11: Schreib-Burst ueber 30/min je Token und MCP-Lesen
//                      ueber 60/min (Free-Org, Cloud-Edition): 429, nie 5xx
//
// MCP gemessen als `kind=mcp_session` (initialize, tools/list) und
// `kind=mcp_call` (Werkzeuge). Jeder MCP-Aufruf loest im MCP-Server ein
// `GET /v1/me` gegen die API aus (Bericht H3): API-Last mitlesen. Bei T7 den
// RAM von api und mcp mitschreiben (README): Drift < 1 MiB/min.

import { sleep } from 'k6'

import {
  SUMMARY_TREND_STATS,
  envNumber,
  healthProbe,
  readMix,
  searchFlow,
  selectProfile,
  sloThresholds,
  think,
  writeBurst,
  writeFlow,
} from '../lib/common.js'
import { agentFlow } from '../lib/mcp.js'

const DURATION = __ENV.DURATION || '30s'
const PROFILE = __ENV.PROFILE || 'smoke'

function oneEach(duration) {
  return {
    agents: { executor: 'constant-vus', exec: 'agents', vus: 1, duration },
    read: { executor: 'constant-vus', exec: 'read', vus: 1, duration },
    write: { executor: 'constant-vus', exec: 'write', vus: 1, duration },
    search: { executor: 'constant-vus', exec: 'search', vus: 1, duration },
  }
}

function constant(exec, share, total, duration) {
  return { executor: 'constant-vus', exec, vus: Math.max(1, Math.round(total * share)), duration }
}

function ramp(exec, target, duration) {
  return { executor: 'ramping-vus', exec, startVUs: 0, stages: [{ duration, target }] }
}

const SOAK_VUS = envNumber('SOAK_VUS', 25)
const SOAK_DURATION = __ENV.SOAK_DURATION || '1h'
const BREAKPOINT_VUS = envNumber('BREAKPOINT_VUS', 400)
const BREAKPOINT_DURATION = __ENV.BREAKPOINT_DURATION || '20m'

const PROFILES = {
  smoke: {
    ...oneEach(DURATION),
    health: { executor: 'constant-vus', exec: 'health', vus: 1, duration: DURATION },
    burst: { executor: 'per-vu-iterations', exec: 'burst', vus: 1, iterations: 1 },
  },
  baseline: oneEach('5m'),
  load: {
    t2_agents: {
      executor: 'ramping-vus',
      exec: 'agents',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 10 },
        { duration: '5m', target: 10 },
        { duration: '1m', target: 50 },
        { duration: '5m', target: 50 },
        { duration: '1m', target: 100 },
        { duration: '5m', target: 100 },
        { duration: '1m', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
  },
  // Verteilung grob wie Bericht §4.3: Agenten zuerst, dann Web-Lesen.
  soak: {
    agents: constant('agents', 0.5, SOAK_VUS, SOAK_DURATION),
    read: constant('read', 0.3, SOAK_VUS, SOAK_DURATION),
    write: constant('write', 0.1, SOAK_VUS, SOAK_DURATION),
    search: constant('search', 0.1, SOAK_VUS, SOAK_DURATION),
  },
  spike: {
    t8_spike: {
      executor: 'ramping-vus',
      exec: 'agentsNoThink',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 200 },
        { duration: '2m', target: 200 },
        { duration: '10s', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
    // Erholung (< 2 min): ein einzelner Agent misst nach der Spitze weiter.
    t8_recovery: {
      executor: 'constant-vus',
      exec: 'agents',
      vus: 1,
      startTime: '2m40s',
      duration: '2m',
      tags: { phase: 'recovery' },
    },
  },
  breakpoint: {
    agents: ramp('agentsNoThink', BREAKPOINT_VUS, BREAKPOINT_DURATION),
    read: ramp('read', BREAKPOINT_VUS, BREAKPOINT_DURATION),
  },
  outage: {
    health: { executor: 'constant-vus', exec: 'health', vus: 1, duration: '10m' },
    read: { executor: 'constant-vus', exec: 'read', vus: 20, duration: '10m' },
    agents: { executor: 'constant-vus', exec: 'agents', vus: 10, duration: '10m' },
  },
  limits: {
    burst: { executor: 'per-vu-iterations', exec: 'burst', vus: 1, iterations: 1 },
    mcp_reads: {
      // 5 Werkzeug-Aufrufe je Iteration × 20/min = 100 Lesezugriffe/min
      executor: 'constant-arrival-rate',
      exec: 'agentsNoThink',
      rate: 20,
      timeUnit: '1m',
      duration: '3m',
      preAllocatedVUs: 5,
      startTime: '10s',
    },
  },
}

const ALL_KINDS = ['read', 'write', 'activate', 'search', 'mcp_session', 'mcp_call']
const MCP_HEALTH = { mcp_session_failures: ['rate<0.005'], mcp_tool_errors: ['rate<0.01'] }

function thresholdsFor(profile) {
  // T8: 429/503 in der Spitze sind gewollt; gegen die SLOs zaehlt die Erholung.
  if (profile === 'spike') {
    return {
      'http_req_duration{kind:mcp_call,phase:recovery}': ['p(95)<500'],
      'errors{phase:recovery}': ['rate<0.005'],
    }
  }
  // T9 bricht selbst ab: der Zeitpunkt des Abbruchs ist das Ergebnis.
  if (profile === 'breakpoint') {
    return {
      errors: [{ threshold: 'rate<0.05', abortOnFail: true, delayAbortEval: '30s' }],
      http_req_duration: [{ threshold: 'p(95)<2000', abortOnFail: true, delayAbortEval: '30s' }],
    }
  }
  // T10: Fehler waehrend des Neustarts sind erwartet; das Ergebnis ist die
  // Erholungszeit aus `health_ok` (README).
  if (profile === 'outage') return {}
  // T11: 429 ja, 5xx nie. Werkzeug-Fehler mit Limit-Text sind hier gewollt.
  if (profile === 'limits') return sloThresholds([])
  // T2: zusaetzlich initialize < 300 ms (Bericht §4.3).
  if (profile === 'load') {
    return sloThresholds(['mcp_session', 'mcp_call'], {
      ...MCP_HEALTH,
      'http_req_duration{name:initialize}': ['p(95)<300'],
    })
  }
  return sloThresholds(ALL_KINDS, MCP_HEALTH)
}

export const options = {
  scenarios: selectProfile(PROFILES),
  thresholds: thresholdsFor(PROFILE),
  summaryTrendStats: SUMMARY_TREND_STATS,
}

export function agents() {
  agentFlow()
}

export function agentsNoThink() {
  agentFlow({ thinkBetween: false })
}

export function read() {
  readMix()
}

export function write() {
  writeFlow()
}

export function search() {
  // Gemischte Last = Menschen: nach jeder Suche Denkzeit (in web.js T5 steuert
  // dagegen die Arrival-Rate).
  searchFlow()
  think()
}

export function health() {
  healthProbe()
  sleep(1)
}

export function burst() {
  writeBurst(envNumber('BURST', 35))
}
