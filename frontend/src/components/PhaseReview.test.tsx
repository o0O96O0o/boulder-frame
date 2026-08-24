/** @vitest-environment jsdom */

import { fireEvent, render, screen } from '@testing-library/react'
import { PhaseReview } from './PhaseReview'
import { evaluationResponseFixture } from '../fixtures/evaluation'

const evaluation = evaluationResponseFixture

describe('PhaseReview', () => {
  beforeEach(() => { vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue() })

  it('explains when no review is available', () => {
    render(<PhaseReview evaluation={{ available: false }} onClose={vi.fn()} onRefresh={vi.fn()} />)
    expect(screen.getByText('No review evidence available')).toBeTruthy()
  })

  it('preserves a nonzero timestamp across phase selection and seeks warning intervals', () => {
    render(<PhaseReview evaluation={evaluation} onClose={vi.fn()} onRefresh={vi.fn()} />)
    const video = screen.getByTestId('review-video') as HTMLVideoElement
    Object.defineProperty(video, 'duration', { value: 20, configurable: true })
    Object.defineProperty(video, 'currentTime', { value: 3.5, writable: true, configurable: true })
    fireEvent.timeUpdate(video)

    fireEvent.click(screen.getByRole('button', { name: 'Pose (warning)' }))
    const poseVideo = screen.getByTestId('review-video') as HTMLVideoElement
    Object.defineProperty(poseVideo, 'duration', { value: 20, configurable: true })
    fireEvent.loadedMetadata(poseVideo)
    expect(poseVideo.currentTime).toBe(3.5)

    fireEvent.click(screen.getByRole('button', { name: /0:04 - 0:05/i }))
    expect(poseVideo.currentTime).toBe(4.2)
    expect(screen.getByRole('button', { name: 'Pose (warning)' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.queryByRole('tab')).toBeNull()
  })

  it('plainly displays an unavailable selected phase', () => {
    render(<PhaseReview evaluation={evaluation} onClose={vi.fn()} onRefresh={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Planning (unavailable)' }))
    expect(screen.getByText('Planning evidence unavailable')).toBeTruthy()
    expect(screen.getByText('Planning evidence was not captured for this review run.')).toBeTruthy()
  })

  it('offers a safe refresh when phase media cannot load', () => {
    const onRefresh = vi.fn()
    render(<PhaseReview evaluation={evaluation} onClose={vi.fn()} onRefresh={onRefresh} />)

    fireEvent.error(screen.getByTestId('review-video'))

    expect(screen.getByRole('alert').textContent).toContain('We could not load this review video.')
    fireEvent.click(screen.getByRole('button', { name: 'Refresh review' }))
    expect(onRefresh).toHaveBeenCalledOnce()
  })
})
