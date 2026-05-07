import { act } from 'react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { fireEvent, render, screen } from '@testing-library/react'
import HeadCoachDashboard from '../pages/HeadCoachDashboard'

vi.mock('../utils/auth', () => ({
  getCurrentUser: () => ({ id: 1, username: '117_HeadCoachGM', user_type: 'head_coach' }),
}))

vi.mock('../services/api', () => ({
  deleteHeadAthlete: vi.fn(),
  deleteHeadCoach: vi.fn(),
  deleteHeadStaff: vi.fn(),
  getHeadOrgSummary: vi.fn(),
  getHeadOrgRoster: vi.fn(),
  getHeadModelStatus: vi.fn(),
  getHeadProgramStyleOutcomes: vi.fn(),
  getHeadProgramNameOutcomes: vi.fn(),
  getHeadRecommendations: vi.fn(),
  patchHeadAthletePrimaryCoach: vi.fn(),
  patchHeadAthleteSkillTeam: vi.fn(),
  patchHeadCoachCategory: vi.fn(),
  patchHeadStaffAssignment: vi.fn(),
  postHeadStaffInvite: vi.fn(),
}))

import {
  getHeadOrgSummary,
  getHeadOrgRoster,
  getHeadModelStatus,
  getHeadProgramStyleOutcomes,
  getHeadProgramNameOutcomes,
  getHeadRecommendations,
  postHeadStaffInvite,
} from '../services/api'

describe('HeadCoachDashboard UAT 3 shell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getHeadOrgSummary.mockResolvedValue({ coaches: [{ id: 1, username: '117_HeadCoachGM', user_type: 'head_coach', athlete_count: 1, program_count: 1, personal_record_count: 1, workout_log_count: 1 }] })
    getHeadOrgRoster.mockResolvedValue({
      head_coaches: [
        { id: 1, username: '117_HeadCoachGM', user_type: 'head_coach', org_prefix: '117', org_label: '117_MASTER_CHIEF', org_color_key: 'sage-green' },
        { id: 4, username: '001_HeadCoach_one', user_type: 'head_coach', org_prefix: '001', org_label: '001_INFINITY', org_color_key: 'gun-silver', owned_lane_prefixes: ['001'] },
      ],
      staff: [
        { id: 2, username: '008_Coach_eight', user_type: 'coach', reports_to_id: 1, reports_to_username: '117_HeadCoachGM', org_prefix: '117', org_label: '117_MASTER_CHIEF', org_color_key: 'sage-green' },
        { id: 5, username: '013_Coach_onethree', user_type: 'coach', reports_to_id: 4, reports_to_username: '001_HeadCoach_one', org_prefix: '001', org_label: '001_INFINITY', org_color_key: 'gun-silver' },
      ],
      athletes: [
        { id: 3, username: '000_Athlete_zero', primary_coach_id: 2, primary_coach_username: '008_Coach_eight', org_prefix: '117', org_label: '117_MASTER_CHIEF', org_color_key: 'sage-green', skill_team: 'NOBLE' },
        { id: 6, username: '009_Athlete_nine', primary_coach_id: 5, primary_coach_username: '013_Coach_onethree', org_prefix: '001', org_label: '001_INFINITY', org_color_key: 'gun-silver', skill_team: 'BLUE' },
      ],
    })
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

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders role-aware workspace tabs', async () => {
    render(
      <MemoryRouter>
        <HeadCoachDashboard />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('heading', { name: /GM Head Coach command center/i })).toBeTruthy()
    expect(screen.getByRole('tab', { name: /GM Head Coach/i })).toBeTruthy()
    expect(screen.getByRole('tab', { name: /Line Coach/i })).toBeTruthy()
    expect(screen.getByRole('tab', { name: /Schedule/i })).toBeTruthy()
    expect(screen.getByRole('tab', { name: /Settings/i })).toBeTruthy()
  })

  it('opens settings and schedule MVP panels', async () => {
    render(
      <MemoryRouter>
        <HeadCoachDashboard />
      </MemoryRouter>,
    )
    fireEvent.click(await screen.findByRole('tab', { name: /Settings/i }))
    expect(screen.getByRole('heading', { name: /Settings/i })).toBeTruthy()
    expect(screen.getByText(/Coach certifications/i)).toBeTruthy()

    fireEvent.click(screen.getByRole('tab', { name: /Schedule/i }))
    expect(screen.getByRole('heading', { name: /Schedule/i })).toBeTruthy()
    expect(screen.getByText(/Weekly outlook/i)).toBeTruthy()
  })

  it('populates assigned AGM category tabs', async () => {
    render(
      <MemoryRouter>
        <HeadCoachDashboard />
      </MemoryRouter>,
    )
    fireEvent.click(await screen.findByRole('tab', { name: /001_INFINITY/i }))
    expect(screen.getAllByText(/@001_HeadCoach_one/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/@013_Coach_onethree/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/@009_Athlete_nine/i).length).toBeGreaterThan(0)
  })

  it('renders athletes grouped by skill team labels', async () => {
    render(
      <MemoryRouter>
        <HeadCoachDashboard />
      </MemoryRouter>,
    )

    expect((await screen.findAllByText(/NOBLE TEAM/i)).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/BLUE TEAM/i).length).toBeGreaterThan(0)
    expect(screen.getByLabelText(/Skill team for 000_Athlete_zero/i)).toBeTruthy()
    expect(screen.getByLabelText(/Accountable coach for 000_Athlete_zero/i)).toBeTruthy()
  })

  it('shows assignment feedback as a hover-pausable toast', async () => {
    vi.useFakeTimers()
    postHeadStaffInvite.mockResolvedValue({ id: 99, username: 'new_line' })

    render(
      <MemoryRouter>
        <HeadCoachDashboard />
      </MemoryRouter>,
    )

    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    fireEvent.change(screen.getByPlaceholderText(/Line coach username/i), {
      target: { value: 'new_line' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Add to org/i }))

    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    const toast = screen.getByRole('status')
    expect(toast.textContent).toContain('Linked @new_line.')

    fireEvent.mouseEnter(toast)
    act(() => {
      vi.advanceTimersByTime(7000)
    })
    expect(screen.getByRole('status')).toBeTruthy()

    fireEvent.mouseLeave(toast)
    act(() => {
      vi.advanceTimersByTime(4500)
    })
    expect(screen.queryByRole('status')).toBeNull()
  })
})

