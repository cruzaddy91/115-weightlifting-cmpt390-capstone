import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import AthleteExerciseCard from '../components/AthleteExerciseCard'

const snatch = {
  name: 'Snatch',
  sets: '5',
  reps: '2',
  percent_1rm: '75%',
  tempo: '',
  rest: '2min',
  notes: 'Fast turnover',
}

describe('AthleteExerciseCard', () => {
  it('renders the exercise name and a scannable prescription summary', () => {
    render(<AthleteExerciseCard exercise={snatch} result={{}} onSaveResult={() => {}} />)
    expect(screen.getByText('Snatch')).toBeTruthy()
    expect(screen.getByText(/5×2 @ 75%/)).toBeTruthy()
  })

  it('starts collapsed regardless of completion state', () => {
    render(<AthleteExerciseCard exercise={snatch} result={{}} onSaveResult={() => {}} />)
    // Header visible, quick-log fields not yet in the DOM.
    expect(screen.getByText('Snatch')).toBeTruthy()
    expect(screen.queryByLabelText('Actual weight hit')).toBeNull()
    expect(screen.queryByRole('radio', { name: 'Solid' })).toBeNull()
  })

  it('expands on header tap and submits on Mark done', () => {
    const onSaveResult = vi.fn()
    render(<AthleteExerciseCard exercise={snatch}
            result={{ completed: false, result: '', athlete_notes: '' }}
            onSaveResult={onSaveResult} />)

    fireEvent.click(screen.getByText('Snatch'))
    fireEvent.change(screen.getByLabelText('Actual weight hit'), { target: { value: '105kg' } })
    fireEvent.click(screen.getByRole('radio', { name: 'Solid' }))
    fireEvent.click(screen.getByRole('button', { name: /mark done/i }))

    expect(onSaveResult).toHaveBeenCalledTimes(1)
    const payload = onSaveResult.mock.calls[0][0]
    expect(payload.completed).toBe(true)
    expect(payload.result).toBe('105kg')
    expect(payload.athlete_notes.toLowerCase()).toContain('felt: solid')
  })

  it('shows a short hit/feel summary when collapsed and done', () => {
    render(<AthleteExerciseCard
      exercise={snatch}
      result={{ completed: true, result: '110kg', athlete_notes: 'felt: easy — snappy' }}
      onSaveResult={() => {}}
    />)
    // Header should still be visible; card starts collapsed when already done.
    expect(screen.getByText('Snatch')).toBeTruthy()
    expect(screen.getByText('110kg')).toBeTruthy()
    expect(screen.getByText(/felt Easy/i)).toBeTruthy()
  })

  it('Mark not done flips the completed flag back to false', () => {
    const onSaveResult = vi.fn()
    render(<AthleteExerciseCard
      exercise={snatch}
      result={{ completed: true, result: '110kg', athlete_notes: 'felt: solid' }}
      onSaveResult={onSaveResult}
    />)
    // Click the header to expand the completed card
    fireEvent.click(screen.getByText('Snatch'))
    fireEvent.click(screen.getByRole('button', { name: /mark not done/i }))
    const payload = onSaveResult.mock.calls[0][0]
    expect(payload.completed).toBe(false)
  })

  it('re-syncs local inputs when the result prop changes and the card is collapsed', () => {
    const { rerender } = render(
      <AthleteExerciseCard exercise={snatch} result={{}} onSaveResult={() => {}} />,
    )
    // Collapsed by default. Rerender with server-authoritative values.
    rerender(
      <AthleteExerciseCard
        exercise={snatch}
        result={{ completed: true, result: '117kg', athlete_notes: 'felt: solid' }}
        onSaveResult={() => {}}
      />,
    )
    // Collapsed summary should now show the new server value, not stale blank.
    expect(screen.getByText('117kg')).toBeTruthy()
    expect(screen.getByText(/felt Solid/i)).toBeTruthy()
  })
})
