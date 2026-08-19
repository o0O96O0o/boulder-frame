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

export function sourceContentType(file: File): 'video/mp4' | 'video/quicktime' {
  return file.name.toLowerCase().endsWith('.mov') ? 'video/quicktime' : 'video/mp4'
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
const maxLoggedBodyCharacters = 64 * 1024

function traceId(): string {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  const bytes = new Uint8Array(16)
  if (globalThis.crypto?.getRandomValues) globalThis.crypto.getRandomValues(bytes)
  else for (let index = 0; index < bytes.length; index += 1) bytes[index] = Math.floor(Math.random() * 256)
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  return [...bytes].map((value, index) => `${[4, 6, 8, 10].includes(index) ? '-' : ''}${value.toString(16).padStart(2, '0')}`).join('')
}

function sanitizeLogValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitizeLogValue)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => {
      const lower = key.toLowerCase()
      return [key, /url|token|secret|password|authorization|cookie/.test(lower) ? '[REDACTED]' : sanitizeLogValue(item)]
    }))
  }
  return value
}

function parseBody(value: unknown): unknown {
  if (typeof value !== 'string' || value.length === 0) return value ?? null
  if (value.length > maxLoggedBodyCharacters) return { omitted: true, reason: 'body_too_large' }
  try { return sanitizeLogValue(JSON.parse(value)) } catch { return { omitted: true, reason: 'non_json_body' } }
}

function logRequest(event: string, fields: Record<string, unknown>): void {
  console.info(JSON.stringify({ module: 'frontend', event, ...fields }))
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const trace = new Headers(init?.headers)
  const id = trace.get('X-Trace-ID') ?? traceId()
  trace.set('X-Trace-ID', id)
  if (!trace.has('Content-Type')) trace.set('Content-Type', 'application/json')
  const requestBody = typeof init?.body === 'string' ? parseBody(init.body) : init?.body ? { omitted: true, reason: 'non_json_body' } : null
  logRequest('http request', { 'trace-id': id, method: init?.method ?? 'GET', path, request_body: requestBody })
  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, { ...init, headers: trace })
  } catch {
    logRequest('http response', { 'trace-id': id, status: 0, response_body: { omitted: true, reason: 'network_error' } })
    throw new ApiError('The API is unavailable. Check the service and try again.', 0)
  }
  const rawBody = await response.text()
  const body = parseBody(rawBody) as { message?: string; error?: SafeError } | null
  logRequest('http response', { 'trace-id': response.headers.get('X-Trace-ID') ?? id, status: response.status, response_body: body })
  if (!response.ok) throw new ApiError(body?.error?.message ?? body?.message ?? `Request failed (${response.status})`, response.status, body?.error?.code)
  return body as T
}

export const api = {
  createProject(name: string) {
    return request<Project>('/api/v1/projects', { method: 'POST', body: JSON.stringify({ name }) })
  },
  requestUpload(projectId: string, file: File) {
    return request<UploadRequest>(`/api/v1/projects/${projectId}/assets/upload`, { method: 'POST', body: JSON.stringify({
      kind: 'source', filename: file.name, content_type: sourceContentType(file), size_bytes: file.size,
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
    const id = traceId()
    xhr.open('PUT', url)
    xhr.setRequestHeader('Content-Type', sourceContentType(file))
    xhr.setRequestHeader('X-Trace-ID', id)
    logRequest('upload request', { 'trace-id': id, method: 'PUT', path: '[SIGNED_URL]', request_body: { filename: file.name, content_type: sourceContentType(file), size_bytes: file.size } })
    xhr.upload.onprogress = (event) => { if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100)) }
    xhr.onerror = () => {
      logRequest('upload response', { 'trace-id': id, status: 0, response_body: { omitted: true, reason: 'network_error' } })
      reject(new ApiError('The source upload failed. Check your connection and retry.', 0))
    }
    xhr.onload = () => {
      logRequest('upload response', { 'trace-id': id, status: xhr.status, response_body: parseBody(xhr.responseText) })
      return xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new ApiError('The source upload was rejected. Retry the upload.', xhr.status))
    }
    xhr.send(file)
  })
}
