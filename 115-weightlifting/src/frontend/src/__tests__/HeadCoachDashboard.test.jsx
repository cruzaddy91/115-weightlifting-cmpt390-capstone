import { describe, expect, it, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { render, screen } from '@testing-library/react'
import HeadCoachDashboard from '../pages/HeadCoachDashboard'

vi.mock('../utils/auth', () => ({
  getCurrentUser: () => ({ id: 1, username: 'head', user_type: 'head_coach' }),
}))

vi.mock('../services/api', () => ({
  getHeadOrgSummary: vi.fn(),
  getHeadOrgRoster: vi.fn(),
  getHeadModelStatus: vi.fn(),
  getHeadProgramStyleOutcomes: vi.fn(),
  getHeadProgramNameOutcomes: vi.fn(),
  getHeadRecommendations: vi.fn(),
  patchHeadAthletePrimaryCoach: vi.fn(),
  patchHeadStaffLink: vi.fn(),
  postHeadStaffInvite: vi.fn(),
}))

import {
  getHeadOrgSummary,
  getHeadOrgRoster,
  getHeadModelStatus,
  getHeadProgramStyleOutcomes,
  getHeadProgramNameOutcomes,
  getHeadRecommendations,
} from '../services/api'

describe('HeadCoachDashboard analytics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getHeadOrgSummary.mockResolvedValue({ coaches: [] })
    getHeadOrgRoster.mockResolvedValue({ staff: [], athletes: [] })
    getHeadModelStatus.mockResolvedValue({
      mode: 'model',
      has_model_artifact: true,
      latest_model: { version: 'head-recommender-202604240001-a1b2c3', trained_at: '2026-04-24T00:01:00Z' },
    })
    getHeadProgramStyleOutcomes.mockResolvedValue({
      minimum_sample_size: 3,
      groups: [
        {
          style_tag: 'style:strength',
          segment: { gender: 'F', bodyweight_bucket: 'small', weight_class: '59 kg' },
          metrics: { sample_size: 4, completion_rate: 0.75, avg_pr_delta_kg: 3.5 },
        },
      ],
    })
    getHeadProgramNameOutcomes.mockResolvedValue({
      minimum_sample_size: 3,
      groups: [
        { normalized_name: 'peak strength', metrics: { sample_size: 4, completion_rate: 0.8, avg_pr_delta_kg: 4.1 } },
      ],
    })
    getHeadRecommendations.mockResolvedValue({
      minimum_sample_size: 3,
      strategy: 'model',
      model_version: 'head-recommender-202604240001-a1b2c3',
      generated_at: '2026-04-24T00:02:00Z',
      fallback_reason: null,
      recommendations: [
        {
          segment: { gender: 'F', bodyweight_bucket: 'small', weight_class: '59 kg' },
          recommended_style_tag: 'style:strength',
          confidence: { sample_size: 4, effect: { completion_rate: 0.75, avg_pr_delta_kg: 3.5 } },
        },
      ],
    })
  })

  it('renders analytics tables and recommendation cards', async () => {
    render(
      <MemoryRouter>
        <HeadCoachDashboard />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('heading', { name: /De-identified analytics/i })).toBeTruthy()
    expect(screen.getByText(/Program style outcomes/i)).toBeTruthy()
    expect(screen.getByText(/peak strength/i)).toBeTruthy()
    expect(screen.getByText(/Segment recommendations/i)).toBeTruthy()
    expect(screen.getByText(/Engine mode/i)).toBeTruthy()
    expect(screen.getAllByText(/^MODEL$/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/style:strength/i).length).toBeGreaterThan(0)
  })
})

