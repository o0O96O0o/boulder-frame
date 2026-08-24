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
export type EvaluationPhaseID = 'measurement' | 'pose' | 'tracking' | 'planning' | 'render'
export type EvaluationPhaseStatus = 'ready' | 'partial' | 'unavailable' | 'warning'
export interface EvaluationWarningInterval { start_ms: number; end_ms?: number; label: string; detail?: string }
export interface EvaluationPhase {
  id: EvaluationPhaseID; label: string; status: EvaluationPhaseStatus; summary?: Record<string, string | number | boolean | null>
  detail?: string; video_url?: string; warning_intervals?: EvaluationWarningInterval[]
}
export interface Evaluation {
  available: boolean; review_id?: string; state?: Extract<JobState, 'completed' | 'failed' | 'cancelled'>
  pipeline_version?: string; model_version?: string; timing?: EvaluationTiming
  phases?: EvaluationPhase[]; warning_intervals?: EvaluationWarningInterval[]; telemetry_download_url?: string; expires_in_seconds?: number
}
export interface EvaluationTiming { frame_rate: number; duration_ms: number; frame_count: number }

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
const maxEvaluationDetailCharacters = 500
const evaluationPhaseIDs: EvaluationPhaseID[] = ['measurement', 'pose', 'tracking', 'planning', 'render']
const evaluationPhaseLabels = ['Measurement', 'Pose', 'Tracking', 'Planning', 'Render']
const evaluationPhaseStatuses: EvaluationPhaseStatus[] = ['ready', 'partial', 'unavailable', 'warning']

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

function parseJson(value: string): unknown {
  if (value.length === 0) return null
  try { return JSON.parse(value) } catch { return null }
}

function logRequest(event: string, fields: Record<string, unknown>): void {
  console.info(JSON.stringify({ module: 'frontend', event, ...fields }))
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isBoundedText(value: unknown, maximum: number): value is string {
  return typeof value === 'string' && value.length > 0 && value.length <= maximum
}

function isSafeManifestText(value: unknown, maximum: number): value is string {
  return isBoundedText(value, maximum) && !/\s|:\/\/|www\.|x-amz-|private\/debug\/|access_key|secret|token|password|authorization|credential|signature/i.test(value)
}

function isSafeURL(value: unknown): value is string {
  if (!isBoundedText(value, 16 * 1024)) return false
  try {
    const url = new URL(value)
    return url.protocol === 'https:' || url.protocol === 'http:'
  } catch {
    return false
  }
}

function isSummary(value: unknown): value is EvaluationPhase['summary'] {
  if (!isRecord(value) || Object.keys(value).length > 32) return false
  return Object.entries(value).every(([key, entry]) => /^[a-z][a-z0-9_]{0,63}$/.test(key) &&
    (typeof entry === 'string' && entry.length > 0 && entry.length <= maxEvaluationDetailCharacters || typeof entry === 'number' && Number.isFinite(entry) || typeof entry === 'boolean' || entry === null))
}

function isWarningIntervals(value: unknown): value is EvaluationWarningInterval[] {
  if (!Array.isArray(value) || value.length > 100) return false
  return value.every((interval) => isRecord(interval) && typeof interval.start_ms === 'number' && Number.isInteger(interval.start_ms) && interval.start_ms >= 0 &&
    (interval.end_ms === undefined || typeof interval.end_ms === 'number' && Number.isInteger(interval.end_ms) && interval.end_ms >= interval.start_ms) &&
    isBoundedText(interval.label, 120) && (interval.detail === undefined || isBoundedText(interval.detail, maxEvaluationDetailCharacters)))
}

function isEvaluationTiming(value: unknown): value is EvaluationTiming {
  return isRecord(value) && typeof value.frame_rate === 'number' && Number.isFinite(value.frame_rate) && value.frame_rate > 0 && value.frame_rate <= 1000 &&
    typeof value.duration_ms === 'number' && Number.isInteger(value.duration_ms) && value.duration_ms > 0 && value.duration_ms <= 604800000 &&
    typeof value.frame_count === 'number' && Number.isInteger(value.frame_count) && value.frame_count > 0 && value.frame_count <= 10000000
}

function parseEvaluation(value: unknown): Evaluation {
  if (!isRecord(value) || typeof value.available !== 'boolean') throw new ApiError('The review response was invalid. Refresh the review or try again later.', 200, 'invalid_evaluation_response')
  const expiresInSeconds = value.expires_in_seconds
  if ((value.telemetry_download_url !== undefined && !isSafeURL(value.telemetry_download_url)) ||
    (expiresInSeconds !== undefined && (typeof expiresInSeconds !== 'number' || !Number.isInteger(expiresInSeconds) || expiresInSeconds <= 0))) {
    throw new ApiError('The review response was invalid. Refresh the review or try again later.', 200, 'invalid_evaluation_response')
  }
  if (!value.available) return { available: false, telemetry_download_url: value.telemetry_download_url as string | undefined, expires_in_seconds: expiresInSeconds as number | undefined }
  if (typeof value.review_id !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value.review_id) || !['completed', 'failed'].includes(value.state as string) || !isSafeManifestText(value.pipeline_version, 128) || !isSafeManifestText(value.model_version, 128) || !isEvaluationTiming(value.timing) || !Array.isArray(value.phases) || value.phases.length !== evaluationPhaseIDs.length) {
    throw new ApiError('The review response was invalid. Refresh the review or try again later.', 200, 'invalid_evaluation_response')
  }
  const phases: EvaluationPhase[] = []
  for (const [index, phase] of value.phases.entries()) {
    if (!isRecord(phase) || phase.id !== evaluationPhaseIDs[index] || phase.label !== evaluationPhaseLabels[index] || !evaluationPhaseStatuses.includes(phase.status as EvaluationPhaseStatus) ||
      (phase.summary !== undefined && !isSummary(phase.summary)) || (phase.warning_intervals !== undefined && !isWarningIntervals(phase.warning_intervals)) ||
      (phase.video_url !== undefined && !isSafeURL(phase.video_url)) || (phase.detail !== undefined && (!isBoundedText(phase.detail, maxEvaluationDetailCharacters) || phase.status !== 'unavailable')) ||
      (phase.status === 'unavailable' && phase.video_url !== undefined) || (phase.status !== 'unavailable' && phase.video_url === undefined)) {
      throw new ApiError('The review response was invalid. Refresh the review or try again later.', 200, 'invalid_evaluation_response')
    }
    phases.push({
      id: phase.id as EvaluationPhaseID,
      label: phase.label as string,
      status: phase.status as EvaluationPhaseStatus,
      summary: phase.summary as EvaluationPhase['summary'],
      detail: phase.detail as string | undefined,
      video_url: phase.video_url as string | undefined,
      warning_intervals: phase.warning_intervals as EvaluationWarningInterval[] | undefined,
    })
  }
  return { available: true, review_id: value.review_id, state: value.state as Evaluation['state'], pipeline_version: value.pipeline_version as string, model_version: value.model_version as string, timing: value.timing as EvaluationTiming, phases, telemetry_download_url: value.telemetry_download_url as string | undefined, expires_in_seconds: expiresInSeconds as number | undefined }
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
  const body = parseJson(rawBody) as { message?: string; error?: SafeError } | null
  const responseBody = path.endsWith('/evaluation') ? { omitted: true, reason: 'evaluation_response' } : parseBody(rawBody)
  logRequest('http response', { 'trace-id': response.headers.get('X-Trace-ID') ?? id, status: response.status, response_body: responseBody })
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
  async getEvaluation(jobId: string) { return parseEvaluation(await request<unknown>(`/api/v1/jobs/${jobId}/evaluation`)) },
}

export function uploadFile(url: string, file: File, onProgress: (value: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const id = traceId()
    xhr.open('PUT', url)
    xhr.setRequestHeader('Content-Type', sourceContentType(file))
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
