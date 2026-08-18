import { appConfig } from './config'

export type UploadState = 'pending' | 'uploaded' | 'invalid'
export type JobState = 'queued' | 'validating' | 'analyzing' | 'rendering' | 'uploading' | 'completed' | 'failed' | 'cancelled'
export type JobStage = JobState
export type AspectRatio = '16:9' | '9:16'
export type Profile = 'tight' | 'balanced' | 'safe' | 'full_movement'

export interface Project { id: string; name: string; created_at: string }
export interface Asset {
  id: string; project_id: string; kind: 'source' | 'output' | 'debug'; upload_state: UploadState
  storage_key?: string; width?: number; height?: number; frame_rate?: number; duration_ms?: number; created_at: string
}
export interface UploadRequest { asset: Asset; upload_url: string; expires_at?: string }
export interface TargetSelection { frame_time_ms: number; normalized_x: number; normalized_y: number }
export interface OutputSettings { aspect_ratio: AspectRatio; profile: Profile }
export interface JobConfiguration { target_selection: TargetSelection; output: OutputSettings; pipeline_version?: string; model_version?: string }
export interface SafeError { code?: string; message: string }
export interface Job {
  id: string; project_id: string; source_asset_id: string; state: JobState; stage: JobStage; progress: number
  configuration: JobConfiguration; output_asset_id?: string | null; error?: SafeError | null
  created_at: string; started_at?: string | null; completed_at?: string | null
}

export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  constructor(message: string, status: number, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

const apiBase = appConfig.api_base_url.replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  } catch {
    throw new ApiError('The API is unavailable. Check the service and try again.', 0)
  }
  const body = await response.json().catch(() => null) as { message?: string; error?: SafeError } | null
  if (!response.ok) throw new ApiError(body?.error?.message ?? body?.message ?? `Request failed (${response.status})`, response.status, body?.error?.code)
  return body as T
}

export const api = {
  createProject(name: string) {
    return request<Project>('/api/v1/projects', { method: 'POST', body: JSON.stringify({ name }) })
  },
  requestUpload(projectId: string, file: File) {
    return request<UploadRequest>(`/api/v1/projects/${projectId}/assets/upload`, { method: 'POST', body: JSON.stringify({
      kind: 'source', filename: file.name, content_type: file.type || 'video/mp4', size_bytes: file.size,
    }) })
  },
  confirmUpload(assetId: string) {
    return request<Asset>(`/api/v1/assets/${assetId}/complete`, { method: 'POST' })
  },
  createJob(projectId: string, sourceAssetId: string, targetSelection: TargetSelection, output: OutputSettings) {
    return request<Job>(`/api/v1/projects/${projectId}/jobs`, { method: 'POST', body: JSON.stringify({ source_asset_id: sourceAssetId, target_selection: targetSelection, output }) })
  },
  getJob(jobId: string) { return request<Job>(`/api/v1/jobs/${jobId}`) },
  getDownloadUrl(jobId: string) { return request<{ download_url: string }>(`/api/v1/jobs/${jobId}/download`) },
}

export function uploadFile(url: string, file: File, onProgress: (value: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', url)
    xhr.setRequestHeader('Content-Type', file.type || 'video/mp4')
    xhr.upload.onprogress = (event) => { if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100)) }
    xhr.onerror = () => reject(new ApiError('The source upload failed. Check your connection and retry.', 0))
    xhr.onload = () => xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new ApiError('The source upload was rejected. Retry the upload.', xhr.status))
    xhr.send(file)
  })
}
