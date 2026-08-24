import { describe, expect, it, vi } from 'vitest'
import { api, ApiError, sourceContentType } from './api'
import { evaluationResponseFixture } from './fixtures/evaluation'

describe('API client contract', () => {
  it('uses QuickTime MIME type for iCloud MOV files', () => {
    expect(sourceContentType(new File(['video'], 'session.MOV', { type: '' }))).toBe('video/quicktime')
    expect(sourceContentType(new File(['video'], 'session.mp4', { type: 'video/mp4' }))).toBe('video/mp4')
  })
  it('serializes the documented job request and route', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'job-1', state: 'queued' }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    await api.createJob('project-1', 'asset-1', { frame_time_ms: 1250, normalized_x: 0.25, normalized_y: 0.75 }, { aspect_ratio: '9:16', profile: 'full_movement' })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/projects/project-1/jobs', expect.objectContaining({ method: 'POST', body: JSON.stringify({ source_asset_id: 'asset-1', target_selection: { frame_time_ms: 1250, normalized_x: 0.25, normalized_y: 0.75 }, output: { aspect_ratio: '9:16', profile: 'full_movement' } }) }))
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get('X-Trace-ID')).toMatch(/^[0-9a-f-]{36}$/)
  })
  it('preserves the signed upload URL from the API response', async () => {
    const uploadUrl = 'http://storage.test/bucket/source.mp4?signature=redacted'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ upload_url: uploadUrl }), { status: 201 })))

    const response = await api.requestUpload('project-1', new File(['video'], 'source.mp4', { type: 'video/mp4' }))

    expect(response.upload_url).toBe(uploadUrl)
  })
  it('exposes safe API errors without leaking response details', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'asset_not_uploaded', message: 'Upload the source first.' } }), { status: 409 })))
    await expect(api.confirmUpload('asset-1')).rejects.toMatchObject({ name: 'ApiError', status: 409, code: 'asset_not_uploaded', message: 'Upload the source first.' } satisfies Partial<ApiError>)
  })
  it('accepts the worker/backend-compatible evaluation schema and redacts signed URLs from logs', async () => {
    const signedURL = evaluationResponseFixture.phases![0].video_url!
    const info = vi.spyOn(console, 'info').mockImplementation(() => undefined)
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(evaluationResponseFixture), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const evaluation = await api.getEvaluation('job-1')

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/jobs/job-1/evaluation', expect.any(Object))
    expect(evaluation.phases?.[0].video_url).toBe(signedURL)
    expect(evaluation.phases?.[1].warning_intervals).toEqual([{ start_ms: 4200, end_ms: 5900, label: 'Low confidence', detail: 'Pose landmarks were intermittently unavailable.' }])
    expect(evaluation.expires_in_seconds).toBe(900)
    expect(info.mock.calls.flat().join(' ')).not.toContain(signedURL)
  })
  it('gets fresh evaluation URLs by repeating the explicit request', async () => {
    const first = 'https://storage.test/first.mp4?signature=old'
    const fresh = 'https://storage.test/second.mp4?signature=fresh'
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...evaluationResponseFixture, phases: evaluationResponseFixture.phases!.map((phase) => phase.id === 'measurement' ? { ...phase, video_url: first } : phase) }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...evaluationResponseFixture, phases: evaluationResponseFixture.phases!.map((phase) => phase.id === 'measurement' ? { ...phase, video_url: fresh } : phase) }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await api.getEvaluation('job-1')
    const reopened = await api.getEvaluation('job-1')

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(reopened.phases?.[0].video_url).toContain('signature=fresh')
  })
  it('keeps a telemetry-only terminal review unavailable without exposing a workspace', async () => {
    const telemetryURL = 'https://storage.test/review/telemetry.jsonl.gz?signature=private'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ available: false, telemetry_download_url: telemetryURL, expires_in_seconds: 900 }), { status: 200 })))

    await expect(api.getEvaluation('job-1')).resolves.toEqual({ available: false, telemetry_download_url: telemetryURL, expires_in_seconds: 900 })
  })
  it.each([
    ['missing phases', { available: true, review_id: 'review-1', state: 'completed' }],
    ['out-of-order phase', { ...evaluationResponseFixture, phases: [...evaluationResponseFixture.phases!].reverse() }],
    ['ready phase without media', { ...evaluationResponseFixture, phases: evaluationResponseFixture.phases!.map((phase) => phase.id === 'render' ? { ...phase, video_url: undefined } : phase) }],
    ['unavailable phase URL', { ...evaluationResponseFixture, phases: evaluationResponseFixture.phases!.map((phase) => phase.id === 'planning' ? { ...phase, video_url: 'https://storage.test/review/planning.mp4?signature=private' } : phase) }],
    ['missing manifest timing', { ...evaluationResponseFixture, timing: undefined }],
    ['unsafe model version', { ...evaluationResponseFixture, model_version: 'https://storage.test/model?signature=private' }],
    ['oversized phase detail', { ...evaluationResponseFixture, phases: evaluationResponseFixture.phases!.map((phase) => phase.id === 'planning' ? { ...phase, detail: 'x'.repeat(501) } : phase) }],
  ])('rejects malformed evaluation payloads: %s without logging signed URLs', async (_, response) => {
    const signedURL = 'https://storage.test/review/render.mp4?signature=private'
    const info = vi.spyOn(console, 'info').mockImplementation(() => undefined)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...response, telemetry_download_url: signedURL }), { status: 200 })))

    await expect(api.getEvaluation('job-1')).rejects.toMatchObject({ name: 'ApiError', status: 200, code: 'invalid_evaluation_response', message: 'The review response was invalid. Refresh the review or try again later.' } satisfies Partial<ApiError>)

    expect(info.mock.calls.flat().join(' ')).not.toContain(signedURL)
  })
})
