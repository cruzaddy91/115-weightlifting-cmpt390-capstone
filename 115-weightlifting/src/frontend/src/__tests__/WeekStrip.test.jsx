import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import WeekStrip from '../components/WeekStrip'

const days = [
  { id: 'd0', day: 'Monday', exercises: [{}, {}, {}] },
  { id: 'd1', day: 'Tuesday', exercises: [{}, {}] },
  { id: 'd2', day: 'Wednesday', exercises: [] },
]

describe('WeekStrip', () => {
  it('renders one cell per day with abbreviated label and ratio', () => {
    render(
      <WeekStrip
        days={days}
        completionCounts={{
          d0: { completed: 2, total: 3 },
          d1: { completed: 2, total: 2 },
          d2: { completed: 0, total: 0 },
        }}
        selectedDayId="d0"
        onSelectDay={() => {}}
      />
    )
    expect(screen.getByText('MON')).toBeTruthy()
    expect(screen.getByText('TUE')).toBeTruthy()
    expect(screen.getByText('WED')).toBeTruthy()
    expect(screen.getByText('2/3')).toBeTruthy()
    expect(screen.getByText('2/2')).toBeTruthy()
  })

  it('marks the selected cell with aria-selected=true', () => {
    render(
      <WeekStrip
        days={days}
        completionCounts={{}}
        selectedDayId="d1"
        onSelectDay={() => {}}
      />
    )
    const cells = screen.getAllByRole('tab')
    expect(cells[0].getAttribute('aria-selected')).toBe('false')
    expect(cells[1].getAttribute('aria-selected')).toBe('true')
    expect(cells[2].getAttribute('aria-selected')).toBe('false')
  })

  it('calls onSelectDay with the clicked day id', () => {
    const onSelectDay = vi.fn()
    render(
      <WeekStrip
        days={days}
        completionCounts={{}}
        selectedDayId="d0"
        onSelectDay={onSelectDay}
      />
    )
    fireEvent.click(screen.getByText('TUE'))
    expect(onSelectDay).toHaveBeenCalledWith('d1')
  })

  it('shows is-full state when day is 100% complete', () => {
    const { container } = render(
      <WeekStrip
        days={[{ id: 'd0', day: 'Monday', exercises: [{}, {}] }]}
        completionCounts={{ d0: { completed: 2, total: 2 } }}
        selectedDayId="d0"
        onSelectDay={() => {}}
      />
    )
    expect(container.querySelector('.week-strip-cell.is-full')).toBeTruthy()
  })

  it('falls back to DN labels when day name is missing', () => {
    render(
      <WeekStrip
        days={[{ id: 'd0', day: '', exercises: [] }]}
        completionCounts={{}}
        selectedDayId="d0"
        onSelectDay={() => {}}
      />
    )
    expect(screen.getByText('D1')).toBeTruthy()
  })
})
