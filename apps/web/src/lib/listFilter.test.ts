import { describe, expect, it } from 'vitest'

import {
  countByStatus,
  isStatusFilterValue,
  matchesStatusFilter,
  needsAttention,
  type StatusLike,
} from './listFilter'

const draft: StatusLike = { status: 'draft', hasPendingDraft: false }
const review: StatusLike = { status: 'review', hasPendingDraft: false }
const active: StatusLike = { status: 'active', hasPendingDraft: false }
const activeWithDraft: StatusLike = { status: 'active', hasPendingDraft: true }
const inactive: StatusLike = { status: 'inactive', hasPendingDraft: false }

describe('needsAttention', () => {
  it('markiert Draft, Review und Active-mit-offenem-Draft', () => {
    expect(needsAttention(draft)).toBe(true)
    expect(needsAttention(review)).toBe(true)
    expect(needsAttention(activeWithDraft)).toBe(true)
  })

  it('ignoriert saubere Active und Inactive', () => {
    expect(needsAttention(active)).toBe(false)
    expect(needsAttention(inactive)).toBe(false)
  })
})

describe('matchesStatusFilter', () => {
  it('all passt immer', () => {
    expect(matchesStatusFilter(inactive, 'all')).toBe(true)
  })

  it('exakter Status matcht', () => {
    expect(matchesStatusFilter(review, 'review')).toBe(true)
    expect(matchesStatusFilter(review, 'active')).toBe(false)
  })

  it('attention nutzt die abgeleitete Regel', () => {
    expect(matchesStatusFilter(activeWithDraft, 'attention')).toBe(true)
    expect(matchesStatusFilter(active, 'attention')).toBe(false)
  })
})

describe('countByStatus', () => {
  it('zaehlt all, attention und je Status', () => {
    const counts = countByStatus([draft, review, active, activeWithDraft, inactive])
    expect(counts.all).toBe(5)
    // draft + review + activeWithDraft
    expect(counts.attention).toBe(3)
    expect(counts.draft).toBe(1)
    expect(counts.review).toBe(1)
    expect(counts.active).toBe(2)
    expect(counts.inactive).toBe(1)
  })

  it('vertraegt fehlenden Status', () => {
    const counts = countByStatus([{ status: undefined, hasPendingDraft: undefined }])
    expect(counts.all).toBe(1)
    expect(counts.attention).toBe(0)
    expect(counts.draft).toBe(0)
  })
})

describe('isStatusFilterValue', () => {
  it('akzeptiert gueltige, verwirft ungueltige Werte', () => {
    expect(isStatusFilterValue('attention')).toBe(true)
    expect(isStatusFilterValue('review')).toBe(true)
    expect(isStatusFilterValue('bogus')).toBe(false)
  })
})
