import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import ErrorBoundary from '../components/ErrorBoundary'

const Bomb = ({ triggered }) => {
  if (triggered) {
    throw new Error('bomb detonated')
  }
  return <div>child tree</div>
}

describe('ErrorBoundary', () => {
  it('renders children when no error thrown', () => {
    render(
      <ErrorBoundary>
        <Bomb triggered={false} />
      </ErrorBoundary>
    )
    expect(screen.getByText('child tree')).toBeTruthy()
  })

  it('renders fallback UI when a child throws', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <ErrorBoundary>
        <Bomb triggered />
      </ErrorBoundary>
    )
    expect(screen.getByRole('alert')).toBeTruthy()
    expect(screen.getByText(/Something went wrong/i)).toBeTruthy()
    expect(screen.getByText(/bomb detonated/i)).toBeTruthy()
    errorSpy.mockRestore()
  })

  it('exposes a reset button in the fallback UI', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <ErrorBoundary>
        <Bomb triggered />
      </ErrorBoundary>
    )
    const retry = screen.getByRole('button', { name: /Try again/i })
    expect(retry).toBeTruthy()
    expect(() => fireEvent.click(retry)).not.toThrow()
    errorSpy.mockRestore()
  })
})
