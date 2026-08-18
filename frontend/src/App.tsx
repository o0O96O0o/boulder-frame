import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { api, ApiError, type AspectRatio, type Asset, type Job, type OutputSettings, type Profile, type Project, type TargetSelection, uploadFile } from './api'
import { appConfig } from './config'
import { mapPointerToNormalized, normalizedToContainPoint } from './coordinates'

const profiles: { value: Profile; label: string; detail: string }[] = [
  { value: 'tight', label: 'Tight', detail: 'Closer framing, stable movement' },
  { value: 'balanced', label: 'Balanced', detail: 'A confident everyday default' },
  { value: 'safe', label: 'Safe', detail: 'Extra room for quick movement' },
  { value: 'full_movement', label: 'Full movement', detail: 'Prioritizes every limb and landing' },
]
const terminalStates = new Set(['completed', 'failed', 'cancelled'])
const stageLabels: Record<string, string> = { queued: 'Queued', validating: 'Checking source', analyzing: 'Finding movement', rendering: 'Rendering crop', uploading: 'Packaging result', completed: 'Ready to download', failed: 'Processing failed', cancelled: 'Cancelled' }
const maxUploadBytes = appConfig.max_upload_bytes
const maxUploadLabel = `${Math.round(maxUploadBytes / 1024 / 1024 / 1024)} GB`

function message(error: unknown) { return error instanceof Error ? error.message : 'Something went wrong. Please retry.' }
function formatDuration(ms?: number) { return ms == null ? 'Duration pending' : `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}` }

export function App() {
  const [project, setProject] = useState<Project | null>(null)
  const [asset, setAsset] = useState<Asset | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [selection, setSelection] = useState<TargetSelection | null>(null)
  const [aspect, setAspect] = useState<AspectRatio>('16:9')
  const [profile, setProfile] = useState<Profile>('balanced')
  const [job, setJob] = useState<Job | null>(null)
  const [projectName, setProjectName] = useState('Saturday session')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])
  useEffect(() => {
    if (!job || terminalStates.has(job.state)) return
    const timer = window.setTimeout(async () => {
      try { setJob(await api.getJob(job.id)) } catch (err) { setError(message(err)) }
    }, 1800)
    return () => window.clearTimeout(timer)
  }, [job])
  useEffect(() => {
    if (job?.state === 'completed') api.getDownloadUrl(job.id).then((result) => setDownloadUrl(result.download_url)).catch((err) => setError(message(err)))
  }, [job?.state, job?.id])

  async function createProject() {
    if (!projectName.trim()) return setError('Give this session a name first.')
    setBusy(true); setError(null)
    try { setProject(await api.createProject(projectName.trim())) } catch (err) { setError(message(err)) } finally { setBusy(false) }
  }
  async function chooseFile(nextFile: File | undefined) {
    if (!nextFile) return
    if (nextFile.type !== 'video/mp4' || nextFile.size > maxUploadBytes) return setError(`Choose an MP4 video smaller than ${maxUploadLabel}.`)
    setFile(nextFile); setSelection(null); setError(null); setUploadProgress(0); setAsset(null); setJob(null); setDownloadUrl(null)
    setPreviewUrl(URL.createObjectURL(nextFile))
    if (!project) return
    setBusy(true)
    try {
      const signed = await api.requestUpload(project.id, nextFile)
      await uploadFile(signed.upload_url, nextFile, setUploadProgress)
      const uploaded = await api.confirmUpload(signed.asset.id)
      if (uploaded.upload_state !== 'uploaded') throw new Error('The API did not confirm this asset as uploaded.')
      setAsset(uploaded)
    } catch (err) { setError(message(err)); setUploadProgress(0) } finally { setBusy(false) }
  }
  function selectAthlete(event: MouseEvent<HTMLVideoElement>) {
    const video = videoRef.current
    if (!video) return
    const width = asset?.width || video.videoWidth
    const height = asset?.height || video.videoHeight
    if (!width || !height) return
    const rect = video.getBoundingClientRect()
    const point = mapPointerToNormalized(event.clientX, event.clientY, { left: rect.left, top: rect.top, width: rect.width, height: rect.height }, width, height)
    if (point) setSelection({ frame_time_ms: Math.round(video.currentTime * 1000), normalized_x: point.x, normalized_y: point.y })
  }
  async function startJob() {
    if (!project || !asset || !selection || busy) return
    setBusy(true); setError(null); setDownloadUrl(null)
    try { setJob(await api.createJob(project.id, asset.id, selection, { aspect_ratio: aspect, profile })) } catch (err) { setError(message(err)) } finally { setBusy(false) }
  }
  const step = !project ? 1 : !asset ? 2 : !selection ? 3 : !job ? 4 : 5

  return <main className="app-shell">
    <header className="topbar"><a className="wordmark" href="/">BOULDER <span>FRAME</span></a><span className="offline-pill"><i /> Offline workflow</span></header>
    <section className="hero"><p className="eyebrow">Wide source. Intentional frame.</p><h1>Keep the movement.<br /><em>Lose the distance.</em></h1><p className="hero-copy">Upload a static-camera session, choose your athlete, and let Boulder Frame shape a smoother close-up.</p></section>
    <div className="workspace">
      <aside className="rail"><div className="rail-title">YOUR SESSION</div><div className="session-name">{project?.name ?? projectName}</div>{['Set up project', 'Upload source', 'Select athlete', 'Frame output', 'Download'].map((label, index) => <div className={`rail-step ${step === index + 1 ? 'current' : ''} ${step > index + 1 ? 'done' : ''}`} key={label}><b>{step > index + 1 ? '✓' : `0${index + 1}`}</b><span>{label}</span></div>)}<div className="rail-note">No processing happens in your browser.<br />Your source stays in private storage.</div></aside>
      <div className="content">
        <div className="content-heading"><div><p className="eyebrow">{job ? 'Processing' : `Step 0${step} / 05`}</p><h2>{job ? 'Your frame is taking shape' : step === 1 ? 'Start a new session' : step === 2 ? 'Bring in your source' : step === 3 ? 'Choose the athlete' : 'Set the final frame'}</h2></div>{project && <span className="project-chip">{project.name}</span>}</div>
        {error && <div className="alert" role="alert"><strong>Couldn’t continue</strong><span>{error}</span><button onClick={() => setError(null)} aria-label="Dismiss error">×</button></div>}
        {!project && <section className="card intro-card"><div className="card-index">01</div><div className="card-body"><span className="micro-label">PROJECT NAME</span><label className="field"><input value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder="e.g. Saturday session" onKeyDown={(e) => e.key === 'Enter' && void createProject()} /><span>Give this one-shot project a name.</span></label><button className="primary" onClick={() => void createProject()} disabled={busy}>{busy ? 'Creating…' : 'Create project'} <span>→</span></button></div></section>}
        {project && !asset && <section className="card upload-card"><div className="card-index">02</div><div className="card-body"><span className="micro-label">SOURCE VIDEO</span><label className="dropzone"><input type="file" accept="video/mp4,.mp4" onChange={(e) => void chooseFile(e.target.files?.[0])} /><span className="upload-glyph">↥</span><strong>{busy ? `Uploading ${uploadProgress}%` : 'Drop your MP4 here'}</strong><span>or click to browse · H.264 MP4 · up to {maxUploadLabel}</span>{busy && <span className="progress"><i style={{ width: `${uploadProgress}%` }} /></span>}</label></div></section>}
        {project && asset && <section className="card preview-card"><div className="card-index">03</div><div className="card-body"><div className="preview-head"><div><span className="micro-label">ATHLETE SELECTION</span><p>Tap the athlete you want to keep in frame.</p></div><span className={selection ? 'selection-state selected' : 'selection-state'}>{selection ? 'Athlete selected' : 'Awaiting selection'}</span></div><div className={`preview ${aspect === '9:16' ? 'portrait-preview' : ''}`}><video ref={videoRef} src={previewUrl ?? undefined} controls playsInline onClick={selectAthlete} onLoadedMetadata={(e) => { if (!asset.width || !asset.height) setAsset({ ...asset, width: e.currentTarget.videoWidth, height: e.currentTarget.videoHeight }) }} />{selection && <span className="target-dot" style={{ left: `${normalizedToContainPoint({ x: selection.normalized_x, y: selection.normalized_y }, videoRef.current?.clientWidth ?? 1, videoRef.current?.clientHeight ?? 1, asset.width || videoRef.current?.videoWidth || 1, asset.height || videoRef.current?.videoHeight || 1).x * 100}%`, top: `${normalizedToContainPoint({ x: selection.normalized_x, y: selection.normalized_y }, videoRef.current?.clientWidth ?? 1, videoRef.current?.clientHeight ?? 1, asset.width || videoRef.current?.videoWidth || 1, asset.height || videoRef.current?.videoHeight || 1).y * 100}%` }} />}</div><div className="asset-meta"><span>{file?.name}</span><span>{asset.width && asset.height ? `${asset.width} × ${asset.height}` : 'Reading dimensions'} · {formatDuration(asset.duration_ms)}</span></div>{selection && <button className="text-button" onClick={() => setSelection(null)}>Choose again</button>}</div></section>}
        {asset && selection && !job && <section className="card settings-card"><div className="card-index">04</div><div className="card-body"><div className="settings-group"><span className="micro-label">OUTPUT ASPECT</span><div className="segmented">{(['16:9', '9:16'] as AspectRatio[]).map((value) => <button className={aspect === value ? 'active' : ''} onClick={() => setAspect(value)} key={value}><span className={value === '16:9' ? 'landscape-icon' : 'portrait-icon'} />{value}</button>)}</div></div><div className="settings-group"><span className="micro-label">FRAMING PROFILE</span><div className="profile-grid">{profiles.map((item) => <button className={profile === item.value ? 'profile active' : 'profile'} onClick={() => setProfile(item.value)} key={item.value}><strong>{item.label}</strong><span>{item.detail}</span>{profile === item.value && <i>✓</i>}</button>)}</div></div><button className="primary start-button" onClick={() => void startJob()} disabled={busy}>{busy ? 'Starting…' : 'Start reframing'} <span>↗</span></button></div></section>}
        {job && <JobCard job={job} downloadUrl={downloadUrl} onRetry={() => { setJob(null); setDownloadUrl(null) }} />}
      </div>
    </div>
    <footer><span>BOULDER FRAME / MVP</span><span>Private by default · Built for recorded movement</span></footer>
  </main>
}

function JobCard({ job, downloadUrl, onRetry }: { job: Job; downloadUrl: string | null; onRetry: () => void }) {
  const percent = Math.max(0, Math.min(100, job.progress))
  return <section className="card job-card"><div className="card-index">05</div><div className="card-body"><div className="job-status"><div className={`status-orb ${job.state}`}><span>{job.state === 'completed' ? '✓' : job.state === 'failed' ? '!' : '↻'}</span></div><div><span className="micro-label">{job.state === 'completed' ? 'COMPLETE' : job.state === 'failed' ? 'TERMINAL ERROR' : 'IN PROGRESS'}</span><h3>{stageLabels[job.stage] ?? job.stage}</h3></div></div>{job.state !== 'failed' && job.state !== 'completed' && <><div className="job-progress"><i style={{ width: `${percent}%` }} /></div><div className="job-progress-meta"><span>{percent}% complete</span><span>Keep this tab open</span></div></>}{job.error && <div className="failure"><strong>{job.error.message}</strong><span>Try a new job with the same source and a different selection if needed.</span></div>}{downloadUrl && <a className="primary download" href={downloadUrl} target="_blank" rel="noreferrer">Download 1080p MP4 <span>↓</span></a>}{job.state === 'failed' && <button className="secondary" onClick={onRetry}>Create a new job</button>}<div className="job-id">JOB {job.id}</div></div></section>
}
