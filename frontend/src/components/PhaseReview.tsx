import { useEffect, useRef, useState } from 'react'
import type { Evaluation, EvaluationPhase, EvaluationWarningInterval } from '../api'

function formatTime(milliseconds: number) {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

function formatSummaryValue(value: string | number | boolean | null) {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (value === null) return 'Unavailable'
  return String(value)
}

function phaseIntervals(phase: EvaluationPhase, evaluation: Evaluation): EvaluationWarningInterval[] {
  return phase.warning_intervals ?? evaluation.warning_intervals ?? []
}

export function PhaseReview({ evaluation, onClose, onRefresh, refreshing = false }: { evaluation: Evaluation; onClose: () => void; onRefresh: () => void; refreshing?: boolean }) {
  const initialPhase = evaluation.phases?.find((phase) => phase.video_url) ?? evaluation.phases?.[0] ?? null
  const [selectedID, setSelectedID] = useState(initialPhase?.id ?? null)
  const [mediaError, setMediaError] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const timestampRef = useRef(0)
  const selectedPhase = evaluation.phases?.find((phase) => phase.id === selectedID) ?? initialPhase

  useEffect(() => {
    setSelectedID(initialPhase?.id ?? null)
    timestampRef.current = 0
  }, [evaluation.review_id])

  useEffect(() => {
    setMediaError(false)
  }, [selectedID, selectedPhase?.video_url])

  function selectPhase(phase: EvaluationPhase) {
    if (videoRef.current && Number.isFinite(videoRef.current.currentTime) && videoRef.current.currentTime > 0) timestampRef.current = videoRef.current.currentTime
    setMediaError(false)
    setSelectedID(phase.id)
  }

  function restoreTimestamp() {
    const video = videoRef.current
    if (!video || timestampRef.current <= 0) return
    video.currentTime = Math.min(timestampRef.current, Number.isFinite(video.duration) ? video.duration : timestampRef.current)
  }

  function seek(interval: EvaluationWarningInterval) {
    const video = videoRef.current
    if (!video) return
    const timestamp = interval.start_ms / 1000
    timestampRef.current = timestamp
    video.currentTime = timestamp
    void video.play().catch(() => undefined)
  }

  if (!evaluation.available) return <section className="card review-empty" aria-live="polite"><div className="card-index">RV</div><div className="card-body"><span className="micro-label">PROCESSING REVIEW</span><h3>No review evidence available</h3><p>This job has no optional diagnostic review run.</p><button className="secondary" onClick={onClose}>Close review</button></div></section>
  if (!selectedPhase) return <section className="card review-empty" aria-live="polite"><div className="card-index">RV</div><div className="card-body"><span className="micro-label">PROCESSING REVIEW</span><h3>Review evidence is incomplete</h3><p>No review phases were available for this job.</p><button className="secondary" onClick={onClose}>Close review</button></div></section>

  const intervals = phaseIntervals(selectedPhase, evaluation)
  return <section className="card phase-review" aria-label="Review processing"><div className="card-index">RV</div><div className="card-body"><div className="review-heading"><div><span className="micro-label">PROCESSING REVIEW</span><h3>Review processing</h3></div><button className="text-button" onClick={onClose}>Close</button></div><div className="phase-rail" aria-label="Review phases">{evaluation.phases?.map((phase) => <button key={phase.id} className={`phase-tab ${selectedPhase.id === phase.id ? 'active' : ''} ${phase.status}`} aria-label={`${phase.label} (${phase.status})`} aria-pressed={selectedPhase.id === phase.id} onClick={() => selectPhase(phase)}><span>{phase.label}</span><i>{phase.status}</i></button>)}</div><div className="review-layout"><div className="review-video-panel">{selectedPhase.video_url ? <><video data-testid="review-video" ref={videoRef} key={selectedPhase.id} src={selectedPhase.video_url} controls playsInline onError={() => setMediaError(true)} onLoadedMetadata={restoreTimestamp} onTimeUpdate={(event) => { timestampRef.current = event.currentTarget.currentTime }} />{mediaError && <div className="review-media-error" role="alert"><span>We could not load this review video. Its access link may have expired.</span><button className="secondary" onClick={onRefresh} disabled={refreshing}>{refreshing ? 'Refreshing review…' : 'Refresh review'}</button></div>}</> : <div className="review-unavailable"><strong>{selectedPhase.label} evidence unavailable</strong><span>{selectedPhase.detail ?? 'This phase was not captured for this review run.'}</span></div>}<div className="review-legend"><strong>{selectedPhase.label}</strong><span>{selectedPhase.status === 'warning' ? 'Warnings are marked in the rendered phase video.' : 'Overlays are rendered by the processing worker.'}</span></div></div><aside className="review-details"><div><span className="micro-label">PHASE STATUS</span><p className={`phase-status ${selectedPhase.status}`}>{selectedPhase.status}</p></div>{selectedPhase.summary && <div><span className="micro-label">SUMMARY</span><dl className="review-summary">{Object.entries(selectedPhase.summary).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{formatSummaryValue(value)}</dd></div>)}</dl></div>}{intervals.length > 0 && <div><span className="micro-label">WARNING INTERVALS</span><div className="warning-list">{intervals.map((interval, index) => <button key={`${interval.start_ms}-${index}`} onClick={() => seek(interval)}><strong>{formatTime(interval.start_ms)}{interval.end_ms != null && ` - ${formatTime(interval.end_ms)}`}</strong><span>{interval.label}{interval.detail ? `: ${interval.detail}` : ''}</span></button>)}</div></div>}{evaluation.telemetry_download_url && <a className="telemetry-link" href={evaluation.telemetry_download_url} target="_blank" rel="noreferrer">Export telemetry <span>↓</span></a>}</aside></div></div></section>
}
