import { describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'

describe('API client contract', () => {
  it('serializes the documented job request and route', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'job-1', state: 'queued' }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    await api.createJob('project-1', 'asset-1', { frame_time_ms: 1250, normalized_x: 0.25, normalized_y: 0.75 }, { aspect_ratio: '9:16', profile: 'full_movement' })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/projects/project-1/jobs', expect.objectContaining({ method: 'POST', body: JSON.stringify({ source_asset_id: 'asset-1', target_selection: { frame_time_ms: 1250, normalized_x: 0.25, normalized_y: 0.75 }, output: { aspect_ratio: '9:16', profile: 'full_movement' } }) }))
  })
  it('exposes safe API errors without leaking response details', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'asset_not_uploaded', message: 'Upload the source first.' } }), { status: 409 })))
    await expect(api.confirmUpload('asset-1')).rejects.toMatchObject({ name: 'ApiError', status: 409, code: 'asset_not_uploaded', message: 'Upload the source first.' } satisfies Partial<ApiError>)
  })
})
