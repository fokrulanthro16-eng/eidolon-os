'use client'

import { useState, useEffect, useCallback, useRef } from 'react'

const API_BASE = 'http://127.0.0.1:8010'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MemoryItem {
  id: string
  type: string
  title: string
  text: string
  file_path: string | null
  source: string
  tags: string[]
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

interface SearchResult {
  score: number
  keyword_score?: number
  semantic_score?: number
  recency_score?: number
  item: MemoryItem
}

interface MemorySearchResponse {
  query: string
  count: number
  results: SearchResult[]
  semantic_mode: boolean
}

// Phase 4 chat types
interface ChatSource {
  id: string
  title: string
  source: string
  type: string
  created_at: string
  score: number
  semantic_score: number
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  sources?: ChatSource[]
  brain_mode?: string
  query_used?: string
  total_memories?: number
}

interface ChatStreamEvent {
  delta: string
  done: boolean
  session_id?: string
  sources?: ChatSource[]
  query_used?: string
  brain_mode?: string
  total_memories?: number
}

// Phase 5 — Session Memory
interface Session {
  session_id: string
  title: string
  start_time: string
  end_time: string
  duration_secs: number
  duration_str: string
  memory_count: number
  main_sources: string[]
  keywords: string[]
  topics?: string[]
  summary: string
}

interface SessionDetail extends Session {
  memories: MemoryItem[]
}

// Phase 6 — Replay Engine
interface ReplayFrame {
  index: number
  memory_id: string
  timestamp: string
  time_offset_secs: number
  title: string
  app_name: string | null
  window_title: string | null
  exe_name: string | null
  ocr_text: string
  ocr_summary: string
  file_path: string | null
  type: string
  source: string
  tags: string[]
}

interface ReplayData {
  session_id: string
  title: string
  start_time: string
  end_time: string
  duration_secs: number
  duration_str: string
  frame_count: number
  frames: ReplayFrame[]
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function getImageUrl(filePath: string): string {
  const filename = filePath.replace(/\\/g, '/').split('/').pop()
  return `${API_BASE}/uploads/${filename}`
}

function getScreenshotUrl(filePath: string): string {
  const filename = filePath.replace(/\\/g, '/').split('/').pop()
  return `${API_BASE}/screenshots/${filename}`
}

function getPdfUrl(filePath: string): string {
  // Handles both Windows (C:\...\uploads\pdfs\file.pdf) and posix paths
  const norm = filePath.replace(/\\/g, '/')
  const idx  = norm.lastIndexOf('/uploads/')
  if (idx >= 0) return `${API_BASE}${norm.slice(idx)}`
  return `${API_BASE}/uploads/${norm.split('/').pop()}`
}

function resolveMediaUrl(item: MemoryItem): string | null {
  if (!item.file_path) {
    // Camera events store thumbnail URL in metadata
    if (item.source === 'live_camera' && item.metadata?.thumbnail_url) {
      return `${API_BASE}${item.metadata.thumbnail_url as string}`
    }
    return null
  }
  if (item.type === 'screenshot') return getScreenshotUrl(item.file_path)
  if (item.type === 'pdf') return null  // PDFs show a link, not an img
  return getImageUrl(item.file_path)
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function formatDateShort(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

// ---------------------------------------------------------------------------
// Shared sub-components
// ---------------------------------------------------------------------------

const TYPE_CHIP: Record<string, string> = {
  screenshot: 'chip-blue',
  image:      'chip-emerald',
  pdf:        'chip-orange',
  text:       'chip-amber',
  code:       'chip-purple',
  voice:      'chip-magenta',
  video:      'chip-cyan',
}

function TypeBadge({ type }: { type: string }) {
  const chipColor = TYPE_CHIP[type] ?? 'chip-ghost'
  return (
    <span className={`chip ${chipColor}`}>
      {type}
    </span>
  )
}

const APP_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  VSCode:      { bg: '#007acc18', border: '#007acc44', text: '#4fc3f7' },
  Cursor:      { bg: '#6e40c918', border: '#6e40c944', text: '#b39ddb' },
  PyCharm:     { bg: '#21d07818', border: '#21d07844', text: '#69f0ae' },
  IntelliJ:    { bg: '#fc52ff18', border: '#fc52ff44', text: '#f48fb1' },
  WebStorm:    { bg: '#07c3f218', border: '#07c3f244', text: '#4dd0e1' },
  Chrome:      { bg: '#4285f418', border: '#4285f444', text: '#7cb9f4' },
  Firefox:     { bg: '#ff713918', border: '#ff713944', text: '#ffab76' },
  Edge:        { bg: '#0078d418', border: '#0078d444', text: '#42a5f5' },
  Brave:       { bg: '#fb542b18', border: '#fb542b44', text: '#ff8a65' },
  Terminal:    { bg: '#00c89618', border: '#00c89644', text: '#4db6ac' },
  PowerShell:  { bg: '#012b7218', border: '#012b7244', text: '#5c9be3' },
  CMD:         { bg: '#2a2a2a18', border: '#2a2a2a88', text: '#9e9e9e' },
  Slack:       { bg: '#4a154b18', border: '#4a154b66', text: '#e91e63' },
  Discord:     { bg: '#5865f218', border: '#5865f244', text: '#7986cb' },
  Teams:       { bg: '#6264a718', border: '#6264a744', text: '#9fa8da' },
  Notion:      { bg: '#ffffff0a', border: '#ffffff22', text: '#bdbdbd' },
  Obsidian:    { bg: '#7c3aed18', border: '#7c3aed44', text: '#ce93d8' },
  Figma:       { bg: '#a259ff18', border: '#a259ff44', text: '#ce93d8' },
  Postman:     { bg: '#ff620018', border: '#ff620044', text: '#ff8a65' },
  Spotify:     { bg: '#1db95418', border: '#1db95444', text: '#66bb6a' },
  Word:        { bg: '#185abd18', border: '#185abd44', text: '#64b5f6' },
  Excel:       { bg: '#1f7a4318', border: '#1f7a4344', text: '#81c784' },
}

function AppBadge({ appName }: { appName: string }) {
  const colors = APP_COLORS[appName] ?? {
    bg: '#2a4a6a18', border: '#2a4a6a66', text: '#78909c',
  }
  return (
    <span style={{
      background: colors.bg,
      border: `1px solid ${colors.border}`,
      color: colors.text,
      fontSize: '10px',
      padding: '1px 6px',
      borderRadius: '3px',
      whiteSpace: 'nowrap' as const,
      fontFamily: 'var(--font-geist-mono, monospace)',
      letterSpacing: '0.04em',
    }}>
      {appName}
    </span>
  )
}

// Phase 9 — Suggestions (updated with stable IDs + dismiss)
interface Suggestion {
  id:                string
  type:              string
  title?:            string
  text:              string
  detail:            string
  reason?:           string
  confidence:        number
  memory_ids:        string[]
  source_memory_ids?: string[]
  action?:           string
  created_at?:       string
  dismissed?:        boolean
}

// Memory Graph
interface GraphNode {
  id:         string
  type:       string
  title:      string
  source:     string
  created_at: string
}

interface GraphEdge {
  from:         string
  to:           string
  relationship: string
  confidence:   number
  reason:       string
}

interface GraphData {
  nodes:     GraphNode[]
  edges:     GraphEdge[]
  stats:     { node_count: number; edge_count: number; relationships: Record<string, number> }
  center_id?: string
}

// Profile
interface ProfileData {
  top_apps:           { app: string; count: number; pct: number }[]
  active_hours:       Record<string, number>
  peak_period:        string
  scene_distribution: Record<string, number>
  workflow_summary:   string
  workflow_patterns:  string[]
  dominant_sources:   { source: string; count: number }[]
  productivity_notes: string[]
  type_distribution:  Record<string, number>
  memory_span_days:   number
  total_memories:     number
  top_keywords:       string[]
  insights:           string[]
  confidence:         number
  privacy_note:       string
}

// Phase 8 — PDF Chat types
interface PdfChunk {
  chunk_id:  string
  memory_id: string
  page_num:  number
  text:      string
  score:     number
}

interface PdfChatResponse {
  answer:         string
  pdf_title:      string | null
  matched_chunks: PdfChunk[]
  confidence:     number
  source_pages:   number[]
}

// Camera / CCTV status
interface CameraStatus {
  running:          boolean
  camera_available: boolean | null
  detection_mode:   string
  last_event_time:  string | null
  event_count:      number
  error:            string | null
}

// Prediction layer
interface PredictionItem {
  track_id:          string
  label:             string
  cls_id:            number
  direction:         string
  speed:             number
  area_trend:        string
  current_x:         number
  current_y:         number
  predicted_x:       number
  predicted_y:       number
  prediction_events: string[]
  confidence:        number
  stationary_secs:   number
}

// Phase 11 — Vision Intelligence types
interface VisionMeta {
  scene_type?:    string
  workflow_type?: string
  probable_task?: string
  smart_title?:   string
  active_tools?:  string[]
  confidence?:    number
  visual_tags?:   string[]
  dominant_app?:  string
}

// Phase 12 — Agent types
interface AgentAction {
  name:        string
  label:       string
  description: string
  args:        Record<string, string>
  icon:        string
}

interface AgentResult {
  success:     boolean
  message:     string
  [key: string]: unknown
}

interface WorkflowPeriod {
  start:         string
  end:           string
  duration_mins: number
  memory_count:  number
  dominant_app:  string
  workflow_type: string
  scene_type:    string
  label:         string
  active_tools:  string[]
  sample_tasks:  string[]
}

interface DailySummary {
  total_memories:     number
  screenshot_count:   number
  active_hours:       number
  workflow_breakdown: Record<string, number>
  top_apps:           { app: string; count: number }[]
  top_tools:          { tool: string; count: number }[]
  key_activities:     string[]
  workflow_periods:   number
  summary_text:       string
}

// Phase 13 — Replay Engine 2.0
interface ReplayMemoryItem {
  id:         string
  type:       string
  title:      string
  created_at: string
  app_name?:  string
  source:     string
}

interface ReplayKeyMoment {
  moment_type: string
  title:       string
  memory_id:   string
  created_at:  string
  description: string
}

interface ReplayResult {
  replay_title:   string
  summary:        string
  ordered_events: ReplayMemoryItem[]
  key_moments:    ReplayKeyMoment[]
  apps_used:      string[]
  memories:       ReplayMemoryItem[]
  confidence:     number
  total_count:    number
  date_range?:    { start: string; end: string }
}

// Phase 14 — Digital Soul
interface SoulPattern {
  name:        string
  description: string
  evidence:    string
  strength:    number
  type:        string
}

interface HourlyActivity {
  hour:       number
  hour_label: string
  count:      number
  top_scene:  string
}

interface SoulWorkflowRhythm {
  hourly_heatmap:  Record<string, number>
  peak_hours:      string[]
  peak_activities: HourlyActivity[]
  day_of_week:     Record<string, number>
  most_active_day: string
}

interface SoulProjectMemory {
  top_projects:        { name: string; mentions: number }[]
  recent_keywords:     string[]
  unfinished_sessions: { session_id: string; title: string; duration_str: string; ended_at: string; apps: string[] }[]
  last_active_app:     string | null
  total_sessions:      number
}

// Phase 15 — Neural Search
interface NeuralSearchGroupItem {
  score:      number
  id:         string
  title:      string
  created_at: string
  type:       string
  source:     string
  metadata:   Record<string, unknown> | null
}

interface NeuralSearchResponse {
  query:               string
  answer_summary:      string
  results:             { score: number; item: MemoryItem; modality_weight: number }[]
  grouped_by_modality: Record<string, NeuralSearchGroupItem[]>
  timeline:            { id: string; type: string; title: string; created_at: string; score: number; app_name: string }[]
  confidence:          number
  search_mode:         string
  total_found:         number
}

// Phase 16 — Multi-Camera
interface MultiCamera {
  camera_id:        string
  name:             string
  source_type:      string
  source:           string
  enabled:          boolean
  detection_mode:   string
  created_at:       string
  running:          boolean
  camera_available: boolean | null
  last_event_time:  string | null
  event_count:      number
  error:            string | null
}

// Phase 17 — World Model
interface WorldEntity {
  label:     string
  count:     number
  last_seen: string
  active:    boolean
}

interface WorldMovementPred {
  track_id:    string
  label:       string
  direction:   string
  speed:       number
  predicted_x: number
  predicted_y: number
  confidence:  number
  note:        string
}

interface WorldEvent {
  created_at:  string
  event_type:  string
  labels:      string[]
  camera_id:   string | null
  camera_name: string | null
}

interface WorldState {
  world_state:           string
  active_entities:       WorldEntity[]
  recent_events:         WorldEvent[]
  movement_predictions:  WorldMovementPred[]
  zones:                 Record<string, string[]>
  risk_notes:            string[]
  confidence:            number
  total_events_analyzed: number
  prediction_count:      number
  disclaimer:            string
}

// Phase 18 / 21 — Brain Status
interface BrainStatus {
  brain_provider:    string
  mode:              string
  llm_active:        boolean
  fallback_used:     boolean
  orb_state?:        'green' | 'yellow' | 'red'
  quota_limited?:    boolean
  retry_after_seconds?: number
  ollama_url?:       string
  ollama_model?:     string
  lmstudio_url?:     string
  lmstudio_model?:   string
  available_models?: string[]
  model?:            string
  lockdown?:         boolean
  error?:            string
}

// Phase 21 — Intelligence / Cognitive Profile
interface IntelDomainScore {
  domain:     string
  score:      number
  percentage: number
  count:      number
  color:      string
}

interface IntelCluster {
  name:         string
  color:        string
  count:        number
  percentage:   number
  recent_title: string
}

interface IntelTrendDomain {
  domain:    string
  color:     string
  this_week: number
  last_week: number
  trend:     'rising' | 'falling' | 'stable' | 'new'
  delta:     string
}

interface IntelDay {
  date:    string
  label:   string
  count:   number
  domains: Record<string, number>
}

interface IntelInsight {
  type:  string
  title: string
  text:  string
  value: string
  color: string
}

interface CognitiveProfile {
  summary:            string
  gemini_powered:     boolean
  primary_activities: string[]
  interests:          string[]
  active_projects:    string[]
  work_patterns:      { peak_period: string; top_apps: string[]; workflow_summary: string }
  dominant_themes:    string[]
  domain_scores:      IntelDomainScore[]
  top_sources:        string[]
  keywords:           string[]
  memory_count:       number
  confidence:         number
  clusters:           IntelCluster[]
  timeline:           TrendsTimeline
  insights:           IntelInsight[]
}

interface TrendsTimeline {
  daily:            IntelDay[]
  this_week_count:  number
  last_week_count:  number
  wow_change:       string
  trending_domains: IntelTrendDomain[]
  best_day:         string | null
  best_day_count:   number
  best_day_label:   string
  total_memories:   number
  narrative?:       string
}

// Phase 10 — Video Intelligence types
interface VideoEvent {
  id:             string
  type:           string
  timestamp_secs: number
  frame_index:    number
  description:    string
  label:          string
  track_id:       string | null
  confidence:     number
  thumbnail_url:  string | null
  person_count?:  number
}

interface VideoRecord {
  id:             string
  filename:       string
  original_name:  string
  file_path:      string
  file_size:      number
  status:         'pending' | 'analyzing' | 'done' | 'error'
  progress:       number
  error:          string | null
  created_at:     string
  analyzed_at:    string | null
  duration_secs:  number | null
  fps:            number | null
  resolution:     string | null
  frame_count:    number | null
  event_count:    number
  thumbnail_path: string | null
  labels:         string[]
  summary:        string
  events?:        VideoEvent[]
}

// ---------------------------------------------------------------------------
// Replay Engine (Phase 6)
// ---------------------------------------------------------------------------

function ctrlBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    background: 'transparent',
    border: `1px solid ${disabled ? '#081428' : '#0c1e38'}`,
    color: disabled ? '#0e2040' : '#3a6080',
    padding: '5px 12px',
    borderRadius: '5px',
    cursor: disabled ? 'default' as const : 'pointer' as const,
    fontSize: '12px',
    fontFamily: 'var(--font-geist-mono, monospace)',
    transition: 'all 0.1s',
  }
}

function formatOffset(secs: number): string {
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `+${m}:${s.toString().padStart(2, '0')}`
}

function ReplayPlayer({ data, onClose }: { data: ReplayData; onClose: () => void }) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [playing, setPlaying]           = useState(false)
  const intervalRef                     = useRef<ReturnType<typeof setInterval> | null>(null)
  const scrubberRef                     = useRef<HTMLDivElement>(null)

  const frame    = data.frames[currentIndex]
  const isFirst  = currentIndex === 0
  const isLast   = currentIndex === data.frames.length - 1

  // Auto-advance
  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(() => {
        setCurrentIndex(i => {
          if (i >= data.frames.length - 1) {
            setPlaying(false)
            return i
          }
          return i + 1
        })
      }, 2000)
    } else {
      if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null }
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [playing, data.frames.length])

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') setCurrentIndex(i => Math.min(i + 1, data.frames.length - 1))
      else if (e.key === 'ArrowLeft') setCurrentIndex(i => Math.max(i - 1, 0))
      else if (e.key === ' ') { e.preventDefault(); setPlaying(p => !p) }
      else if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose, data.frames.length])

  // Scroll active scrubber dot into view
  useEffect(() => {
    if (!scrubberRef.current) return
    const active = scrubberRef.current.querySelector('[data-active="true"]') as HTMLElement | null
    active?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' })
  }, [currentIndex])

  const mediaUrl = frame.file_path
    ? (frame.type === 'screenshot' ? getScreenshotUrl(frame.file_path) : getImageUrl(frame.file_path))
    : null

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.92)', backdropFilter: 'blur(8px)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{ width: '100%', maxWidth: '1100px', height: '90vh', background: '#050510', border: '1px solid #00b4ff22', borderRadius: '12px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* ── Header ── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 18px', borderBottom: '1px solid #0a1830', flexShrink: 0 }}>
          <span style={{ color: '#00b4ff', fontSize: '10px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.12em' }}>▶ REPLAY</span>
          <span style={{ color: '#0e2040', fontSize: '12px' }}>|</span>
          <span style={{ color: '#8aaaca', fontSize: '12px', fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{data.title}</span>
          <span style={{ color: '#1e4060', fontSize: '10px', fontFamily: 'var(--font-geist-mono, monospace)', flexShrink: 0 }}>{currentIndex + 1} / {data.frame_count}</span>
          <span style={{ color: '#0e2a40', fontSize: '10px', fontFamily: 'var(--font-geist-mono, monospace)', flexShrink: 0 }}>{data.duration_str}</span>
          <button onClick={onClose} style={{ background: 'transparent', border: '1px solid #0c1e38', color: '#2a5070', padding: '3px 9px', borderRadius: '4px', cursor: 'pointer', fontSize: '13px', flexShrink: 0 }}>✕</button>
        </div>

        {/* ── Main content ── */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>

          {/* Screenshot */}
          <div style={{ flex: '1 1 60%', background: '#030308', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', borderRight: '1px solid #0a1830' }}>
            {mediaUrl ? (
              <img
                key={frame.memory_id}
                src={mediaUrl}
                alt={frame.title}
                style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
              />
            ) : (
              <div style={{ textAlign: 'center', color: '#1e3050' }}>
                <div style={{ fontSize: '40px', marginBottom: '10px' }}>◫</div>
                <p style={{ fontFamily: 'var(--font-geist-mono, monospace)', fontSize: '11px', letterSpacing: '0.1em', margin: 0 }}>NO SCREENSHOT</p>
              </div>
            )}
          </div>

          {/* Metadata panel */}
          <div style={{ flex: '0 0 300px', padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px', overflowY: 'auto' }}>

            <div>
              <div style={{ color: '#1e4060', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.15em', marginBottom: '4px' }}>TIMESTAMP</div>
              <div style={{ color: '#3a6080', fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                {new Date(frame.timestamp).toLocaleTimeString()}
              </div>
              <div style={{ color: '#1e3050', fontSize: '10px', fontFamily: 'var(--font-geist-mono, monospace)', marginTop: '3px' }}>
                {formatOffset(frame.time_offset_secs)} from session start
              </div>
            </div>

            {frame.app_name && (
              <div>
                <div style={{ color: '#1e4060', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.15em', marginBottom: '6px' }}>APPLICATION</div>
                <AppBadge appName={frame.app_name} />
                {frame.window_title && (
                  <div style={{ color: '#2a4a6a', fontSize: '10px', fontFamily: 'var(--font-geist-mono, monospace)', marginTop: '8px', wordBreak: 'break-word' as const, lineHeight: 1.5 }}>
                    {frame.window_title}
                  </div>
                )}
              </div>
            )}

            <div>
              <div style={{ color: '#1e4060', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.15em', marginBottom: '4px' }}>TITLE</div>
              <div style={{ color: '#8aaaca', fontSize: '12px', fontWeight: 600, lineHeight: 1.4 }}>{frame.title}</div>
            </div>

            {frame.ocr_summary && !frame.ocr_summary.startsWith('[OCR') && (
              <div style={{ flex: 1 }}>
                <div style={{ color: '#1e4060', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.15em', marginBottom: '4px' }}>OCR TEXT</div>
                <p style={{ color: '#3a5070', fontSize: '11px', lineHeight: 1.7, margin: 0, fontFamily: 'var(--font-geist-mono, monospace)', wordBreak: 'break-word' as const }}>
                  {frame.ocr_summary}
                </p>
              </div>
            )}

            {frame.tags.length > 0 && (
              <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' as const }}>
                {frame.tags.map(t => (
                  <span key={t} style={{ background: '#0a1828', border: '1px solid #0e2438', color: '#3a6a8a', fontSize: '9px', padding: '1px 6px', borderRadius: '3px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                    {t}
                  </span>
                ))}
              </div>
            )}

          </div>
        </div>

        {/* ── Scrubber ── */}
        <div style={{ padding: '8px 18px 4px', borderTop: '1px solid #0a1830', flexShrink: 0 }}>
          <div ref={scrubberRef} style={{ display: 'flex', alignItems: 'center', gap: '3px', overflowX: 'auto', paddingBottom: '4px' }}>
            {data.frames.map((f, idx) => (
              <button
                key={f.memory_id}
                data-active={idx === currentIndex ? 'true' : 'false'}
                onClick={() => { setCurrentIndex(idx); setPlaying(false) }}
                title={`${new Date(f.timestamp).toLocaleTimeString()} · ${f.app_name ?? f.source}`}
                style={{
                  flex: '1 0 8px',
                  maxWidth: '28px',
                  height: idx === currentIndex ? '22px' : '10px',
                  borderRadius: '3px',
                  background: idx === currentIndex ? '#00b4ff' : idx < currentIndex ? '#0a3060' : '#0a1828',
                  border: `1px solid ${idx === currentIndex ? '#00b4ff' : '#0e2438'}`,
                  cursor: 'pointer',
                  transition: 'all 0.12s',
                  padding: 0,
                }}
              />
            ))}
          </div>
        </div>

        {/* ── Controls ── */}
        <div style={{ padding: '10px 18px 14px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', borderTop: '1px solid #0a1830', flexShrink: 0 }}>
          <button onClick={() => { setCurrentIndex(0); setPlaying(false) }} disabled={isFirst} style={ctrlBtnStyle(isFirst)} title="First (Home)">⏮</button>
          <button onClick={() => setCurrentIndex(i => Math.max(0, i - 1))} disabled={isFirst} style={ctrlBtnStyle(isFirst)} title="Previous (←)">‹ Prev</button>
          <button
            onClick={() => setPlaying(p => !p)}
            style={{ ...ctrlBtnStyle(false), background: playing ? '#00b4ff22' : '#00b4ff0a', border: `1px solid ${playing ? '#00b4ff55' : '#00b4ff22'}`, color: '#00b4ff', padding: '5px 22px', minWidth: '90px' }}
            title="Play / Pause (Space)"
          >
            {playing ? '⏸ Pause' : '▶ Play'}
          </button>
          <button onClick={() => setCurrentIndex(i => Math.min(data.frames.length - 1, i + 1))} disabled={isLast} style={ctrlBtnStyle(isLast)} title="Next (→)">Next ›</button>
          <button onClick={() => { setCurrentIndex(data.frames.length - 1); setPlaying(false) }} disabled={isLast} style={ctrlBtnStyle(isLast)} title="Last (End)">⏭</button>
        </div>

      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Suggestions Panel (Phase 9 — Autonomous Suggestions)
// ---------------------------------------------------------------------------

const SUGGESTION_ICONS: Record<string, string> = {
  pdf_cluster:      '◫',
  workflow_pattern: '⬡',
  time_pattern:     '◷',
  topic_insight:    '◈',
  session_pattern:  '▶',
  app_dominance:    '◆',
}

function SuggestionsPanel({
  suggestions,
  loading,
  dismissed,
  onDismiss,
  onRefresh,
}: {
  suggestions: Suggestion[]
  loading: boolean
  dismissed: Set<string>
  onDismiss: (id: string) => void
  onRefresh: () => void
}) {
  const [open, setOpen] = useState(false)
  const visible = suggestions.filter(s => !dismissed.has(s.id))

  return (
    <div style={{ padding: '0 28px', marginBottom: '8px' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width:        '100%',
          background:   open ? 'rgba(124,58,237,0.06)' : 'transparent',
          border:       `1px solid ${open ? 'rgba(124,58,237,0.2)' : 'rgba(255,255,255,0.06)'}`,
          borderRadius: open ? '10px 10px 0 0' : '10px',
          padding:      '10px 16px',
          display:      'flex',
          alignItems:   'center',
          gap:          '10px',
          cursor:       'pointer',
          transition:   'border-color 0.15s, background 0.15s',
        }}
      >
        <span style={{ color: 'var(--violet)', fontSize: '12px', letterSpacing: '0.1em', fontFamily: 'var(--font-geist-mono, monospace)' }}>
          ⬡ EIDOLON INSIGHTS
        </span>
        {visible.length > 0 && (
          <span className="chip chip-purple" style={{ fontSize: '9px' }}>
            {visible.length}
          </span>
        )}
        <span style={{ flex: 1, color: 'var(--text-4)', fontSize: '11px', textAlign: 'left' as const }}>
          {!open && (visible.length > 0 ? visible[0].text : 'Analysing your memory patterns…')}
        </span>
        <span style={{ color: 'var(--text-4)', fontSize: '11px' }}>
          {open ? '▲' : '▼'}
        </span>
      </button>

      {open && (
        <div style={{
          background:    'rgba(6,6,20,0.9)',
          border:        '1px solid rgba(124,58,237,0.18)',
          borderTop:     'none',
          borderRadius:  '0 0 10px 10px',
          padding:       '14px 16px',
          display:       'flex',
          flexDirection: 'column',
          gap:           '8px',
          backdropFilter: 'blur(16px)',
        }}>
          {loading && (
            <div style={{ color: 'var(--text-3)', fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)', display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span className="spin-ring" style={{ fontSize: '16px' }}>⟳</span>
              Analysing patterns…
            </div>
          )}

          {!loading && visible.length === 0 && (
            <p style={{ color: 'var(--text-4)', fontSize: '11px', margin: 0, fontFamily: 'var(--font-geist-mono, monospace)' }}>
              No insights yet — capture more memories to unlock pattern analysis.
            </p>
          )}

          {visible.map(s => (
            <div key={s.id} className="suggestion-card">
              <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                <span style={{ color: 'var(--violet)', fontSize: '18px', flexShrink: 0, marginTop: '1px' }}>
                  {SUGGESTION_ICONS[s.type] ?? '◆'}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ color: 'var(--text-1)', fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>
                    {s.text}
                  </div>
                  <div style={{ color: 'var(--text-3)', fontSize: '11px', lineHeight: 1.5, fontFamily: 'var(--font-geist-mono, monospace)' }}>
                    {s.detail}
                  </div>
                  {s.action && (
                    <div style={{ marginTop: '5px', color: 'var(--violet)', fontSize: '10px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                      → {s.action}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-end', flexShrink: 0 }}>
                  <span className="chip chip-purple" style={{ fontSize: '9px' }}>
                    {Math.round(s.confidence * 100)}%
                  </span>
                  <button
                    onClick={() => onDismiss(s.id)}
                    style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.06)', color: 'var(--text-4)', fontSize: '10px', padding: '1px 7px', borderRadius: '4px', cursor: 'pointer', transition: 'all 0.15s' }}
                    onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(244,63,94,0.3)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--rose)' }}
                    onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.06)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-4)' }}
                    title="Dismiss"
                  >
                    ✕
                  </button>
                </div>
              </div>
              {/* Confidence bar */}
              <div className="conf-bar">
                <div className="conf-bar-fill" style={{ width: `${Math.round(s.confidence * 100)}%` }} />
              </div>
            </div>
          ))}

          {!loading && suggestions.length > 0 && (
            <button onClick={onRefresh} className="btn-ghost" style={{ fontSize: '10px', alignSelf: 'flex-start' }}>
              ↺ Refresh insights
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// PDF Chat Panel (Phase 8)
// ---------------------------------------------------------------------------

function confidenceColor(c: number): string {
  if (c >= 0.65) return '#00ff88'
  if (c >= 0.35) return '#ffd700'
  return '#ff6b35'
}

function PdfChatPanel({
  target,
  onClose,
}: {
  target: MemoryItem | null
  onClose: () => void
}) {
  const [question, setQuestion]       = useState('')
  const [response, setResponse]       = useState<PdfChatResponse | null>(null)
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState<string | null>(null)
  const [searchAll, setSearchAll]     = useState(false)
  const [chunksOpen, setChunksOpen]   = useState(false)
  const inputRef                      = useRef<HTMLInputElement>(null)

  // Focus input when panel opens
  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 80)
  }, [])

  // Esc closes
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  const ask = async (overrideQ?: string) => {
    const q = (overrideQ ?? question).trim()
    if (!q || loading) return
    if (overrideQ) setQuestion(overrideQ)
    setLoading(true)
    setError(null)
    setResponse(null)
    setChunksOpen(false)
    try {
      const body: Record<string, unknown> = { question: q }
      if (target && !searchAll) body.pdf_memory_id = target.id
      const res = await fetch(`${API_BASE}/pdf/chat`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error((err as { detail?: string }).detail || `HTTP ${res.status}`)
      }
      const data: PdfChatResponse = await res.json()
      setResponse(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') ask()
  }

  const SAMPLE_QUESTIONS = [
    'What is this document about?',
    'What are the main conclusions?',
    'List the key points',
    'What does it say about results?',
  ]

  return (
    <div
      style={{
        position:   'fixed',
        top:        0,
        right:      0,
        bottom:     0,
        width:      'min(480px, 100vw)',
        background: '#050510',
        border:     'none',
        borderLeft: '1px solid #00b4ff22',
        boxShadow:  '-8px 0 40px rgba(0,0,0,0.7)',
        zIndex:     90,
        display:    'flex',
        flexDirection: 'column',
        overflow:   'hidden',
      }}
    >
      {/* ── Header ── */}
      <div style={{
        padding:      '12px 16px',
        borderBottom: '1px solid #0a1830',
        display:      'flex',
        alignItems:   'center',
        gap:          '10px',
        flexShrink:   0,
      }}>
        <span style={{ color: '#ff8c5a', fontSize: '10px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.12em' }}>
          ◫ ASK PDF
        </span>
        <span style={{ color: '#0e2040', fontSize: '12px' }}>|</span>
        <span style={{
          color:          '#8aaaca',
          fontSize:       '12px',
          fontWeight:     600,
          flex:           1,
          overflow:       'hidden',
          textOverflow:   'ellipsis',
          whiteSpace:     'nowrap' as const,
        }}>
          {searchAll || !target ? 'All PDFs' : target.title}
        </span>
        <button
          onClick={onClose}
          style={{
            background:   'transparent',
            border:       '1px solid #0c1e38',
            color:        '#2a5070',
            padding:      '3px 9px',
            borderRadius: '4px',
            cursor:       'pointer',
            fontSize:     '13px',
            flexShrink:   0,
          }}
        >
          ✕
        </button>
      </div>

      {/* ── Scope toggle ── */}
      {target && (
        <div style={{
          padding:      '8px 16px',
          borderBottom: '1px solid #0a1830',
          display:      'flex',
          gap:          '6px',
          flexShrink:   0,
        }}>
          {[false, true].map(all => (
            <button
              key={String(all)}
              onClick={() => { setSearchAll(all); setResponse(null); setError(null) }}
              style={{
                background:    searchAll === all ? '#ff6b3518' : 'transparent',
                border:        `1px solid ${searchAll === all ? '#ff6b3544' : '#0c1e38'}`,
                color:         searchAll === all ? '#ff8c5a' : '#2a5070',
                fontSize:      '10px',
                padding:       '3px 10px',
                borderRadius:  '4px',
                cursor:        'pointer',
                fontFamily:    'var(--font-geist-mono, monospace)',
                transition:    'all 0.12s',
              }}
            >
              {all ? 'All PDFs' : 'This PDF only'}
            </button>
          ))}
        </div>
      )}

      {/* ── Input area ── */}
      <div style={{ padding: '14px 16px', borderBottom: '1px solid #0a1830', flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            ref={inputRef}
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask a question about the PDF…"
            disabled={loading}
            style={{
              flex:         1,
              background:   '#08081a',
              border:       '1px solid #0e2040',
              borderRadius: '5px',
              color:        '#c0cce8',
              padding:      '7px 12px',
              fontSize:     '13px',
              outline:      'none',
              fontFamily:   'inherit',
            }}
          />
          <button
            onClick={() => ask()}
            disabled={loading || !question.trim()}
            className="btn-primary"
            style={{ flexShrink: 0, minWidth: '64px' }}
          >
            {loading ? '…' : 'Ask'}
          </button>
        </div>

        {/* Sample questions */}
        {!response && !loading && (
          <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' as const, marginTop: '8px' }}>
            {SAMPLE_QUESTIONS.map(q => (
              <button
                key={q}
                onClick={() => ask(q)}
                disabled={loading}
                style={{
                  background:   'transparent',
                  border:       '1px solid #0e2040',
                  color:        '#2a5070',
                  fontSize:     '9px',
                  padding:      '2px 7px',
                  borderRadius: '3px',
                  cursor:       'pointer',
                  fontFamily:   'var(--font-geist-mono, monospace)',
                }}
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Results area ── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>

        {/* Loading */}
        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#1e4060' }}>
            <span style={{ fontSize: '20px', animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
            <span style={{ fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em' }}>
              SEARCHING PDF…
            </span>
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <p style={{ color: '#ff4455', fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)', margin: 0 }}>
            ERROR: {error}
          </p>
        )}

        {/* Answer */}
        {response && !loading && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>

            {/* Confidence + source pages row */}
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' as const }}>
              <span style={{
                background:   `${confidenceColor(response.confidence)}18`,
                border:       `1px solid ${confidenceColor(response.confidence)}44`,
                color:        confidenceColor(response.confidence),
                fontSize:     '9px',
                padding:      '1px 7px',
                borderRadius: '3px',
                fontFamily:   'var(--font-geist-mono, monospace)',
                letterSpacing: '0.06em',
              }}>
                {Math.round(response.confidence * 100)}% confidence
              </span>

              {response.source_pages.length > 0 && (
                <div style={{ display: 'flex', gap: '4px', alignItems: 'center', flexWrap: 'wrap' as const }}>
                  <span style={{ color: '#1e4060', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                    pages:
                  </span>
                  {response.source_pages.map(p => (
                    <span key={p} style={{
                      background:   '#ff6b3511',
                      border:       '1px solid #ff6b3533',
                      color:        '#ff8c5a',
                      fontSize:     '9px',
                      padding:      '1px 5px',
                      borderRadius: '3px',
                      fontFamily:   'var(--font-geist-mono, monospace)',
                    }}>
                      {p}
                    </span>
                  ))}
                </div>
              )}

              {response.pdf_title && (
                <span style={{ color: '#2a4060', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)', flex: '1 1 100%', marginTop: '2px' }}>
                  {response.pdf_title}
                </span>
              )}
            </div>

            {/* Answer text */}
            <div style={{
              background:   '#06060f',
              border:       '1px solid #0a1e38',
              borderRadius: '6px',
              padding:      '14px',
            }}>
              <p style={{
                color:      '#c0d4f0',
                fontSize:   '13px',
                lineHeight: 1.7,
                margin:     0,
              }}>
                {response.answer}
              </p>
            </div>

            {/* Matched chunks (collapsible) */}
            {response.matched_chunks.length > 0 && (
              <div>
                <button
                  onClick={() => setChunksOpen(o => !o)}
                  style={{
                    background:   'transparent',
                    border:       '1px solid #0c1e38',
                    color:        '#2a5070',
                    fontSize:     '10px',
                    padding:      '3px 10px',
                    borderRadius: '4px',
                    cursor:       'pointer',
                    fontFamily:   'var(--font-geist-mono, monospace)',
                    marginBottom: '8px',
                  }}
                >
                  {chunksOpen ? '▲' : '▼'} {response.matched_chunks.length} source chunk{response.matched_chunks.length !== 1 ? 's' : ''}
                </button>

                {chunksOpen && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {response.matched_chunks.map(chunk => (
                      <div key={chunk.chunk_id} style={{
                        background:   '#04040c',
                        border:       '1px solid #0a1828',
                        borderRadius: '5px',
                        padding:      '10px 12px',
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', gap: '6px' }}>
                          {chunk.page_num > 0 && (
                            <span style={{
                              background:   '#ff6b3511',
                              border:       '1px solid #ff6b3533',
                              color:        '#ff8c5a',
                              fontSize:     '9px',
                              padding:      '0 5px',
                              borderRadius: '3px',
                              fontFamily:   'var(--font-geist-mono, monospace)',
                            }}>
                              p.{chunk.page_num}
                            </span>
                          )}
                          <span style={{ color: '#00ff88', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)', marginLeft: 'auto' }}>
                            ↑{(chunk.score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <p style={{
                          color:      '#3a5a7a',
                          fontSize:   '11px',
                          lineHeight: 1.6,
                          margin:     0,
                          fontFamily: 'var(--font-geist-mono, monospace)',
                        }}>
                          {chunk.text}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Memory grid card
// ---------------------------------------------------------------------------

function MemoryCard({ item, result, onAskPdf }: { item: MemoryItem; result?: SearchResult; onAskPdf?: () => void }) {
  const isPdf   = item.type === 'pdf'
  const isVoice = item.type === 'voice'
  const isVisual = item.type === 'screenshot' || item.type === 'image'

  const preview = item.text
    ? item.text.slice(0, 180) + (item.text.length > 180 ? '…' : '')
    : (isPdf ? '[No text extracted — install PyMuPDF]' : isVoice ? '[No transcript — install faster-whisper]' : 'No text extracted')

  const mediaUrl = resolveMediaUrl(item)
  const hasSemantic = result && result.semantic_score !== undefined && result.semantic_score > 0
  const appName    = item.metadata?.app_name as string | undefined
  const windowTitle = item.metadata?.window_title as string | undefined
  const pageCount  = item.metadata?.page_count as number | undefined
  const pdfAvailable = item.metadata?.extraction_available as boolean | undefined

  // Voice metadata
  const durationStr = item.metadata?.duration_str as string | undefined
  const language    = item.metadata?.language as string | undefined
  const transcriptConf = item.metadata?.transcript_confidence as number | undefined
  const voiceAvailable = item.metadata?.transcription_available as boolean | undefined

  // Vision / Phase 11 metadata
  const sceneType     = item.metadata?.scene_type as string | undefined
  const visualTags    = item.metadata?.visual_tags as string[] | undefined
  const probableTask  = item.metadata?.probable_task as string | undefined
  const activeTools   = item.metadata?.active_tools as string[] | undefined
  const visionConf    = item.metadata?.confidence as number | undefined
  const workflowType  = item.metadata?.workflow_type as string | undefined

  return (
    <div className={`memory-card card-${item.type} reveal`}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
        <span style={{ fontWeight: 600, color: 'var(--text-1)', fontSize: '13px', flex: 1, wordBreak: 'break-word' as const }}>
          {item.title}
        </span>
        <TypeBadge type={item.type} />
      </div>

      {appName && (
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' as const }}>
          <AppBadge appName={appName} />
          {windowTitle && (
            <span style={{
              color: '#2a4a6a',
              fontSize: '10px',
              fontFamily: 'var(--font-geist-mono, monospace)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap' as const,
              maxWidth: '200px',
            }} title={windowTitle}>
              {windowTitle}
            </span>
          )}
        </div>
      )}

      {isPdf && (
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' as const }}>
          {pageCount !== undefined && pageCount > 0 && (
            <span className="chip chip-orange" style={{ fontSize: '9px' }}>
              {pageCount} {pageCount === 1 ? 'page' : 'pages'}
            </span>
          )}
          {!pdfAvailable && <span className="label-xs">install pymupdf for text</span>}
          {item.file_path && (
            <a
              href={getPdfUrl(item.file_path)}
              target="_blank"
              rel="noopener noreferrer"
              className="chip chip-orange"
              style={{ fontSize: '9px', textDecoration: 'none' }}
            >
              ↗ Open PDF
            </a>
          )}
          {pdfAvailable && onAskPdf && (
            <button
              onClick={e => { e.stopPropagation(); onAskPdf() }}
              className="chip chip-orange"
              style={{ fontSize: '9px', cursor: 'pointer', background: 'none', fontFamily: 'inherit' }}
            >
              ◫ Ask PDF
            </button>
          )}
        </div>
      )}

      {/* Voice metadata */}
      {isVoice && (
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' as const }}>
          {durationStr && <span className="chip chip-magenta" style={{ fontSize: '9px' }}>◷ {durationStr}</span>}
          {language && language !== 'unknown' && <span className="chip chip-magenta" style={{ fontSize: '9px' }}>{language}</span>}
          {transcriptConf !== undefined && voiceAvailable && (
            <span className={`chip ${transcriptConf > 0.65 ? 'chip-emerald' : transcriptConf > 0.35 ? 'chip-amber' : 'chip-rose'}`} style={{ fontSize: '9px' }}>
              {Math.round(transcriptConf * 100)}% conf
            </span>
          )}
          {!voiceAvailable && <span className="label-xs">install faster-whisper for transcript</span>}
        </div>
      )}

      {/* Phase 11 — Vision Intelligence badges */}
      {isVisual && (sceneType || probableTask || (activeTools && activeTools.length > 0)) && (
        <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '5px' }}>
          {/* Probable task — natural language */}
          {probableTask && (
            <div style={{ fontSize: '11px', color: 'var(--cyan)', fontStyle: 'italic', opacity: 0.85 }}>
              {probableTask}
            </div>
          )}
          {/* Scene + workflow + tool chips */}
          <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' as const, alignItems: 'center' }}>
            {sceneType && sceneType !== 'unknown' && (
              <span className="chip chip-blue" style={{ fontSize: '9px' }}>{sceneType}</span>
            )}
            {workflowType && workflowType !== 'other' && (
              <span style={{
                fontSize: '9px', padding: '2px 6px', borderRadius: '4px',
                background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.22)',
                color: 'var(--violet)', fontFamily: 'var(--font-geist-mono, monospace)',
              }}>{workflowType}</span>
            )}
            {activeTools && activeTools.slice(0, 3).map(tool => (
              <span key={tool} style={{
                fontSize: '9px', padding: '2px 6px', borderRadius: '4px',
                background: 'rgba(16,217,132,0.08)', border: '1px solid rgba(16,217,132,0.18)',
                color: 'var(--emerald)', fontFamily: 'var(--font-geist-mono, monospace)',
              }}>{tool}</span>
            ))}
            {visionConf !== undefined && visionConf > 0 && (
              <span style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', marginLeft: 'auto' }}>
                {Math.round(visionConf * 100)}% conf
              </span>
            )}
          </div>
        </div>
      )}

      <p style={{ color: 'var(--text-3)', fontSize: '12px', lineHeight: 1.6, margin: 0, fontFamily: 'var(--font-geist-mono, monospace)' }}>
        {preview}
      </p>

      {mediaUrl && (
        <div className="thumb" style={{ maxHeight: '140px' }}>
          <img
            src={mediaUrl}
            alt={item.title}
            style={{ maxHeight: '140px' }}
            onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
          />
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto' }}>
        <span className="label-xs">{item.source}</span>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {result && (
            <>
              {hasSemantic && (
                <span className="chip chip-purple" style={{ fontSize: '9px' }} title={`semantic: ${(result.semantic_score! * 100).toFixed(0)}%`}>
                  ⬡{(result.semantic_score! * 100).toFixed(0)}%
                </span>
              )}
              <span style={{ color: 'var(--emerald)', fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                ↑{result.score}
              </span>
            </>
          )}
          <span className="label-xs">{formatDate(item.created_at)}</span>
        </div>
      </div>
    </div>
  )
}


// ---------------------------------------------------------------------------
// Source citation chip (Phase 4)
// ---------------------------------------------------------------------------

function SourceChip({ source }: { source: ChatSource }) {
  const hasSem = source.semantic_score > 0
  return (
    <div style={{
      flexShrink: 0,
      width: '190px',
      background: '#04040e',
      border: '1px solid #0a1a30',
      borderRadius: '6px',
      padding: '8px 10px',
      display: 'flex',
      flexDirection: 'column',
      gap: '5px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '4px', alignItems: 'flex-start' }}>
        <span style={{ color: '#8a9abb', fontSize: '11px', fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
          {source.title}
        </span>
        <span style={{ color: '#00ff88', fontSize: '10px', fontFamily: 'var(--font-geist-mono, monospace)', flexShrink: 0 }}>
          ↑{source.score}
        </span>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '4px' }}>
        <TypeBadge type={source.type} />
        {hasSem && (
          <span style={{ color: '#a040ff', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)' }}
            title="semantic similarity">
            ⬡{(source.semantic_score * 100).toFixed(0)}%
          </span>
        )}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ color: '#1e3050', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)' }}>{source.source}</span>
        <span style={{ color: '#1a2840', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)' }}>{formatDateShort(source.created_at)}</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Chat message bubble
// ---------------------------------------------------------------------------

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: isUser ? 'flex-end' : 'flex-start' }}>
      <div style={{
        maxWidth: '85%',
        padding: '10px 14px',
        borderRadius: isUser ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
        background: isUser ? '#0a1e38' : '#060614',
        border: `1px solid ${isUser ? '#0e2a4a' : '#0a1830'}`,
        color: isUser ? '#8aaaca' : '#c8d8f0',
        fontSize: '13px',
        lineHeight: 1.7,
        fontFamily: isUser ? 'inherit' : 'inherit',
      }}>
        {msg.streaming && !msg.content ? (
          <span style={{ color: '#1e4060', fontFamily: 'var(--font-geist-mono, monospace)' }}>▌</span>
        ) : (
          <>
            {msg.content}
            {msg.streaming && <span style={{ color: '#00b4ff', animation: 'pulse 0.8s ease-in-out infinite' }}>▌</span>}
          </>
        )}
      </div>

      {/* Metadata row for assistant messages */}
      {!isUser && !msg.streaming && msg.brain_mode && (
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', paddingLeft: '2px' }}>
          <span style={{
            color: msg.brain_mode === 'gemini_hybrid' || msg.brain_mode === 'remote_llm'
              ? '#a78bfa'
              : msg.brain_mode === 'local_llm'
                ? '#00ff88'
                : msg.brain_mode === 'local_semantic'
                  ? '#00c8ff'
                  : '#2a4a6a',
            fontSize: '9px',
            fontFamily: 'var(--font-geist-mono, monospace)',
            border: `1px solid ${
              msg.brain_mode === 'gemini_hybrid' || msg.brain_mode === 'remote_llm'
                ? '#a78bfa33'
                : msg.brain_mode === 'local_llm'
                  ? '#00ff8833'
                  : msg.brain_mode === 'local_semantic'
                    ? '#00c8ff33'
                    : '#0e2040'
            }`,
            padding: '0 5px',
            borderRadius: '3px',
          }}>
            {msg.brain_mode === 'gemini_hybrid' || msg.brain_mode === 'remote_llm'
              ? '⬡ Gemini'
              : msg.brain_mode === 'local_llm'
                ? '⬡ LLM'
                : msg.brain_mode === 'local_semantic'
                  ? '⬡ Local Semantic'
                  : '⬡ rule-based'}
          </span>
          {/* Search metadata — only shown for local search modes, not Gemini */}
          {msg.brain_mode !== 'gemini_hybrid' && msg.brain_mode !== 'remote_llm' && (
            <>
              {msg.query_used && (
                <span style={{ color: '#1e3050', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                  searched: <span style={{ color: '#00b4ff44' }}>{msg.query_used}</span>
                </span>
              )}
              {msg.total_memories !== undefined && (
                <span style={{ color: '#1e3050', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                  {msg.total_memories} mem
                </span>
              )}
            </>
          )}
        </div>
      )}

      {/* Source citations */}
      {!isUser && !msg.streaming && msg.sources && msg.sources.length > 0 && (
        <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', paddingBottom: '2px', maxWidth: '100%' }}>
          {msg.sources.map(s => <SourceChip key={s.id} source={s} />)}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Session card (Phase 5)
// ---------------------------------------------------------------------------

function SessionCard({ session, onClick, onReplay }: { session: Session; onClick: () => void; onReplay: () => void }) {
  const start = new Date(session.start_time)
  const end   = new Date(session.end_time)
  const timeRange = `${start.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })} – ${end.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`

  return (
    <div
      onClick={onClick}
      className="glass-card card-screenshot reveal"
      style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: '10px', cursor: 'pointer' }}
    >
      {/* Row 1: title + replay button + count */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
        <span style={{ fontWeight: 600, color: 'var(--text-1)', fontSize: '13px', flex: 1 }}>
          {session.title}
        </span>
        <div style={{ display: 'flex', gap: '5px', alignItems: 'center', flexShrink: 0 }}>
          <button
            onClick={e => { e.stopPropagation(); onReplay() }}
            className="chip chip-blue"
            style={{ cursor: 'pointer', fontFamily: 'inherit', fontSize: '9px' }}
          >
            ▶ Replay
          </button>
          <span className="chip chip-ghost" style={{ fontSize: '9px' }}>
            {session.memory_count} mem
          </span>
        </div>
      </div>

      {/* Row 2: time range + duration */}
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
        <span className="label-xs">{timeRange}</span>
        <span className="label-xs">{session.duration_str}</span>
      </div>

      {/* Row 3: source badges */}
      {session.main_sources.length > 0 && (
        <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' as const }}>
          {session.main_sources.map(src => (
            <span key={src} className="chip chip-ghost" style={{ fontSize: '9px' }}>{src}</span>
          ))}
        </div>
      )}

      {/* Row 4: topics (app names + key topics) */}
      {session.topics && session.topics.length > 0 && (
        <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' as const }}>
          {session.topics.map(topic => (
            <AppBadge key={topic} appName={topic} />
          ))}
        </div>
      )}

      {/* Row 5: keywords */}
      {session.keywords.length > 0 && (
        <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' as const }}>
          {session.keywords.slice(0, 6).map(kw => (
            <span key={kw} className="label-xs">{kw}</span>
          ))}
        </div>
      )}

      {/* Row 6: summary */}
      <p style={{ color: 'var(--text-4)', fontSize: '11px', margin: 0, lineHeight: 1.5, fontFamily: 'var(--font-geist-mono, monospace)' }}>
        {session.summary}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Phase 4 Chat panel — streaming + sessions
// ---------------------------------------------------------------------------

function ChatPanel() {
  const [open, setOpen]           = useState(false)
  const [input, setInput]         = useState('')
  const [messages, setMessages]   = useState<ChatMessage[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [streaming, setStreaming] = useState(false)
  const [error, setError]         = useState<string | null>(null)
  const textareaRef               = useRef<HTMLTextAreaElement>(null)
  const bottomRef                 = useRef<HTMLDivElement>(null)
  const abortRef                  = useRef<AbortController | null>(null)

  const scrollToBottom = () => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
  }

  const newChat = () => {
    abortRef.current?.abort()
    setMessages([])
    setSessionId(null)
    setError(null)
    setStreaming(false)
    setTimeout(() => textareaRef.current?.focus(), 80)
  }

  const submit = useCallback(async (msg: string) => {
    const trimmed = msg.trim()
    if (!trimmed || streaming) return

    setInput('')
    setError(null)
    setStreaming(true)

    const userMsgId  = crypto.randomUUID()
    const assistantMsgId = crypto.randomUUID()

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', content: trimmed },
      { id: assistantMsgId, role: 'assistant', content: '', streaming: true },
    ])
    scrollToBottom()

    abortRef.current = new AbortController()

    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed, session_id: sessionId }),
        signal: abortRef.current.signal,
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      if (!res.body) throw new Error('No response body')

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer    = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let event: ChatStreamEvent
          try { event = JSON.parse(line.slice(6)) } catch { continue }

          if (event.done) {
            if (event.session_id) setSessionId(event.session_id)
            setMessages(prev => prev.map(m =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    streaming:      false,
                    sources:        event.sources,
                    brain_mode:     event.brain_mode,
                    query_used:     event.query_used,
                    total_memories: event.total_memories,
                  }
                : m
            ))
          } else if (event.delta) {
            setMessages(prev => prev.map(m =>
              m.id === assistantMsgId
                ? { ...m, content: m.content + event.delta }
                : m
            ))
            scrollToBottom()
          }
        }
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') return
      setError(e instanceof Error ? e.message : 'Stream failed')
      setMessages(prev => prev.filter(m => m.id !== assistantMsgId))
    } finally {
      setStreaming(false)
      setMessages(prev => prev.map(m =>
        m.id === assistantMsgId ? { ...m, streaming: false } : m
      ))
    }
  }, [streaming, sessionId])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit(input)
    }
  }

  const handleOpen = () => {
    setOpen(true)
    setTimeout(() => textareaRef.current?.focus(), 80)
  }

  const PROMPTS = [
    'What was I building yesterday?',
    'Summarize my coding work',
    'What was I researching?',
    'What project am I working on?',
  ]

  const hasMessages = messages.length > 0

  return (
    <div style={{ padding: '0 28px', marginBottom: '8px' }}>
      {/* Toggle bar */}
      <button
        onClick={() => (open ? setOpen(false) : handleOpen())}
        style={{
          width: '100%',
          background: open ? '#08081a' : 'transparent',
          border: `1px solid ${open ? '#00b4ff33' : '#0c1e38'}`,
          borderRadius: open ? '8px 8px 0 0' : '8px',
          padding: '10px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          cursor: 'pointer',
          transition: 'border-color 0.15s, background 0.15s',
        }}
      >
        <span style={{ color: '#00b4ff', fontSize: '13px', letterSpacing: '0.08em', fontFamily: 'var(--font-geist-mono, monospace)' }}>
          ⬡ ASK EIDOLON
        </span>
        {sessionId && (
          <span style={{ color: '#1a3a5a', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)', border: '1px solid #0a1e38', padding: '1px 5px', borderRadius: '3px' }}>
            session:{sessionId}
          </span>
        )}
        <span style={{ color: '#1a3a5a', fontSize: '11px', flex: 1, textAlign: 'left' }}>
          {!open && 'Ask anything about your digital memory…'}
        </span>
        <span style={{ color: '#1a3a5a', fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
          {open ? '▲' : '▼'}
        </span>
      </button>

      {/* Expanded panel */}
      {open && (
        <div style={{
          background: '#08081a',
          border: '1px solid #00b4ff33',
          borderTop: 'none',
          borderRadius: '0 0 8px 8px',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}>
          {/* Message history */}
          {hasMessages && (
            <div style={{
              maxHeight: '420px',
              overflowY: 'auto',
              padding: '16px 20px',
              borderBottom: '1px solid #0c1e38',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
            }}>
              {messages.map(msg => <ChatBubble key={msg.id} msg={msg} />)}
              {error && (
                <p style={{ color: '#ff4455', fontSize: '12px', margin: 0, fontFamily: 'var(--font-geist-mono, monospace)' }}>
                  ERROR: {error}
                </p>
              )}
              <div ref={bottomRef} />
            </div>
          )}

          {/* Streaming indicator (when no messages yet in this send) */}
          {streaming && !hasMessages && (
            <div style={{ padding: '14px 20px', display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1px solid #0c1e38' }}>
              <span style={{ color: '#00b4ff', fontSize: '16px', animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
              <span style={{ color: '#1e4060', fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em' }}>
                EIDOLON IS THINKING…
              </span>
            </div>
          )}

          {/* Input area */}
          <div style={{ padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about your digital life… (Enter to send)"
              rows={2}
              className="chat-textarea"
              disabled={streaming}
            />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
              {/* Example prompts / new chat */}
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' as const, flex: 1 }}>
                {!hasMessages
                  ? PROMPTS.map(p => (
                      <button
                        key={p}
                        onClick={() => { setInput(p); submit(p) }}
                        disabled={streaming}
                        style={{
                          background: 'transparent',
                          border: '1px solid #0e2040',
                          color: '#2a5070',
                          fontSize: '10px',
                          padding: '3px 8px',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          fontFamily: 'var(--font-geist-mono, monospace)',
                        }}
                      >
                        {p}
                      </button>
                    ))
                  : (
                      <button
                        onClick={newChat}
                        style={{
                          background: 'transparent',
                          border: '1px solid #0e2040',
                          color: '#2a5070',
                          fontSize: '10px',
                          padding: '3px 10px',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          fontFamily: 'var(--font-geist-mono, monospace)',
                        }}
                      >
                        ↺ New Chat
                      </button>
                    )
                }
              </div>

              <button
                onClick={() => submit(input)}
                disabled={streaming || !input.trim()}
                className="btn-primary"
                style={{ flexShrink: 0, minWidth: '80px' }}
              >
                {streaming ? '…' : 'Ask ↵'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Video Intelligence components
// ---------------------------------------------------------------------------

const EVENT_ICONS: Record<string, string> = {
  person_appeared:  '⬡',
  person_left:      '⬡',
  vehicle_appeared: '◈',
  motion_detected:  '◉',
  crowd_detected:   '◎',
  bag_detected:     '◫',
  object_appeared:  '◌',
}

const EVENT_COLORS: Record<string, string> = {
  person_appeared:  '#00b4ff',
  person_left:      '#2a4a6a',
  vehicle_appeared: '#ffd700',
  motion_detected:  '#ff8c5a',
  crowd_detected:   '#ff4455',
  bag_detected:     '#a040ff',
  object_appeared:  '#00ff88',
}

function VideoStatusBadge({ status, progress }: { status: string; progress: number }) {
  return (
    <span className={`status-pill status-${status}`}>
      <span className="dot" />
      {status === 'analyzing' ? `${progress}%` : status.toUpperCase()}
    </span>
  )
}

function EventCard({ event }: { event: VideoEvent }) {
  const icon  = EVENT_ICONS[event.type] ?? '◌'
  const color = EVENT_COLORS[event.type] ?? '#5a7a9a'
  const ts    = event.timestamp_secs
  const m     = Math.floor(ts / 60)
  const s     = Math.floor(ts % 60)
  const timeStr = `${m}:${s.toString().padStart(2, '0')}`

  return (
    <div className="event-card" style={{ borderColor: `${color}22`, borderLeftColor: `${color}66` }}>
      {event.thumbnail_url && (
        <img
          src={`${API_BASE}${event.thumbnail_url}`}
          alt="event frame"
          style={{ width: '80px', height: '45px', objectFit: 'cover', borderRadius: '4px', flexShrink: 0, border: '1px solid rgba(255,255,255,0.06)' }}
        />
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <span style={{ color, fontSize: '13px' }}>{icon}</span>
          <span style={{ color: 'var(--text-1)', fontSize: '12px', fontWeight: 500 }}>{event.description}</span>
          {event.person_count != null && (
            <span className="chip chip-rose" style={{ fontSize: '9px' }}>
              {event.person_count} persons
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }} className="label-xs">
          <span style={{ color: 'var(--text-3)' }}>{timeStr}</span>
          {event.track_id && <span style={{ color: 'var(--text-4)' }}>track {event.track_id}</span>}
          <span style={{ color }}>{event.type.replace('_', ' ')}</span>
          <span style={{ color: 'var(--text-4)' }}>{Math.round(event.confidence * 100)}%</span>
        </div>
      </div>
    </div>
  )
}

function VideoCard({
  video,
  onClick,
  onDelete,
}: {
  video: VideoRecord
  onClick: () => void
  onDelete: () => void
}) {
  return (
    <div className="video-card" onClick={onClick}>
      {/* Thumbnail */}
      <div className="video-thumb scanlines" style={{ height: '130px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {video.thumbnail_path ? (
          <img
            src={`${API_BASE}${video.thumbnail_path}`}
            alt="video thumbnail"
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <span style={{ fontSize: '40px', color: 'var(--text-4)', opacity: 0.3 }}>⬡</span>
        )}
        {/* Status overlay */}
        <div style={{ position: 'absolute', top: '8px', right: '8px', zIndex: 2 }}>
          <VideoStatusBadge status={video.status} progress={video.progress} />
        </div>
        {/* Duration overlay */}
        {video.duration_secs != null && (
          <div style={{ position: 'absolute', bottom: '8px', right: '8px', zIndex: 2, background: 'rgba(0,0,0,0.75)', color: 'var(--text-2)', fontSize: '10px', padding: '2px 6px', borderRadius: '3px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
            {Math.floor(video.duration_secs / 60)}:{Math.floor(video.duration_secs % 60).toString().padStart(2, '0')}
          </div>
        )}
      </div>

      <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
          {video.original_name}
        </div>

        {/* Labels */}
        {video.labels.length > 0 && (
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' as const }}>
            {video.labels.map(lbl => (
              <span key={lbl} className="chip chip-ghost" style={{ fontSize: '9px' }}>
                {lbl}
              </span>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="label-xs">
            {video.event_count} events{video.resolution && ` · ${video.resolution}`}
          </span>
          <button
            onClick={e => { e.stopPropagation(); onDelete() }}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-4)', fontSize: '13px', cursor: 'pointer', padding: '0 2px', lineHeight: 1, transition: 'color 0.15s' }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--rose)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-4)')}
            title="Delete video"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main dashboard
// ---------------------------------------------------------------------------

export default function Dashboard() {
  // ── Timeline state ──────────────────────────────────────
  const [items, setItems]               = useState<MemoryItem[]>([])
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null)
  const [semanticMode, setSemanticMode] = useState(false)
  const [query, setQuery]               = useState('')
  const [loading, setLoading]           = useState(false)
  const [searching, setSearching]       = useState(false)
  const [error, setError]               = useState<string | null>(null)

  // ── Session state ───────────────────────────────────────
  const [activeTab, setActiveTab]             = useState<'timeline' | 'sessions' | 'videos' | 'graph' | 'profile' | 'agent' | 'replay' | 'soul' | 'trends'>('timeline')
  const [sessions, setSessions]               = useState<Session[]>([])
  const [sessionsLoaded, setSessionsLoaded]   = useState(false)
  const [loadingSessions, setLoadingSessions] = useState(false)
  const [activeSession, setActiveSession]     = useState<SessionDetail | null>(null)
  const [loadingSession, setLoadingSession]   = useState(false)

  // ── Replay state ─────────────────────────────────────────
  const [activeReplay, setActiveReplay]       = useState<ReplayData | null>(null)

  // ── PDF upload state ──────────────────────────────────────
  const [uploadingPdf, setUploadingPdf]       = useState(false)
  const [pdfUploadError, setPdfUploadError]   = useState<string | null>(null)
  const pdfInputRef                           = useRef<HTMLInputElement>(null)

  // ── PDF chat state ────────────────────────────────────────
  const [pdfChatTarget, setPdfChatTarget]     = useState<MemoryItem | null>(null)

  // ── Audio upload state ────────────────────────────────────
  const [uploadingAudio, setUploadingAudio]   = useState(false)
  const [audioUploadError, setAudioUploadError] = useState<string | null>(null)
  const audioInputRef                         = useRef<HTMLInputElement>(null)

  // ── Suggestions state ─────────────────────────────────────
  const [suggestions, setSuggestions]         = useState<Suggestion[]>([])
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [dismissedIds, setDismissedIds]       = useState<Set<string>>(new Set())

  // ── Video Intelligence state ──────────────────────────────
  const [videos, setVideos]                   = useState<VideoRecord[]>([])
  const [videosLoaded, setVideosLoaded]       = useState(false)
  const [loadingVideos, setLoadingVideos]     = useState(false)
  const [activeVideo, setActiveVideo]         = useState<VideoRecord | null>(null)
  const [videoEvents, setVideoEvents]         = useState<VideoEvent[]>([])
  const [loadingVideoEvents, setLoadingVideoEvents] = useState(false)
  const [uploadingVideo, setUploadingVideo]   = useState(false)
  const [videoUploadError, setVideoUploadError] = useState<string | null>(null)
  const [videoEventFilter, setVideoEventFilter] = useState<string | null>(null)
  const videoInputRef                         = useRef<HTMLInputElement>(null)
  const videoPollRef                          = useRef<ReturnType<typeof setInterval> | null>(null)
  const [uploadingVisionVideo, setUploadingVisionVideo] = useState(false)
  const [visionVideoError, setVisionVideoError]         = useState<string | null>(null)
  const visionVideoInputRef                             = useRef<HTMLInputElement>(null)

  // ── Live Camera / CCTV state ──────────────────────────────
  const [cameraRunning, setCameraRunning]     = useState(false)
  const [cameraStatus, setCameraStatus]       = useState<CameraStatus | null>(null)
  const [cameraLoading, setCameraLoading]     = useState(false)
  const cameraPollRef                         = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Browser camera preview (frontend-only, no backend) ────
  const [previewActive, setPreviewActive]     = useState(false)
  const [previewError, setPreviewError]       = useState<string | null>(null)
  const previewVideoRef                       = useRef<HTMLVideoElement>(null)
  const previewStreamRef                      = useRef<MediaStream | null>(null)

  // ── Prediction layer ──────────────────────────────────────
  const [predictions, setPredictions]         = useState<PredictionItem[]>([])

  // ── Graph state ───────────────────────────────────────────
  const [graphData, setGraphData]             = useState<GraphData | null>(null)
  const [loadingGraph, setLoadingGraph]       = useState(false)
  const [graphLoaded, setGraphLoaded]         = useState(false)

  // ── Profile state ─────────────────────────────────────────
  const [profileData, setProfileData]         = useState<ProfileData | null>(null)
  const [loadingProfile, setLoadingProfile]   = useState(false)
  const [profileLoaded, setProfileLoaded]     = useState(false)

  // ── Intelligence / Cognitive Profile (Phase 21) ───────────
  const [cogProfile, setCogProfile]           = useState<CognitiveProfile | null>(null)
  const [cogLoaded, setCogLoaded]             = useState(false)
  const [loadingCog, setLoadingCog]           = useState(false)
  const [trendsData, setTrendsData]           = useState<TrendsTimeline | null>(null)
  const [trendsLoaded, setTrendsLoaded]       = useState(false)
  const [loadingTrends, setLoadingTrends]     = useState(false)

  // ── Agent state ───────────────────────────────────────────
  const [agentActions, setAgentActions]       = useState<AgentAction[]>([])
  const [agentResult, setAgentResult]         = useState<AgentResult | null>(null)
  const [agentExecuting, setAgentExecuting]   = useState(false)
  const [agentExecutingId, setAgentExecutingId] = useState<string | null>(null)
  const [quickBtnLoading, setQuickBtnLoading] = useState<string | null>(null)
  const [dailySummary, setDailySummary]       = useState<DailySummary | null>(null)
  const [workflowPeriods, setWorkflowPeriods] = useState<WorkflowPeriod[]>([])
  const [agentLoaded, setAgentLoaded]         = useState(false)
  const [screenWatchRunning, setScreenWatchRunning] = useState(false)

  // ── Phase 13: Replay 2.0 ─────────────────────────────────
  const [replayTab, setReplayTab]             = useState<'day' | 'topic' | 'modality'>('day')
  const [replayDate, setReplayDate]           = useState('')
  const [replayQuery, setReplayQuery]         = useState('')
  const [replayModality, setReplayModality]   = useState('screenshot')
  const [replayResult, setReplayResult]       = useState<ReplayResult | null>(null)
  const [loadingReplay, setLoadingReplay]     = useState(false)

  // ── Phase 14: Digital Soul ────────────────────────────────
  const [soulPatterns, setSoulPatterns]       = useState<SoulPattern[]>([])
  const [workflowRhythm, setWorkflowRhythm]   = useState<SoulWorkflowRhythm | null>(null)
  const [projectMemory, setProjectMemory]     = useState<SoulProjectMemory | null>(null)
  const [soulLoaded, setSoulLoaded]           = useState(false)
  const [loadingSoul, setLoadingSoul]         = useState(false)

  // ── Phase 15: Neural Search ───────────────────────────────
  const [neuralResults, setNeuralResults]     = useState<NeuralSearchResponse | null>(null)

  // ── Phase 16: Multi-Camera ────────────────────────────────
  const [multiCameras, setMultiCameras]       = useState<MultiCamera[]>([])
  const [mcAddName, setMcAddName]             = useState('')
  const [mcAddSource, setMcAddSource]         = useState('0')
  const [mcAddType, setMcAddType]             = useState<'webcam' | 'rtsp' | 'file'>('webcam')
  const [mcAdding, setMcAdding]               = useState(false)

  // ── Phase 17: World Model ─────────────────────────────────
  const [worldState, setWorldState]           = useState<WorldState | null>(null)
  const [loadingWorld, setLoadingWorld]       = useState(false)

  // ── Phase 18: Brain Status ────────────────────────────────
  const [brainStatus, setBrainStatus]         = useState<BrainStatus | null>(null)
  const [brainChatMsg, setBrainChatMsg]         = useState('')
  const [brainChatAnswer, setBrainChatAnswer]   = useState<string | null>(null)
  const [brainChatLoading, setBrainChatLoading] = useState(false)
  const [brainChatNotice, setBrainChatNotice]   = useState<string | null>(null)
  const [brainChatError, setBrainChatError]     = useState<string | null>(null)

  // ── Timeline ─────────────────────────────────────────────
  const fetchTimeline = useCallback(async () => {
    setLoading(true)
    setError(null)
    setSearchResults(null)
    setSemanticMode(false)
    setQuery('')
    try {
      const res = await fetch(`${API_BASE}/memory/timeline`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setItems(data.items ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to connect to backend')
    } finally {
      setLoading(false)
    }
  }, [])

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) { fetchTimeline(); return }
    setSearching(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/memory/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: MemorySearchResponse = await res.json()
      setSearchResults(data.results ?? [])
      setSemanticMode(data.semantic_mode ?? false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed')
    } finally {
      setSearching(false)
    }
  }

  // ── Sessions ─────────────────────────────────────────────
  const fetchSessions = useCallback(async () => {
    setLoadingSessions(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/sessions/list`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setSessions(data.sessions ?? [])
      setSessionsLoaded(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load sessions')
    } finally {
      setLoadingSessions(false)
    }
  }, [])

  const openSession = async (sessionId: string) => {
    setLoadingSession(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/sessions/${sessionId}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: SessionDetail = await res.json()
      setActiveSession(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load session')
    } finally {
      setLoadingSession(false)
    }
  }

  const switchTab = (tab: 'timeline' | 'sessions' | 'videos' | 'graph' | 'profile' | 'agent' | 'replay' | 'soul' | 'trends') => {
    setActiveTab(tab)
    setError(null)
    setActiveSession(null)
    setActiveVideo(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
    if (tab === 'sessions' && !sessionsLoaded) fetchSessions()
    if (tab === 'videos'   && !videosLoaded)   fetchVideos()
    if (tab === 'videos')                      { fetchCameraStatus(); fetchMultiCameras(); fetchWorldState() }
    if (tab === 'graph'    && !graphLoaded)     fetchGraph()
    if (tab === 'profile'  && !profileLoaded)  fetchProfile()
    if (tab === 'profile'  && !cogLoaded)      fetchCogProfile()
    if (tab === 'trends'   && !trendsLoaded)   fetchTrends()
    if (tab === 'agent'    && !agentLoaded)     fetchAgentData()
    if (tab === 'soul'     && !soulLoaded)      fetchSoulData()
  }

  const handleRefresh = () => {
    if (activeTab === 'timeline') {
      fetchTimeline()
    } else if (activeTab === 'videos') {
      setVideosLoaded(false); setActiveVideo(null); fetchVideos()
    } else if (activeTab === 'graph') {
      setGraphLoaded(false); fetchGraph()
    } else if (activeTab === 'profile') {
      setProfileLoaded(false); fetchProfile()
      setCogLoaded(false); fetchCogProfile()
    } else if (activeTab === 'trends') {
      setTrendsLoaded(false); fetchTrends()
    } else {
      setSessionsLoaded(false); setActiveSession(null); fetchSessions()
    }
  }

  const openReplay = async (sessionId: string) => {
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/sessions/${sessionId}/replay`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: ReplayData = await res.json()
      setActiveReplay(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load replay')
    }
  }

  // ── PDF upload ───────────────────────────────────────────
  const uploadPdf = async (file: File) => {
    setUploadingPdf(true)
    setPdfUploadError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API_BASE}/memory/ingest-pdf`, { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error((err as { detail?: string }).detail || `HTTP ${res.status}`)
      }
      await res.json()
      fetchTimeline()  // show new memory immediately
    } catch (e) {
      setPdfUploadError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploadingPdf(false)
      if (pdfInputRef.current) pdfInputRef.current.value = ''
    }
  }

  // ── Audio upload ─────────────────────────────────────────
  const uploadAudio = async (file: File) => {
    setUploadingAudio(true)
    setAudioUploadError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API_BASE}/memory/ingest-audio`, { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error((err as { detail?: string }).detail || `HTTP ${res.status}`)
      }
      await res.json()
      fetchTimeline()
    } catch (e) {
      setAudioUploadError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploadingAudio(false)
      if (audioInputRef.current) audioInputRef.current.value = ''
    }
  }

  // ── Vision video upload (toolbar — posts to /vision/ingest-video) ─────────
  const uploadVisionVideo = async (file: File) => {
    setUploadingVisionVideo(true)
    setVisionVideoError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API_BASE}/vision/ingest-video`, { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error((err as { detail?: string }).detail || `HTTP ${res.status}`)
      }
      await res.json()
      fetchTimeline()
      setVideosLoaded(false)
    } catch (e) {
      setVisionVideoError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploadingVisionVideo(false)
      if (visionVideoInputRef.current) visionVideoInputRef.current.value = ''
    }
  }

  // ── Live Camera ──────────────────────────────────────────
  const fetchCameraStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/vision/camera/status`)
      if (!res.ok) return
      const data: CameraStatus = await res.json()
      setCameraStatus(data)
      setCameraRunning(data.running)
    } catch { /* non-critical */ }
  }, [])

  const startCamera = async () => {
    setCameraLoading(true)
    try {
      const res = await fetch(`${API_BASE}/vision/camera/start`, { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: CameraStatus & { success: boolean } = await res.json()
      setCameraStatus(data)
      setCameraRunning(data.running)
    } catch (e) {
      setCameraStatus(prev => prev
        ? { ...prev, error: e instanceof Error ? e.message : 'Failed to start camera' }
        : { running: false, camera_available: null, detection_mode: 'unknown', last_event_time: null, event_count: 0, error: e instanceof Error ? e.message : 'Failed to start camera' }
      )
    } finally {
      setCameraLoading(false)
    }
  }

  const stopCamera = async () => {
    setCameraLoading(true)
    try {
      const res = await fetch(`${API_BASE}/vision/camera/stop`, { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: CameraStatus & { success: boolean } = await res.json()
      setCameraStatus(data)
      setCameraRunning(data.running)
    } catch { /* non-critical */ }
    finally {
      setCameraLoading(false)
    }
  }

  // ── Browser camera preview functions ────────────────────
  const startPreview = async () => {
    setPreviewError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      previewStreamRef.current = stream
      // ref is always in DOM (display toggle), so srcObject assignment always works
      if (previewVideoRef.current) {
        previewVideoRef.current.srcObject = stream
      }
      setPreviewActive(true)
    } catch (e) {
      let msg = 'Camera access denied or unavailable'
      if (e instanceof Error) {
        if (e.name === 'NotAllowedError')    msg = 'Camera permission denied — allow camera access in browser settings'
        else if (e.name === 'NotFoundError') msg = 'No camera found — connect a webcam and try again'
        else if (e.name === 'NotReadableError') msg = 'Camera is already in use by another application'
        else msg = e.message
      }
      setPreviewError(msg)
      setPreviewActive(false)
    }
  }

  const stopPreview = () => {
    if (previewStreamRef.current) {
      previewStreamRef.current.getTracks().forEach(t => t.stop())
      previewStreamRef.current = null
    }
    if (previewVideoRef.current) {
      previewVideoRef.current.srcObject = null
    }
    setPreviewActive(false)
    setPreviewError(null)
  }

  // Cleanup preview stream on unmount
  useEffect(() => {
    return () => {
      if (previewStreamRef.current) {
        previewStreamRef.current.getTracks().forEach(t => t.stop())
      }
    }
  }, [])

  const fetchPredictions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/vision/camera/predictions/active`)
      if (!res.ok) return
      const data: { predictions: PredictionItem[] } = await res.json()
      setPredictions(data.predictions ?? [])
    } catch { /* non-critical */ }
  }, [])

  // Poll camera status + predictions every 3s when running + on videos tab
  useEffect(() => {
    if (cameraRunning && activeTab === 'videos') {
      if (!cameraPollRef.current) {
        cameraPollRef.current = setInterval(() => {
          fetchCameraStatus()
          fetchPredictions()
        }, 3000)
      }
    } else {
      if (cameraPollRef.current) { clearInterval(cameraPollRef.current); cameraPollRef.current = null }
      if (!cameraRunning) setPredictions([])
    }
    return () => { if (cameraPollRef.current) { clearInterval(cameraPollRef.current); cameraPollRef.current = null } }
  }, [cameraRunning, activeTab, fetchCameraStatus, fetchPredictions])

  // ── Suggestions ───────────────────────────────────────────
  const fetchSuggestions = useCallback(async () => {
    setLoadingSuggestions(true)
    try {
      const res = await fetch(`${API_BASE}/suggestions`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setSuggestions(data.suggestions ?? [])
    } catch {
      // Suggestions are non-critical — fail silently
    } finally {
      setLoadingSuggestions(false)
    }
  }, [])

  // ── Video Intelligence ────────────────────────────────────
  const fetchVideos = useCallback(async () => {
    setLoadingVideos(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/video/list`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setVideos(data.videos ?? [])
      setVideosLoaded(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load videos')
    } finally {
      setLoadingVideos(false)
    }
  }, [])

  const uploadVideo = async (file: File) => {
    setUploadingVideo(true)
    setVideoUploadError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API_BASE}/video/upload`, { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error((err as { detail?: string }).detail || `HTTP ${res.status}`)
      }
      await res.json()
      fetchVideos()
    } catch (e) {
      setVideoUploadError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploadingVideo(false)
      if (videoInputRef.current) videoInputRef.current.value = ''
    }
  }

  const openVideoDetail = async (v: VideoRecord) => {
    setActiveVideo(v)
    setVideoEventFilter(null)
    setLoadingVideoEvents(true)
    try {
      const res = await fetch(`${API_BASE}/video/${v.id}/events?limit=200`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setVideoEvents(data.events ?? [])
    } catch {
      setVideoEvents([])
    } finally {
      setLoadingVideoEvents(false)
    }
  }

  const deleteVideo = async (videoId: string) => {
    try {
      await fetch(`${API_BASE}/video/${videoId}`, { method: 'DELETE' })
      setVideos(prev => prev.filter(v => v.id !== videoId))
      if (activeVideo?.id === videoId) setActiveVideo(null)
    } catch { /* non-critical */ }
  }

  // Poll in-progress videos every 3s
  useEffect(() => {
    const hasActive = videos.some(v => v.status === 'analyzing' || v.status === 'pending')
    if (hasActive && activeTab === 'videos') {
      if (!videoPollRef.current) {
        videoPollRef.current = setInterval(fetchVideos, 3000)
      }
    } else {
      if (videoPollRef.current) {
        clearInterval(videoPollRef.current)
        videoPollRef.current = null
      }
    }
    return () => {
      if (videoPollRef.current) { clearInterval(videoPollRef.current); videoPollRef.current = null }
    }
  }, [videos, activeTab, fetchVideos])

  // ── Graph ─────────────────────────────────────────────────
  const fetchGraph = useCallback(async () => {
    setLoadingGraph(true)
    try {
      const res = await fetch(`${API_BASE}/graph/overview`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: GraphData = await res.json()
      setGraphData(data)
      setGraphLoaded(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load graph')
    } finally {
      setLoadingGraph(false)
    }
  }, [])

  // ── Profile ───────────────────────────────────────────────
  const fetchProfile = useCallback(async () => {
    setLoadingProfile(true)
    try {
      const res = await fetch(`${API_BASE}/profile/summary`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: ProfileData = await res.json()
      setProfileData(data)
      setProfileLoaded(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load profile')
    } finally {
      setLoadingProfile(false)
    }
  }, [])

  // ── Cognitive Profile (Phase 21) ──────────────────────────
  const fetchCogProfile = useCallback(async () => {
    setLoadingCog(true)
    try {
      const res = await fetch(`${API_BASE}/intelligence/profile`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: CognitiveProfile = await res.json()
      setCogProfile(data)
      setCogLoaded(true)
    } catch { /* non-critical */ } finally {
      setLoadingCog(false)
    }
  }, [])

  const fetchTrends = useCallback(async () => {
    setLoadingTrends(true)
    try {
      const res = await fetch(`${API_BASE}/intelligence/timeline`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: TrendsTimeline = await res.json()
      setTrendsData(data)
      setTrendsLoaded(true)
    } catch { /* non-critical */ } finally {
      setLoadingTrends(false)
    }
  }, [])

  const dismissSuggestion = async (id: string) => {
    try {
      await fetch(`${API_BASE}/suggestions/${id}/dismiss`, { method: 'POST' })
      setDismissedIds(prev => new Set([...prev, id]))
    } catch { /* non-critical */ }
  }

  // ── Agent ─────────────────────────────────────────────────
  const fetchAgentData = useCallback(async () => {
    try {
      const [actRes, sumRes, wfRes, statusRes] = await Promise.all([
        fetch(`${API_BASE}/agent/actions`),
        fetch(`${API_BASE}/agent/daily-summary`),
        fetch(`${API_BASE}/agent/workflow`),
        fetch(`${API_BASE}/agent/status`),
      ])
      if (actRes.ok) {
        const d = await actRes.json()
        setAgentActions(d.actions ?? [])
      }
      if (sumRes.ok) {
        const d: DailySummary = await sumRes.json()
        setDailySummary(d)
      }
      if (wfRes.ok) {
        const d = await wfRes.json()
        setWorkflowPeriods(d.periods ?? [])
      }
      if (statusRes.ok) {
        const d = await statusRes.json()
        setScreenWatchRunning(d.screen_watch_running ?? false)
      }
      setAgentLoaded(true)
    } catch { /* non-critical */ }
  }, [])

  const executeAgentAction = async (actionName: string, args: Record<string, unknown> = {}) => {
    setAgentExecuting(true)
    setAgentExecutingId(actionName)
    setAgentResult(null)
    try {
      const res = await fetch(`${API_BASE}/agent/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: actionName, args }),
      })
      const data: AgentResult = await res.json()
      setAgentResult(data)
      // Refresh screen watch status after start/stop
      if (actionName === 'start_screen_watch' || actionName === 'stop_screen_watch') {
        setScreenWatchRunning(data.running as boolean ?? false)
      }
      // Refresh summary after summarize
      if (actionName === 'summarize_today') {
        setDailySummary(data as unknown as DailySummary)
      }
    } catch (e) {
      setAgentResult({ success: false, message: e instanceof Error ? e.message : 'Action failed' })
    } finally {
      setAgentExecuting(false)
      setAgentExecutingId(null)
    }
  }

  const runQuickAction = async (btnId: string, actionName: string, args: Record<string, unknown> = {}) => {
    setQuickBtnLoading(btnId)
    setAgentResult(null)
    try {
      const res = await fetch(`${API_BASE}/agent/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: actionName, args }),
      })
      const data: AgentResult = await res.json()
      setAgentResult(data)
      if (actionName === 'summarize_today') {
        setDailySummary(data as unknown as DailySummary)
      }
    } catch (e) {
      setAgentResult({ success: false, message: e instanceof Error ? e.message : 'Action failed' })
    } finally {
      setQuickBtnLoading(null)
    }
  }

  // ── Phase 13: Replay ─────────────────────────────────────
  const runReplay = async () => {
    setLoadingReplay(true)
    setReplayResult(null)
    try {
      let url = ''
      if (replayTab === 'day') {
        const d = replayDate || new Date().toISOString().slice(0, 10)
        url = `${API_BASE}/replay/day?date=${encodeURIComponent(d)}`
      } else if (replayTab === 'topic') {
        if (!replayQuery.trim()) return
        url = `${API_BASE}/replay/topic?query=${encodeURIComponent(replayQuery.trim())}`
      } else {
        url = `${API_BASE}/replay/modality?type=${encodeURIComponent(replayModality)}`
      }
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: ReplayResult = await res.json()
      setReplayResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Replay failed')
    } finally {
      setLoadingReplay(false)
    }
  }

  // ── Phase 14: Digital Soul ────────────────────────────────
  const fetchSoulData = useCallback(async () => {
    if (loadingSoul) return
    setLoadingSoul(true)
    try {
      const [patRes, rhythmRes, projRes] = await Promise.all([
        fetch(`${API_BASE}/soul/patterns`),
        fetch(`${API_BASE}/soul/workflow-rhythm`),
        fetch(`${API_BASE}/soul/project-memory`),
      ])
      if (patRes.ok)    setSoulPatterns((await patRes.json()).patterns ?? [])
      if (rhythmRes.ok) setWorkflowRhythm(await rhythmRes.json())
      if (projRes.ok)   setProjectMemory(await projRes.json())
      setSoulLoaded(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load soul data')
    } finally {
      setLoadingSoul(false)
    }
  }, [loadingSoul])

  // ── Phase 16: Multi-Camera ────────────────────────────────
  const fetchMultiCameras = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/cameras/list`)
      if (res.ok) {
        const data = await res.json()
        setMultiCameras(data.cameras ?? [])
      }
    } catch { /* non-critical */ }
  }, [])

  const addMultiCamera = async () => {
    if (!mcAddName.trim()) return
    setMcAdding(true)
    try {
      const res = await fetch(`${API_BASE}/cameras/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: mcAddName.trim(), source_type: mcAddType, source: mcAddSource }),
      })
      if (res.ok) {
        setMcAddName(''); setMcAddSource('0')
        await fetchMultiCameras()
      }
    } catch { /* non-critical */ } finally {
      setMcAdding(false)
    }
  }

  const startMultiCam = async (id: string) => {
    await fetch(`${API_BASE}/cameras/${id}/start`, { method: 'POST' })
    await fetchMultiCameras()
  }

  const stopMultiCam = async (id: string) => {
    await fetch(`${API_BASE}/cameras/${id}/stop`, { method: 'POST' })
    await fetchMultiCameras()
  }

  const deleteMultiCam = async (id: string) => {
    await fetch(`${API_BASE}/cameras/${id}`, { method: 'DELETE' })
    await fetchMultiCameras()
  }

  // ── Phase 17: World Model ─────────────────────────────────
  const fetchWorldState = useCallback(async () => {
    if (loadingWorld) return
    setLoadingWorld(true)
    try {
      const res = await fetch(`${API_BASE}/world/state`)
      if (res.ok) setWorldState(await res.json())
    } catch { /* non-critical */ } finally {
      setLoadingWorld(false)
    }
  }, [loadingWorld])

  // ── Phase 18: Brain ───────────────────────────────────────
  const fetchBrainStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/brain/status`)
      if (res.ok) setBrainStatus(await res.json())
    } catch { /* non-critical */ }
  }, [])

  const sendBrainChat = async () => {
    if (!brainChatMsg.trim()) return
    setBrainChatLoading(true)
    setBrainChatAnswer(null)
    setBrainChatNotice(null)
    setBrainChatError(null)
    try {
      const res = await fetch(`${API_BASE}/brain/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: brainChatMsg.trim() }),
      })
      if (res.ok) {
        const data = await res.json()
        setBrainChatAnswer(data.answer ?? '')
        if (data.status === 'quota_exceeded' || data.fallback_used) {
          const retry = data.retry_after_seconds
            ? ` · retry in ${data.retry_after_seconds}s`
            : ''
          setBrainChatNotice(`Gemini limited · local fallback active${retry}`)
        }
        // Sync orb immediately after a chat response (don't wait for 30s poll)
        fetchBrainStatus()
      } else {
        setBrainChatError('The brain is not responding. Make sure the backend is running.')
      }
    } catch {
      setBrainChatError('Cannot reach the backend on port 8010. Is it running?')
    } finally {
      setBrainChatLoading(false)
    }
  }

  // ── Init ─────────────────────────────────────────────────
  useEffect(() => { fetchTimeline() }, [fetchTimeline])
  useEffect(() => { fetchSuggestions() }, [fetchSuggestions])
  useEffect(() => { fetchBrainStatus() }, [fetchBrainStatus])
  // Poll brain status every 30 s to keep the Cognitive Core Orb in sync
  useEffect(() => {
    const id = setInterval(() => { fetchBrainStatus() }, 30_000)
    return () => clearInterval(id)
  }, [fetchBrainStatus])

  const isSearch = searchResults !== null
  const count = isSearch ? searchResults!.length : items.length

  return (
    <div style={{ minHeight: '100vh', color: 'var(--text-1)' }}>
      {/* Cinematic background */}
      <div className="eidolon-bg">
        <div className="bg-orb bg-orb-1" />
        <div className="bg-orb bg-orb-2" />
        <div className="bg-orb bg-orb-3" />
      </div>

      {/* Content layer above cinematic background */}
      <div style={{ position: 'relative', zIndex: 1 }}>

      {/* ── Header ── */}
      <header className="glass-header" style={{
        padding: '14px 28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky' as const,
        top: 0,
        zIndex: 10,
      }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '18px', fontWeight: 700, letterSpacing: '0.12em' }}>
            <span style={{ color: 'var(--blue)' }} className="glow-text">EIDOLON</span>
            <span style={{ color: 'var(--text-4)', margin: '0 6px' }}>·</span>
            <span style={{ color: 'var(--text-3)' }}>OS</span>
          </h1>
          <p style={{ margin: 0 }} className="label-xs">
            Local-First AI Cognitive OS · Phase 20
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <a
            href={`${API_BASE}/export/memories`}
            download
            className="btn-ghost"
            style={{ fontSize: '10px', padding: '5px 10px', textDecoration: 'none' }}
            title="Download all memories as JSON"
          >
            ↓ Memories
          </a>
          <a
            href={`${API_BASE}/export/sessions`}
            download
            className="btn-ghost"
            style={{ fontSize: '10px', padding: '5px 10px', textDecoration: 'none' }}
            title="Download all sessions as JSON"
          >
            ↓ Sessions
          </a>
          {/* ── Cognitive Core Orb (Phase 21) ── */}
          {(() => {
            // Derive orb state: green=LLM live, yellow=fallback/quota, red=lockdown/offline
            const isLockdown = brainStatus?.lockdown === true
            const orbColor  = !brainStatus || isLockdown ? '#ef4444'
                            : brainStatus.llm_active     ? '#22c55e'
                            : '#eab308'
            const orbLabel  = !brainStatus                          ? 'OFFLINE'
                            : isLockdown                            ? 'LOCKED'
                            : brainStatus.llm_active                ? brainStatus.brain_provider.toUpperCase()
                            : brainStatus.quota_limited             ? 'LIMITED'
                            : 'LOCAL'
            const orbTip    = !brainStatus
                            ? 'Cognitive Core: backend unreachable'
                            : isLockdown
                            ? 'Cognitive Core: system lockdown active'
                            : brainStatus.quota_limited
                            ? `Cognitive Core · Gemini limited · local fallback active` +
                              (brainStatus.retry_after_seconds ? ` · retry in ${brainStatus.retry_after_seconds}s` : '')
                            : `Cognitive Core · ${brainStatus.brain_provider} · ${brainStatus.mode}` +
                              (brainStatus.fallback_used ? ' (fallback)' : '') +
                              (brainStatus.model ? ` · ${brainStatus.model}` : '')
            return (
              <div
                title={orbTip}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'default', userSelect: 'none' as const }}
              >
                <style>{`@keyframes orb-pulse{0%,100%{transform:scale(1);opacity:.6}50%{transform:scale(1.55);opacity:.15}}`}</style>
                {/* Orb: pulsing ring + solid core */}
                <div style={{ position: 'relative', width: 20, height: 20, flexShrink: 0 }}>
                  <div style={{
                    position: 'absolute', inset: 0, borderRadius: '50%',
                    background: orbColor, opacity: 0.22,
                    animation: 'orb-pulse 2.6s ease-in-out infinite',
                  }} />
                  <div style={{
                    position: 'absolute', inset: '5px', borderRadius: '50%',
                    background: orbColor,
                    boxShadow: `0 0 7px 2px ${orbColor}55`,
                  }} />
                </div>
                <span style={{
                  fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)',
                  letterSpacing: '0.12em', color: orbColor, fontWeight: 700,
                }}>
                  {orbLabel}
                </span>
              </div>
            )
          })()}
          {isSearch && (
            <span className={`chip ${semanticMode ? 'chip-purple' : 'chip-ghost'}`} style={{ fontSize: '10px' }}>
              {semanticMode ? '⬡ semantic' : '⬡ keyword'}
            </span>
          )}
        </div>
      </header>

      {/* ── Search bar (Timeline only) ── */}
      {activeTab === 'timeline' && (
        <div style={{ padding: '18px 28px 0' }}>
          <form onSubmit={handleSearch} style={{ display: 'flex', gap: '8px', maxWidth: '720px' }}>
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search memories — screenshots, PDFs, voice, video…"
              className="search-input"
              style={{ flex: 1 }}
            />
            <button type="submit" disabled={searching} className="btn-primary" style={{ minWidth: '90px' }}>
              {searching ? '…' : 'Search'}
            </button>
            {isSearch && (
              <button type="button" onClick={fetchTimeline} className="btn-ghost">Clear</button>
            )}
          </form>
        </div>
      )}

      {/* ── Hidden file inputs ── */}
      <input ref={pdfInputRef}         type="file" accept=".pdf"                        style={{ display: 'none' }} onChange={e => { const f = e.target.files?.[0]; if (f) uploadPdf(f) }} />
      <input ref={audioInputRef}       type="file" accept=".mp3,.wav,.m4a,.ogg,.flac,.webm" style={{ display: 'none' }} onChange={e => { const f = e.target.files?.[0]; if (f) uploadAudio(f) }} />
      <input ref={visionVideoInputRef} type="file" accept=".mp4,.avi,.mov,.mkv"          style={{ display: 'none' }} onChange={e => { const f = e.target.files?.[0]; if (f) uploadVisionVideo(f) }} />
      <input ref={videoInputRef}       type="file" accept=".mp4,.avi,.mov,.mkv,.wmv,.webm,.m4v" style={{ display: 'none' }} onChange={e => { const f = e.target.files?.[0]; if (f) uploadVideo(f) }} />

      {/* ── Action bar ── */}
      <div style={{
        padding: '14px 28px',
        display: 'flex',
        gap: '10px',
        flexWrap: 'wrap' as const,
        alignItems: 'center',
        borderBottom: '1px solid rgba(0,212,255,0.07)',
        background: 'rgba(4,4,16,0.6)',
        backdropFilter: 'blur(12px)',
      }}>
        {/* Upload PDF */}
        <button
          type="button"
          onClick={() => pdfInputRef.current?.click()}
          disabled={uploadingPdf}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '8px',
            padding: '10px 18px', borderRadius: '10px', cursor: uploadingPdf ? 'default' as const : 'pointer' as const,
            fontSize: '13px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 500,
            border: '1px solid rgba(255,107,53,0.35)', color: uploadingPdf ? 'rgba(255,107,53,0.45)' : 'var(--orange)',
            background: uploadingPdf ? 'rgba(255,107,53,0.05)' : 'rgba(255,107,53,0.08)',
            transition: 'all 0.2s', whiteSpace: 'nowrap' as const,
            boxShadow: uploadingPdf ? 'none' : '0 0 14px rgba(255,107,53,0.1)',
          }}
          title="Upload PDF to extract and search text"
        >
          <span style={{ fontSize: '15px' }}>◫</span>
          {uploadingPdf ? 'Uploading…' : 'Upload PDF'}
        </button>

        {/* Upload Audio */}
        <button
          type="button"
          onClick={() => audioInputRef.current?.click()}
          disabled={uploadingAudio}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '8px',
            padding: '10px 18px', borderRadius: '10px', cursor: uploadingAudio ? 'default' as const : 'pointer' as const,
            fontSize: '13px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 500,
            border: '1px solid rgba(224,64,251,0.35)', color: uploadingAudio ? 'rgba(224,64,251,0.45)' : 'var(--magenta)',
            background: uploadingAudio ? 'rgba(224,64,251,0.04)' : 'rgba(224,64,251,0.07)',
            transition: 'all 0.2s', whiteSpace: 'nowrap' as const,
            boxShadow: uploadingAudio ? 'none' : '0 0 14px rgba(224,64,251,0.1)',
          }}
          title="Upload audio for voice transcription"
        >
          <span style={{ fontSize: '15px' }}>◎</span>
          {uploadingAudio ? 'Transcribing…' : 'Upload Audio'}
        </button>

        {/* Upload Video — prominent */}
        <button
          type="button"
          onClick={() => visionVideoInputRef.current?.click()}
          disabled={uploadingVisionVideo}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '8px',
            padding: '10px 22px', borderRadius: '10px', cursor: uploadingVisionVideo ? 'default' as const : 'pointer' as const,
            fontSize: '13px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 600,
            border: `1px solid ${uploadingVisionVideo ? 'rgba(124,58,237,0.3)' : 'rgba(124,58,237,0.55)'}`,
            color: uploadingVisionVideo ? 'rgba(168,85,247,0.5)' : 'var(--violet)',
            background: uploadingVisionVideo
              ? 'rgba(124,58,237,0.06)'
              : 'linear-gradient(135deg, rgba(124,58,237,0.15) 0%, rgba(100,40,200,0.1) 100%)',
            transition: 'all 0.2s', whiteSpace: 'nowrap' as const,
            boxShadow: uploadingVisionVideo ? 'none' : '0 0 20px rgba(124,58,237,0.2), inset 0 1px 0 rgba(168,85,247,0.1)',
            letterSpacing: '0.02em',
          }}
          title="Upload video for AI object detection and motion analysis (mp4, avi, mov, mkv)"
        >
          <span style={{ fontSize: '16px' }}>⬡</span>
          {uploadingVisionVideo ? 'Analyzing…' : 'Upload Video'}
        </button>

        {/* Camera / CCTV */}
        <button
          type="button"
          onClick={cameraRunning ? stopCamera : startCamera}
          disabled={cameraLoading}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '8px',
            padding: '10px 18px', borderRadius: '10px',
            fontSize: '13px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 500,
            border: `1px solid ${cameraRunning ? 'rgba(244,63,94,0.45)' : 'rgba(0,212,255,0.35)'}`,
            color: cameraRunning ? 'var(--rose)' : 'var(--cyan)',
            background: cameraRunning ? 'rgba(244,63,94,0.08)' : 'rgba(0,212,255,0.06)',
            cursor: cameraLoading ? 'default' as const : 'pointer' as const,
            transition: 'all 0.2s', whiteSpace: 'nowrap' as const,
            boxShadow: cameraRunning ? '0 0 14px rgba(244,63,94,0.15)' : '0 0 14px rgba(0,212,255,0.08)',
          }}
          title={cameraRunning ? 'Stop live camera capture' : 'Start live camera — requires opencv-python-headless'}
        >
          <span style={{ fontSize: '12px' }}>{cameraRunning ? '⏹' : '◉'}</span>
          {cameraLoading ? '…' : cameraRunning ? 'Stop Camera' : 'Camera / CCTV'}
        </button>

        <div style={{ width: '1px', height: '28px', background: 'rgba(255,255,255,0.06)', flexShrink: 0, margin: '0 2px' }} />

        {/* Start Screen Watch placeholder */}
        <button
          type="button"
          disabled
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '8px',
            padding: '10px 18px', borderRadius: '10px', cursor: 'default' as const,
            fontSize: '13px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 500,
            border: '1px solid rgba(0,212,255,0.12)', color: 'rgba(0,212,255,0.3)',
            background: 'rgba(0,212,255,0.03)', whiteSpace: 'nowrap' as const,
          }}
          title="Run screen_watcher.py in a terminal to start screen capture"
        >
          <span style={{ fontSize: '12px' }}>●</span>
          Start Screen Watch
        </button>

        <div style={{ flex: 1 }} />

        {/* Refresh */}
        <button
          onClick={handleRefresh}
          disabled={loading || loadingSessions}
          className="btn-outline"
          style={{ padding: '10px 18px', fontSize: '13px' }}
        >
          {loading || loadingSessions ? '…' : '↺ Refresh'}
        </button>
      </div>

      {/* Upload errors */}
      {(pdfUploadError || audioUploadError || visionVideoError) && (
        <div style={{ padding: '6px 28px', display: 'flex', gap: '16px', flexWrap: 'wrap' as const }}>
          {pdfUploadError   && <span className="error-text">PDF: {pdfUploadError}</span>}
          {audioUploadError && <span className="error-text">Audio: {audioUploadError}</span>}
          {visionVideoError && <span className="error-text">Video: {visionVideoError}</span>}
        </div>
      )}

      {/* ── Tab bar ── */}
      <div style={{ padding: '12px 28px 0', display: 'flex', gap: '6px', flexWrap: 'wrap' as const }}>
        {([
          { id: 'timeline', label: '◈ Timeline' },
          { id: 'sessions', label: '◫ Sessions' },
          { id: 'videos',   label: '⬡ Vision / CCTV' },
          { id: 'replay',   label: '◈ Replay' },
          { id: 'soul',     label: '◉ Soul' },
          { id: 'graph',    label: '◎ Graph' },
          { id: 'profile',  label: '◉ Profile' },
          { id: 'trends',   label: '◷ Trends' },
          { id: 'agent',    label: '⬡ Agent' },
        ] as const).map(({ id: tab, label }) => (
          <button
            key={tab}
            onClick={() => switchTab(tab)}
            className={`tab-btn ${activeTab === tab ? 'active' : 'inactive'}`}
            style={{ padding: '8px 18px', fontSize: '12px' }}
          >
            {label}
            {tab === 'sessions' && sessionsLoaded && sessions.length > 0 && (
              <span style={{ marginLeft: '5px', opacity: 0.45, fontSize: '9px' }}>{sessions.length}</span>
            )}
            {tab === 'videos' && videosLoaded && videos.length > 0 && (
              <span style={{ marginLeft: '5px', opacity: 0.45, fontSize: '9px' }}>{videos.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── Chat panel ── */}
      <ChatPanel />

      {/* ── Suggestions panel ── */}
      <SuggestionsPanel
        suggestions={suggestions}
        loading={loadingSuggestions}
        dismissed={dismissedIds}
        onDismiss={dismissSuggestion}
        onRefresh={fetchSuggestions}
      />

      {/* ── Status bar ── */}
      <div style={{ padding: '4px 28px 10px', display: 'flex', alignItems: 'center', gap: '10px' }}>
        {error ? (
          <>
            <span className="error-text">ERROR: {error}</span>
            <button onClick={handleRefresh} className="btn-ghost" style={{ fontSize: '10px', padding: '2px 10px' }}>↺ Retry</button>
          </>
        ) : (
          <span className="label-xs">
            {activeTab === 'graph'
              ? (loadingGraph ? 'BUILDING GRAPH…' : graphData ? `${graphData.stats.node_count} nodes · ${graphData.stats.edge_count} edges` : 'Graph ready')
              : activeTab === 'profile'
              ? (loadingProfile ? 'COMPUTING PROFILE…' : profileData ? `${profileData.total_memories} memories · ${profileData.memory_span_days} days · ${Math.round((profileData.confidence ?? 0) * 100)}% confidence` : 'Profile ready')
              : activeTab === 'videos'
              ? (loadingVideos ? 'LOADING VIDEOS…' : activeVideo ? `${activeVideo.event_count} events · ${activeVideo.original_name}` : `${videos.length} video${videos.length !== 1 ? 's' : ''} stored`)
              : activeTab === 'sessions'
              ? (loadingSessions ? 'DETECTING SESSIONS…' : activeSession ? `${activeSession.memory_count} memories · ${activeSession.duration_str}` : `${sessions.length} session${sessions.length !== 1 ? 's' : ''} detected`)
              : activeTab === 'agent'
              ? (screenWatchRunning ? 'SCREEN WATCH ACTIVE' : `${agentActions.length} actions · ${workflowPeriods.length} workflow periods`)
              : activeTab === 'replay'
              ? (loadingReplay ? 'REPLAYING…' : replayResult ? `${replayResult.total_count} events · ${replayResult.key_moments.length} key moments` : 'Replay Studio ready')
              : activeTab === 'soul'
              ? (loadingSoul ? 'COMPUTING SOUL…' : soulPatterns.length > 0 ? `${soulPatterns.length} patterns · ${projectMemory?.top_projects.length ?? 0} projects` : 'Digital Soul ready')
              : (loading ? 'FETCHING…' : isSearch ? `${count} result${count !== 1 ? 's' : ''} for "${query}"` : `${count} memor${count !== 1 ? 'ies' : 'y'} stored`)}
          </span>
        )}
      </div>

      {/* ── Main content ── */}
      <main style={{ padding: '0 28px 48px' }}>

        {/* Timeline tab */}
        {activeTab === 'timeline' && (
          error && !loading ? (
            <div className="empty-state">
              <div className="empty-icon" style={{ color: 'var(--rose)' }}>⚠</div>
              <div className="empty-title" style={{ color: 'var(--rose)' }}>BACKEND UNREACHABLE</div>
              <div className="empty-sub">Make sure the API is running on port 8010</div>
              <button onClick={fetchTimeline} className="btn-outline" style={{ marginTop: '20px' }}>↺ Retry</button>
            </div>
          ) : loading ? (
            <div className="empty-state">
              <span className="spin-ring">⟳</span>
              <div className="empty-title" style={{ marginTop: '16px' }}>LOADING MEMORIES…</div>
            </div>
          ) : count === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">◈</div>
              <div className="empty-title">{isSearch ? 'NO RESULTS FOUND' : 'NO MEMORIES STORED YET'}</div>
              {isSearch && (
                <div className="empty-sub">
                  Try a different term or{' '}
                  <button onClick={fetchTimeline} style={{ background: 'none', border: 'none', color: 'var(--blue)', cursor: 'pointer', fontSize: '12px', padding: 0 }}>
                    view all
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))', gap: '14px' }}>
              {isSearch
                ? searchResults!.map(r => (
                    <MemoryCard
                      key={r.item.id}
                      item={r.item}
                      result={r}
                      onAskPdf={r.item.type === 'pdf' ? () => setPdfChatTarget(r.item) : undefined}
                    />
                  ))
                : items.map(item => (
                    <MemoryCard
                      key={item.id}
                      item={item}
                      onAskPdf={item.type === 'pdf' ? () => setPdfChatTarget(item) : undefined}
                    />
                  ))
              }
            </div>
          )
        )}

        {/* Graph tab */}
        {activeTab === 'graph' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {loadingGraph ? (
              <div className="empty-state">
                <span className="spin-ring">⟳</span>
                <div className="empty-title" style={{ marginTop: '16px' }}>BUILDING MEMORY GRAPH…</div>
              </div>
            ) : !graphData ? (
              <div className="empty-state">
                <div className="empty-icon">◎</div>
                <button onClick={fetchGraph} className="btn-outline">Load Graph</button>
              </div>
            ) : (
              <div>
                {/* Stats row */}
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' as const, marginBottom: '24px' }}>
                  {[
                    { label: 'Nodes', value: graphData.stats.node_count },
                    { label: 'Edges', value: graphData.stats.edge_count },
                    ...Object.entries(graphData.stats.relationships ?? {}).map(([k, v]) => ({ label: k.replace('_', ' '), value: v })),
                  ].map(({ label, value }) => (
                    <div key={label} className="stat-card reveal">
                      <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--blue)', fontFamily: 'var(--font-geist-mono, monospace)' }}>{value}</div>
                      <div className="label-xs" style={{ marginTop: '4px' }}>{label}</div>
                    </div>
                  ))}
                </div>

                {/* Edge list */}
                <div className="section-title" style={{ marginBottom: '12px' }}>
                  Memory Connections — most recent {graphData.stats.node_count} memories
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', maxHeight: '600px', overflowY: 'auto' }} className="scroll-thin">
                  {graphData.edges.slice(0, 60).map((e, i) => {
                    const fromNode = graphData.nodes.find(n => n.id === e.from)
                    const toNode   = graphData.nodes.find(n => n.id === e.to)
                    const relColor: Record<string, string> = {
                      same_session:     'var(--blue)',
                      near_time:        'var(--amber)',
                      same_app:         'var(--emerald)',
                      same_topic:       'var(--violet)',
                      workflow_related: 'var(--orange)',
                      semantic_match:   'var(--magenta)',
                    }
                    const color = relColor[e.relationship] ?? 'var(--text-3)'
                    return (
                      <div key={i} className="edge-card" style={{ borderLeftColor: color }}>
                        <div style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const, color: 'var(--text-2)', fontSize: '11px' }}>
                          {fromNode?.title ?? e.from.slice(0, 12)}
                        </div>
                        <span className="chip" style={{ color, borderColor: `${color}55`, background: `${color}10`, fontSize: '9px', flexShrink: 0 }}>
                          {e.relationship.replace('_', ' ')}
                        </span>
                        <div style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const, color: 'var(--text-2)', textAlign: 'right' as const, fontSize: '11px' }}>
                          {toNode?.title ?? e.to.slice(0, 12)}
                        </div>
                        <span className="label-xs" style={{ flexShrink: 0 }}>{Math.round(e.confidence * 100)}%</span>
                      </div>
                    )
                  })}
                  {graphData.edges.length === 0 && (
                    <div className="empty-state">
                      <div className="empty-icon">◎</div>
                      <div className="empty-title">NO CONNECTIONS YET</div>
                      <div className="empty-sub">Capture more memories to build the graph</div>
                    </div>
                  )}
                  {graphData.edges.length > 60 && (
                    <div style={{ padding: '8px 0', textAlign: 'center' as const }} className="label-xs">
                      Showing 60 of {graphData.edges.length} edges
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Trends tab — Phase 21 */}
        {activeTab === 'trends' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {loadingTrends ? (
              <div className="empty-state">
                <span className="spin-ring">⟳</span>
                <div className="empty-title" style={{ marginTop: '16px' }}>ANALYSING TRENDS…</div>
              </div>
            ) : !trendsData ? (
              <div className="empty-state">
                <div className="empty-icon">◷</div>
                <button onClick={fetchTrends} className="btn-outline">Load Timeline Intelligence</button>
              </div>
            ) : (
              <>
                {/* Narrative */}
                {trendsData.narrative && (
                  <div style={{ background: 'rgba(0,180,255,0.04)', border: '1px solid rgba(0,180,255,0.14)', borderRadius: '10px', padding: '14px 18px' }}>
                    <div style={{ color: 'var(--cyan)', fontSize: '10px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '8px' }}>◷ TIMELINE ANALYSIS</div>
                    <p style={{ color: 'var(--text-2)', fontSize: '13px', lineHeight: 1.7, margin: 0 }}>{trendsData.narrative}</p>
                  </div>
                )}

                {/* Week summary cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
                  {([
                    { label: 'THIS WEEK', value: trendsData.this_week_count, sub: trendsData.wow_change },
                    { label: 'LAST WEEK', value: trendsData.last_week_count, sub: 'prev 7 days' },
                    { label: 'ALL TIME',  value: trendsData.total_memories,  sub: 'total memories' },
                  ] as const).map(({ label, value, sub }) => (
                    <div key={label} className="stat-card" style={{ textAlign: 'center' as const }}>
                      <div style={{ color: 'var(--text-4)', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '6px' }}>{label}</div>
                      <div style={{ color: 'var(--text-1)', fontSize: '26px', fontWeight: 700, fontFamily: 'var(--font-geist-mono, monospace)' }}>{value}</div>
                      <div style={{ color: 'var(--text-4)', fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)', marginTop: '4px' }}>{sub}</div>
                    </div>
                  ))}
                </div>

                {/* 14-day activity bar chart */}
                {trendsData.daily.length > 0 && (() => {
                  const maxCnt = Math.max(...trendsData.daily.map(d => d.count), 1)
                  return (
                    <div className="stat-card">
                      <div className="section-title" style={{ marginBottom: '14px' }}>14-Day Activity</div>
                      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '3px', height: '72px' }}>
                        {trendsData.daily.map((day, i) => (
                          <div key={i} title={`${day.date}: ${day.count}`} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%' }}>
                            <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', width: '100%' }}>
                              <div style={{
                                width: '100%',
                                height: day.count > 0 ? `${Math.max(day.count / maxCnt * 100, 10)}%` : '2px',
                                background: day.count > 0 ? 'rgba(0,180,255,0.55)' : 'rgba(255,255,255,0.04)',
                                borderRadius: '2px 2px 0 0',
                                boxShadow: day.count > 0 ? '0 0 6px rgba(0,180,255,0.25)' : 'none',
                              }} />
                            </div>
                            {i % 2 === 0 && (
                              <div style={{ color: 'var(--text-4)', fontSize: '7px', fontFamily: 'var(--font-geist-mono, monospace)', marginTop: '3px' }}>{day.label}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })()}

                {/* Trending domains */}
                {trendsData.trending_domains.length > 0 && (
                  <div className="stat-card">
                    <div className="section-title" style={{ marginBottom: '12px' }}>Domain Trends (this week vs last)</div>
                    {trendsData.trending_domains.map(td => (
                      <div key={td.domain} style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                        <span style={{ fontSize: '13px', color: td.trend === 'rising' ? '#22c55e' : td.trend === 'falling' ? '#ef4444' : '#eab308', flexShrink: 0 }}>
                          {td.trend === 'rising' ? '↑' : td.trend === 'falling' ? '↓' : '→'}
                        </span>
                        <span style={{ flex: 1, fontSize: '12px', color: td.color }}>{td.domain}</span>
                        <span style={{ fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)', color: td.trend === 'rising' ? '#22c55e' : td.trend === 'falling' ? '#ef4444' : 'var(--text-4)' }}>
                          {td.delta}
                        </span>
                        <span style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', minWidth: '22px', textAlign: 'right' as const }}>
                          {td.this_week}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Memory clusters from daily domain data */}
                {trendsData.daily.some(d => Object.keys(d.domains).length > 0) && (() => {
                  const totals: Record<string, number> = {}
                  trendsData.daily.forEach(day => {
                    Object.entries(day.domains).forEach(([dom, cnt]) => {
                      totals[dom] = (totals[dom] || 0) + (cnt as number)
                    })
                  })
                  const total = Object.values(totals).reduce((a, b) => a + b, 0) || 1
                  const sorted = Object.entries(totals).sort(([, a], [, b]) => b - a)
                  return (
                    <div className="stat-card">
                      <div className="section-title" style={{ marginBottom: '12px' }}>Memory Clusters (14-day window)</div>
                      {sorted.map(([domain, count]) => {
                        const pct = Math.round((count as number) / total * 100)
                        return (
                          <div key={domain} style={{ marginBottom: '8px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                              <span style={{ fontSize: '11px', color: 'var(--text-2)' }}>{domain}</span>
                              <span style={{ fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)', color: 'var(--text-4)' }}>{count} · {pct}%</span>
                            </div>
                            <div style={{ height: '3px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px' }}>
                              <div style={{ height: '100%', width: `${pct}%`, background: '#00b4ff', opacity: 0.55, borderRadius: '2px' }} />
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )
                })()}
              </>
            )}
          </div>
        )}

        {/* Profile tab */}
        {activeTab === 'profile' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

            {/* ── Cognitive Profile (Phase 21) ── */}
            {loadingCog ? (
              <div style={{ padding: '14px 18px', display: 'flex', gap: '10px', alignItems: 'center', background: 'rgba(139,92,246,0.04)', border: '1px solid rgba(139,92,246,0.14)', borderRadius: '10px' }}>
                <span style={{ color: 'var(--violet)', fontSize: '16px', animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
                <span style={{ color: 'var(--text-3)', fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)' }}>SYNTHESISING COGNITIVE PROFILE…</span>
              </div>
            ) : cogProfile ? (
              <>
                {/* Gemini summary */}
                <div style={{ background: 'rgba(139,92,246,0.04)', border: '1px solid rgba(139,92,246,0.14)', borderRadius: '10px', padding: '16px 18px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px', flexWrap: 'wrap' as const }}>
                    <span style={{ color: 'var(--violet)', fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em' }}>◈ COGNITIVE PROFILE</span>
                    {cogProfile.gemini_powered && (
                      <span style={{ fontSize: '9px', padding: '1px 6px', borderRadius: '3px', background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.3)', color: 'var(--violet)', fontFamily: 'var(--font-geist-mono, monospace)' }}>⬡ Gemini</span>
                    )}
                    <span style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', marginLeft: 'auto' }}>
                      {Math.round(cogProfile.confidence * 100)}% confidence · {cogProfile.memory_count} memories
                    </span>
                  </div>
                  <p style={{ color: 'var(--text-2)', fontSize: '13px', lineHeight: 1.75, margin: 0 }}>{cogProfile.summary}</p>
                </div>

                {/* Domain activity bars + active projects */}
                {cogProfile.domain_scores.length > 0 && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <div className="stat-card">
                      <div className="section-title" style={{ marginBottom: '12px' }}>Primary Activities</div>
                      {cogProfile.domain_scores.slice(0, 5).map(ds => (
                        <div key={ds.domain} style={{ marginBottom: '9px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                            <span style={{ fontSize: '11px', color: ds.color }}>{ds.domain}</span>
                            <span style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)' }}>{ds.percentage}%</span>
                          </div>
                          <div style={{ height: '3px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px' }}>
                            <div style={{ height: '100%', width: `${ds.percentage}%`, background: ds.color, borderRadius: '2px', boxShadow: `0 0 5px ${ds.color}44` }} />
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="stat-card">
                      <div className="section-title" style={{ marginBottom: '12px' }}>Active Projects</div>
                      {cogProfile.active_projects.map(p => (
                        <div key={p} style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '7px' }}>
                          <span style={{ color: 'var(--violet)', fontSize: '10px' }}>◈</span>
                          <span style={{ fontSize: '12px', color: 'var(--text-1)' }}>{p}</span>
                        </div>
                      ))}
                      {cogProfile.keywords.length > 0 && (
                        <div style={{ marginTop: '10px', display: 'flex', gap: '5px', flexWrap: 'wrap' as const }}>
                          {cogProfile.keywords.slice(0, 6).map(kw => (
                            <span key={kw} className="chip chip-purple" style={{ fontSize: '9px' }}>{kw}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Proactive insights */}
                {cogProfile.insights.length > 0 && (
                  <div>
                    <div className="section-title" style={{ marginBottom: '10px' }}>Proactive Insights</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {cogProfile.insights.map((ins, i) => (
                        <div key={i} style={{
                          padding: '10px 14px',
                          background: `${ins.color}0a`,
                          border: `1px solid ${ins.color}22`,
                          borderRadius: '8px',
                          display: 'flex',
                          gap: '12px',
                          alignItems: 'flex-start',
                        }}>
                          <span style={{ color: ins.color, fontSize: '16px', flexShrink: 0, marginTop: '1px' }}>◉</span>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ color: 'var(--text-1)', fontSize: '12px', fontWeight: 600, marginBottom: '2px' }}>{ins.title}</div>
                            <div style={{ color: 'var(--text-3)', fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)', lineHeight: 1.5 }}>{ins.text}</div>
                          </div>
                          {ins.value && (
                            <span style={{ color: ins.color, fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)', flexShrink: 0, fontWeight: 700 }}>{ins.value}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <button onClick={fetchCogProfile} className="btn-outline" style={{ alignSelf: 'flex-start' }}>Generate Cognitive Profile</button>
            )}

            {/* divider */}
            <div style={{ height: '1px', background: 'rgba(255,255,255,0.05)' }} />

            {/* ── Existing behavioural profile below ── */}
            {loadingProfile ? (
              <div className="empty-state">
                <span className="spin-ring">⟳</span>
                <div className="empty-title" style={{ marginTop: '16px' }}>COMPUTING PROFILE…</div>
              </div>
            ) : !profileData ? (
              <div className="empty-state">
                <div className="empty-icon">◉</div>
                <button onClick={fetchProfile} className="btn-outline">Load Profile</button>
              </div>
            ) : (
              <>
                {/* Privacy note */}
                <div style={{ background: 'rgba(16,217,132,0.04)', border: '1px solid rgba(16,217,132,0.12)', borderRadius: '8px', padding: '10px 16px' }} className="label-xs" >
                  <span style={{ color: 'var(--emerald)', marginRight: '8px' }}>◉</span>
                  <span style={{ color: 'var(--text-3)', letterSpacing: '0.04em', textTransform: 'none', fontSize: '11px' }}>{profileData.privacy_note}</span>
                </div>

                {/* Insights */}
                <div>
                  <div className="section-title" style={{ marginBottom: '10px' }}>Insights</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    {profileData.insights.map((ins, i) => (
                      <div key={i} className="glass-card reveal" style={{ padding: '8px 14px', fontSize: '12px', color: 'var(--text-2)', animation: `fade-up 0.3s ease ${i * 0.05}s both` }}>
                        <span style={{ color: 'var(--blue)', marginRight: '8px' }}>·</span>{ins}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Workflow patterns */}
                {profileData.workflow_patterns && profileData.workflow_patterns.length > 0 && (
                  <div>
                    <div className="section-title" style={{ marginBottom: '10px' }}>Workflow Patterns</div>
                    {profileData.workflow_patterns.map((p, i) => (
                      <div key={i} className="edge-card reveal" style={{ borderLeftColor: 'var(--orange)', marginBottom: '5px', animation: `fade-up 0.3s ease ${i * 0.05}s both` }}>
                        <span style={{ color: 'var(--text-2)', fontSize: '12px' }}>{p}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '14px' }}>
                  {/* Top apps */}
                  {profileData.top_apps.length > 0 && (
                    <div className="stat-card">
                      <div className="section-title" style={{ marginBottom: '12px' }}>Top Apps</div>
                      {profileData.top_apps.map(a => (
                        <div key={a.app} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                          <span style={{ fontSize: '12px', color: 'var(--text-1)' }}>{a.app}</span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <div style={{ width: `${Math.max(a.pct * 1.2, 8)}px`, height: '3px', background: 'rgba(0,212,255,0.35)', borderRadius: '2px', boxShadow: '0 0 6px rgba(0,212,255,0.3)' }} />
                            <span className="label-xs">{a.pct}%</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Top keywords */}
                  {profileData.top_keywords.length > 0 && (
                    <div className="stat-card">
                      <div className="section-title" style={{ marginBottom: '12px' }}>Recurring Topics</div>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' as const }}>
                        {profileData.top_keywords.map(kw => (
                          <span key={kw} className="chip chip-purple">{kw}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Type distribution */}
                  {Object.keys(profileData.type_distribution).length > 0 && (
                    <div className="stat-card">
                      <div className="section-title" style={{ marginBottom: '12px' }}>Memory Types</div>
                      {Object.entries(profileData.type_distribution).map(([t, c]) => (
                        <div key={t} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '12px' }}>
                          <TypeBadge type={t} />
                          <span className="label-xs">{String(c)}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Productivity notes */}
                  {profileData.productivity_notes.length > 0 && (
                    <div className="stat-card">
                      <div className="section-title" style={{ marginBottom: '12px' }}>Productivity</div>
                      {profileData.productivity_notes.map((n, i) => (
                        <div key={i} style={{ fontSize: '11px', color: 'var(--text-3)', marginBottom: '5px' }}>
                          <span style={{ color: 'var(--emerald)', marginRight: '6px' }}>·</span>{n}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Peak period + confidence */}
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' as const, alignItems: 'center' }}>
                  <span className="chip chip-blue">PEAK: {profileData.peak_period}</span>
                  <span className="chip chip-ghost">SPAN: {profileData.memory_span_days} days</span>
                  <span className="chip chip-emerald">CONFIDENCE: {Math.round((profileData.confidence ?? 0) * 100)}%</span>
                </div>

                {/* Desktop Ready note — Phase 19 */}
                <div style={{ background: 'rgba(0,212,255,0.04)', border: '1px solid rgba(0,212,255,0.10)', borderRadius: '8px', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ color: 'var(--cyan)', fontSize: '13px' }}>◉</span>
                  <div>
                    <span style={{ color: 'var(--cyan)', fontSize: '11px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' as const }}>Desktop Ready</span>
                    <span style={{ color: 'var(--text-3)', fontSize: '11px', marginLeft: '10px' }}>Native desktop shell planned (Tauri/Electron). Current version runs as a local web OS — all data stays on your machine.</span>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* Vision / CCTV tab */}
        {activeTab === 'videos' && (
          activeVideo ? (
            /* ── Video detail view ── */
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Back + header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <button
                  onClick={() => { setActiveVideo(null); setVideoEvents([]) }}
                  className="btn-ghost"
                  style={{ fontSize: '12px', padding: '8px 16px' }}
                >
                  ← Back
                </button>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-1)' }}>{activeVideo.original_name}</div>
                  <div className="label-xs" style={{ marginTop: '5px' }}>
                    {activeVideo.resolution && <span>{activeVideo.resolution} · </span>}
                    {activeVideo.duration_secs != null && <span>{Math.floor(activeVideo.duration_secs / 60)}m {Math.round(activeVideo.duration_secs % 60)}s · </span>}
                    {activeVideo.event_count} events
                    {activeVideo.labels.length > 0 && <span> · {activeVideo.labels.join(', ')}</span>}
                  </div>
                </div>
                <VideoStatusBadge status={activeVideo.status} progress={activeVideo.progress} />
              </div>

              {/* Summary */}
              {activeVideo.summary && (
                <div className="glass-card" style={{ padding: '14px 18px', fontSize: '13px', color: 'var(--text-2)', fontFamily: 'var(--font-geist-mono, monospace)', lineHeight: 1.7, borderLeft: '3px solid rgba(124,58,237,0.4)' }}>
                  {activeVideo.summary}
                </div>
              )}

              {/* Analyzing banner */}
              {activeVideo.status === 'analyzing' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 16px', background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: '10px' }}>
                  <span className="spin-ring" style={{ fontSize: '18px', color: 'var(--amber)' }}>⟳</span>
                  <div>
                    <div style={{ fontSize: '13px', color: 'var(--amber)', fontWeight: 600 }}>Analyzing video…</div>
                    <div className="label-xs" style={{ marginTop: '2px' }}>YOLO object detection · Motion analysis · {activeVideo.progress}% complete</div>
                  </div>
                </div>
              )}

              {/* Event type filters */}
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' as const }}>
                {[null, 'person_appeared', 'motion_detected', 'vehicle_appeared', 'crowd_detected', 'bag_detected'].map(f => (
                  <button
                    key={f ?? 'all'}
                    onClick={() => setVideoEventFilter(f)}
                    className={`tab-btn ${videoEventFilter === f ? 'active' : 'inactive'}`}
                    style={{ padding: '6px 14px', fontSize: '11px' }}
                  >
                    {f === null ? 'All Events' : EVENT_ICONS[f] + ' ' + f.replace('_', ' ')}
                  </button>
                ))}
              </div>

              {/* Events list */}
              {loadingVideoEvents ? (
                <div style={{ textAlign: 'center', padding: '40px 0' }}>
                  <span className="spin-ring" style={{ fontSize: '28px' }}>⟳</span>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
                  {videoEvents
                    .filter(e => videoEventFilter === null || e.type === videoEventFilter)
                    .map(ev => <EventCard key={ev.id} event={ev} />)
                  }
                  {videoEvents.filter(e => videoEventFilter === null || e.type === videoEventFilter).length === 0 && (
                    <div className="empty-state" style={{ padding: '48px 0' }}>
                      <div className="empty-icon" style={{ fontSize: '36px' }}>◌</div>
                      <div className="empty-title">NO EVENTS{videoEventFilter ? ` — ${videoEventFilter.replace('_', ' ').toUpperCase()}` : ''}</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            /* ── Vision / CCTV main view ── */
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

              {/* Upload hero area */}
              <div style={{
                background: 'linear-gradient(135deg, rgba(124,58,237,0.1) 0%, rgba(0,212,255,0.05) 100%)',
                border: '1px solid rgba(124,58,237,0.25)',
                borderRadius: '16px',
                padding: '28px 32px',
                display: 'flex',
                gap: '24px',
                alignItems: 'center',
                flexWrap: 'wrap' as const,
              }}>
                <div style={{ flex: 1, minWidth: '220px' }}>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-1)', marginBottom: '6px', letterSpacing: '0.02em' }}>
                    <span style={{ color: 'var(--violet)' }}>⬡</span> Vision Intelligence
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-3)', lineHeight: 1.6 }}>
                    Upload video for motion detection and object analysis.<br />
                    YOLO nano detects persons, vehicles, bags and more.
                  </div>
                  <div className="label-xs" style={{ marginTop: '10px' }}>
                    mp4 · avi · mov · mkv · max 2 GB · CPU-only · local processing
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' as const, alignItems: 'center' }}>
                  <button
                    type="button"
                    onClick={() => visionVideoInputRef.current?.click()}
                    disabled={uploadingVisionVideo}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: '10px',
                      padding: '14px 28px', borderRadius: '12px',
                      fontSize: '15px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 700,
                      border: `1px solid ${uploadingVisionVideo ? 'rgba(124,58,237,0.3)' : 'rgba(124,58,237,0.6)'}`,
                      color: uploadingVisionVideo ? 'rgba(168,85,247,0.45)' : 'var(--violet)',
                      background: uploadingVisionVideo
                        ? 'rgba(124,58,237,0.05)'
                        : 'linear-gradient(135deg, rgba(124,58,237,0.2) 0%, rgba(100,40,200,0.12) 100%)',
                      cursor: uploadingVisionVideo ? 'default' as const : 'pointer' as const,
                      transition: 'all 0.2s',
                      boxShadow: uploadingVisionVideo ? 'none' : '0 0 28px rgba(124,58,237,0.25), inset 0 1px 0 rgba(168,85,247,0.15)',
                      letterSpacing: '0.02em',
                    }}
                  >
                    <span style={{ fontSize: '20px' }}>⬡</span>
                    {uploadingVisionVideo ? 'Analyzing…' : 'Upload Video'}
                  </button>
                  {uploadingVisionVideo && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--amber)', fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                      <span className="spin-ring" style={{ fontSize: '16px', color: 'var(--amber)' }}>⟳</span>
                      Processing…
                    </div>
                  )}
                </div>
              </div>

              {/* Live Camera / CCTV panel — two-column console */}
              <div style={{
                background: 'rgba(6,6,18,0.85)',
                border: `1px solid ${(cameraRunning || previewActive) ? 'rgba(0,212,255,0.28)' : 'rgba(0,212,255,0.12)'}`,
                borderRadius: '12px',
                overflow: 'hidden',
                transition: 'border-color 0.3s',
              }}>

                {/* Panel header bar */}
                <div style={{ padding: '12px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ color: (cameraRunning || previewActive) ? 'var(--cyan)' : 'var(--text-4)', fontSize: '10px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.12em' }}>
                    ◉ LIVE CCTV CONSOLE
                  </span>
                  <div style={{ flex: 1 }} />
                  {previewActive && (
                    <span className="chip chip-rose" style={{ fontSize: '9px' }}>● PREVIEW</span>
                  )}
                  {cameraRunning && (
                    <span className="chip chip-emerald" style={{ fontSize: '9px' }}>● AI ACTIVE</span>
                  )}
                  {cameraStatus?.detection_mode && cameraStatus.detection_mode !== 'unknown' && (
                    <span className={`chip ${cameraStatus.detection_mode === 'yolo' ? 'chip-cyan' : cameraStatus.detection_mode === 'motion_only' ? 'chip-amber' : 'chip-ghost'}`} style={{ fontSize: '9px' }}>
                      {cameraStatus.detection_mode === 'yolo' ? 'YOLO' : cameraStatus.detection_mode === 'motion_only' ? 'MOTION' : 'UNAVAIL'}
                    </span>
                  )}
                </div>

                {/* Two-column body */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>

                  {/* ── LEFT: Browser Camera Preview ── */}
                  <div style={{ padding: '18px 20px', borderRight: '1px solid rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column' as const, gap: '12px' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em' }}>
                      BROWSER PREVIEW — frontend only
                    </div>

                    {/* Video viewport */}
                    <div style={{
                      position: 'relative' as const,
                      width: '100%',
                      aspectRatio: '16/9',
                      background: '#020208',
                      border: `1px solid ${previewActive ? 'rgba(0,212,255,0.3)' : 'rgba(255,255,255,0.06)'}`,
                      borderRadius: '8px',
                      overflow: 'hidden',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      {/* Video element always in DOM so ref assignment works before display flip */}
                      <video
                        ref={previewVideoRef}
                        autoPlay
                        playsInline
                        muted
                        style={{
                          width: '100%',
                          height: '100%',
                          objectFit: 'cover',
                          display: previewActive ? 'block' : 'none',
                        }}
                      />
                      {/* No-signal placeholder */}
                      {!previewActive && (
                        <div style={{ textAlign: 'center' as const, color: 'var(--text-4)', userSelect: 'none' as const }}>
                          <div style={{ fontSize: '40px', opacity: 0.18, marginBottom: '8px', fontFamily: 'var(--font-geist-mono, monospace)' }}>◉</div>
                          <div style={{ fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.18em', opacity: 0.3 }}>NO SIGNAL</div>
                        </div>
                      )}
                      {/* LIVE badge overlay */}
                      {previewActive && (
                        <div style={{ position: 'absolute' as const, top: '8px', left: '8px', display: 'flex', alignItems: 'center', gap: '5px', background: 'rgba(0,0,0,0.65)', padding: '3px 8px', borderRadius: '4px' }}>
                          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--rose)', display: 'inline-block', boxShadow: '0 0 6px var(--rose)' }} />
                          <span style={{ fontSize: '9px', color: '#fff', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em' }}>LIVE</span>
                        </div>
                      )}
                    </div>

                    {/* Preview error */}
                    {previewError && (
                      <div style={{ fontSize: '11px', color: 'var(--rose)', fontFamily: 'var(--font-geist-mono, monospace)', background: 'rgba(244,63,94,0.06)', border: '1px solid rgba(244,63,94,0.2)', borderRadius: '7px', padding: '9px 12px', lineHeight: 1.5 }}>
                        ⚠ {previewError}
                      </div>
                    )}

                    {/* Preview controls */}
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        type="button"
                        onClick={startPreview}
                        disabled={previewActive}
                        style={{
                          flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '7px',
                          padding: '9px 12px', borderRadius: '8px',
                          fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 500,
                          border: `1px solid ${previewActive ? 'rgba(0,212,255,0.1)' : 'rgba(0,212,255,0.4)'}`,
                          color: previewActive ? 'rgba(0,212,255,0.3)' : 'var(--cyan)',
                          background: previewActive ? 'rgba(0,212,255,0.02)' : 'rgba(0,212,255,0.08)',
                          cursor: previewActive ? 'default' as const : 'pointer' as const,
                          transition: 'all 0.2s',
                        }}
                      >
                        ▶ Start Preview
                      </button>
                      <button
                        type="button"
                        onClick={stopPreview}
                        disabled={!previewActive}
                        style={{
                          flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '7px',
                          padding: '9px 12px', borderRadius: '8px',
                          fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 500,
                          border: `1px solid ${!previewActive ? 'rgba(244,63,94,0.1)' : 'rgba(244,63,94,0.4)'}`,
                          color: !previewActive ? 'rgba(244,63,94,0.3)' : 'var(--rose)',
                          background: !previewActive ? 'transparent' : 'rgba(244,63,94,0.07)',
                          cursor: !previewActive ? 'default' as const : 'pointer' as const,
                          transition: 'all 0.2s',
                        }}
                      >
                        ⏹ Stop Preview
                      </button>
                    </div>
                    <div className="label-xs" style={{ opacity: 0.45 }}>
                      Browser preview only · no video is recorded or sent anywhere
                    </div>
                  </div>

                  {/* ── RIGHT: AI Detection Status ── */}
                  <div style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column' as const, gap: '12px' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em' }}>
                      AI DETECTION — backend OpenCV
                    </div>

                    {/* Status grid */}
                    <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '7px' }}>
                      {[
                        { label: 'Status',   value: cameraRunning ? 'RUNNING' : 'STOPPED',
                          color: cameraRunning ? 'var(--emerald)' : 'var(--text-4)' },
                        { label: 'Engine',   value: cameraStatus?.detection_mode === 'yolo' ? 'YOLO nano' : cameraStatus?.detection_mode === 'motion_only' ? 'Motion only' : cameraStatus?.detection_mode === 'unavailable' ? '— not installed' : '—',
                          color: 'var(--text-3)' },
                        { label: 'Camera',   value: cameraStatus?.camera_available === true ? 'Detected' : cameraStatus?.camera_available === false ? 'Unavailable' : '—',
                          color: cameraStatus?.camera_available === true ? 'var(--emerald)' : cameraStatus?.camera_available === false ? 'var(--rose)' : 'var(--text-4)' },
                        { label: 'Events',   value: String(cameraStatus?.event_count ?? 0),
                          color: 'var(--text-3)' },
                      ].map(row => (
                        <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span className="label-xs">{row.label}</span>
                          <span style={{ fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)', color: row.color }}>{row.value}</span>
                        </div>
                      ))}
                      {cameraStatus?.last_event_time && (
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span className="label-xs">Last event</span>
                          <span className="label-xs">{formatDate(cameraStatus.last_event_time)}</span>
                        </div>
                      )}
                    </div>

                    {/* AI error */}
                    {cameraStatus?.error && (
                      <div style={{ fontSize: '11px', color: 'var(--rose)', fontFamily: 'var(--font-geist-mono, monospace)', background: 'rgba(244,63,94,0.06)', border: '1px solid rgba(244,63,94,0.2)', borderRadius: '7px', padding: '9px 12px', lineHeight: 1.5 }}>
                        ⚠ {cameraStatus.error}
                      </div>
                    )}

                    {/* AI start / stop */}
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        type="button"
                        onClick={startCamera}
                        disabled={cameraLoading || cameraRunning}
                        style={{
                          flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '7px',
                          padding: '9px 12px', borderRadius: '8px',
                          fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 500,
                          border: `1px solid ${cameraRunning ? 'rgba(16,217,132,0.1)' : 'rgba(16,217,132,0.38)'}`,
                          color: cameraRunning ? 'rgba(16,217,132,0.3)' : 'var(--emerald)',
                          background: cameraRunning ? 'rgba(16,217,132,0.02)' : 'rgba(16,217,132,0.07)',
                          cursor: (cameraLoading || cameraRunning) ? 'default' as const : 'pointer' as const,
                          transition: 'all 0.2s',
                        }}
                      >
                        ⬡ Start AI Analysis
                      </button>
                      <button
                        type="button"
                        onClick={stopCamera}
                        disabled={cameraLoading || !cameraRunning}
                        style={{
                          flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '7px',
                          padding: '9px 12px', borderRadius: '8px',
                          fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 500,
                          border: `1px solid ${!cameraRunning ? 'rgba(244,63,94,0.08)' : 'rgba(244,63,94,0.38)'}`,
                          color: !cameraRunning ? 'rgba(244,63,94,0.3)' : 'var(--rose)',
                          background: !cameraRunning ? 'transparent' : 'rgba(244,63,94,0.06)',
                          cursor: (cameraLoading || !cameraRunning) ? 'default' as const : 'pointer' as const,
                          transition: 'all 0.2s',
                        }}
                      >
                        ⏹ Stop AI
                      </button>
                    </div>

                    {/* Install hint / events note */}
                    <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '4px' }}>
                      {cameraStatus?.camera_available !== true && (
                        <div className="label-xs" style={{ opacity: 0.45 }}>
                          pip install opencv-python-headless ultralytics numpy
                        </div>
                      )}
                      {(cameraStatus?.event_count ?? 0) > 0 && (
                        <div className="label-xs" style={{ opacity: 0.45 }}>
                          Detected events appear in Timeline tab
                        </div>
                      )}
                    </div>
                  </div>

                </div>
              </div>

              {/* ── Prediction panel ── */}
              {cameraRunning && (
                <div style={{
                  background: 'rgba(0,212,255,0.03)',
                  border: '1px solid rgba(0,212,255,0.14)',
                  borderRadius: '14px',
                  padding: '18px 20px',
                  marginBottom: '24px',
                }}>
                  {/* Header */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
                    <span style={{ fontSize: '13px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.14em', color: 'var(--cyan)', fontWeight: 700 }}>
                      ◈ MOTION PREDICTIONS
                    </span>
                    <span style={{
                      fontSize: '9px', padding: '2px 7px', borderRadius: '4px',
                      background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.25)',
                      color: 'var(--violet)', fontFamily: 'var(--font-geist-mono, monospace)',
                      letterSpacing: '0.1em',
                    }}>HEURISTIC</span>
                    <span style={{ flex: 1 }} />
                    <span style={{ fontSize: '10px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                      {predictions.length} object{predictions.length !== 1 ? 's' : ''} tracked
                    </span>
                  </div>

                  {/* Disclaimer */}
                  <div style={{
                    fontSize: '10px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)',
                    marginBottom: '14px', padding: '6px 10px',
                    background: 'rgba(255,255,255,0.03)', borderRadius: '6px',
                    border: '1px solid rgba(255,255,255,0.05)',
                  }}>
                    ⚠ Prediction is heuristic, not guaranteed. Based on linear velocity extrapolation (1.5 s horizon).
                  </div>

                  {predictions.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--text-4)', fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                      {cameraStatus?.detection_mode === 'yolo'
                        ? 'No objects tracked yet — predictions appear once objects have been observed for 2+ frames'
                        : 'Predictions require YOLO — install ultralytics for object tracking'}
                    </div>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '10px' }}>
                      {predictions.map(p => {
                        const dirIcon: Record<string, string> = {
                          approaching: '↗', leaving: '↙', left: '←', right: '→',
                          up: '↑', down: '↓', stationary: '◉',
                        }
                        const dirColor: Record<string, string> = {
                          approaching: 'var(--rose)', leaving: 'var(--amber)',
                          left: 'var(--cyan)', right: 'var(--cyan)',
                          up: 'var(--violet)', down: 'var(--violet)',
                          stationary: 'var(--text-4)',
                        }
                        const icon = dirIcon[p.direction] ?? '?'
                        const color = dirColor[p.direction] ?? 'var(--text-3)'
                        const confidencePct = Math.round(p.confidence * 100)
                        return (
                          <div key={p.track_id} style={{
                            background: 'rgba(255,255,255,0.02)',
                            border: '1px solid rgba(255,255,255,0.07)',
                            borderRadius: '10px',
                            padding: '12px 14px',
                          }}>
                            {/* Track header */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                              <span style={{ fontSize: '16px', color }}>{icon}</span>
                              <span style={{ fontSize: '11px', color: 'var(--text-2)', fontWeight: 600 }}>
                                {p.label.charAt(0).toUpperCase() + p.label.slice(1)}
                              </span>
                              <span style={{
                                fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)',
                                color: 'var(--text-4)', marginLeft: 'auto',
                              }}>
                                {p.track_id}
                              </span>
                            </div>

                            {/* Stats grid */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px', marginBottom: '8px' }}>
                              {[
                                { k: 'Direction', v: p.direction, c: color },
                                { k: 'Speed',     v: p.speed.toFixed(3), c: 'var(--text-2)' },
                                { k: 'Trend',     v: p.area_trend, c: 'var(--text-3)' },
                                { k: 'Confidence', v: `${confidencePct}%`, c: confidencePct >= 70 ? 'var(--emerald)' : confidencePct >= 50 ? 'var(--amber)' : 'var(--rose)' },
                              ].map(row => (
                                <div key={row.k}>
                                  <div style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.08em' }}>{row.k.toUpperCase()}</div>
                                  <div style={{ fontSize: '11px', color: row.c, fontWeight: 500 }}>{row.v}</div>
                                </div>
                              ))}
                            </div>

                            {/* Predicted position */}
                            <div style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', marginBottom: '6px' }}>
                              NOW ({p.current_x.toFixed(2)}, {p.current_y.toFixed(2)}) → PRED ({p.predicted_x.toFixed(2)}, {p.predicted_y.toFixed(2)})
                            </div>

                            {/* Prediction events */}
                            {p.prediction_events.length > 0 && (
                              <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: '4px' }}>
                                {p.prediction_events.map(evt => (
                                  <span key={evt} style={{
                                    fontSize: '9px', padding: '2px 6px', borderRadius: '4px',
                                    background: 'rgba(244,63,94,0.1)', border: '1px solid rgba(244,63,94,0.25)',
                                    color: 'var(--rose)', fontFamily: 'var(--font-geist-mono, monospace)',
                                    letterSpacing: '0.06em',
                                  }}>
                                    {evt.replace(/_/g, ' ')}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* ── Multi-Camera Panel ── */}
              <div style={{
                background: 'rgba(124,58,237,0.03)',
                border: '1px solid rgba(124,58,237,0.18)',
                borderRadius: '14px',
                padding: '18px 20px',
                marginBottom: '8px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
                  <span style={{ fontSize: '13px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.14em', color: 'var(--violet)', fontWeight: 700 }}>
                    ◈ MULTI-CAMERA REGISTRY
                  </span>
                  <span style={{ flex: 1 }} />
                  <button onClick={fetchMultiCameras} className="btn-ghost" style={{ fontSize: '10px', padding: '3px 10px' }}>↺</button>
                </div>

                {/* Add Camera form */}
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' as const, marginBottom: '14px', alignItems: 'flex-end' }}>
                  <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '4px' }}>
                    <label style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em' }}>NAME</label>
                    <input
                      value={mcAddName}
                      onChange={e => setMcAddName(e.target.value)}
                      placeholder="Kitchen Cam"
                      style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', color: 'var(--text-1)', padding: '6px 10px', fontSize: '12px', width: '140px', fontFamily: 'var(--font-geist-mono, monospace)' }}
                    />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '4px' }}>
                    <label style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em' }}>TYPE</label>
                    <select
                      value={mcAddType}
                      onChange={e => setMcAddType(e.target.value as 'webcam' | 'rtsp' | 'file')}
                      style={{ background: '#0a1428', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', color: 'var(--text-2)', padding: '6px 10px', fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)' }}
                    >
                      <option value="webcam">Webcam</option>
                      <option value="rtsp">RTSP</option>
                      <option value="file">File</option>
                    </select>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '4px' }}>
                    <label style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em' }}>
                      {mcAddType === 'webcam' ? 'INDEX' : mcAddType === 'rtsp' ? 'RTSP URL' : 'FILE PATH'}
                    </label>
                    <input
                      value={mcAddSource}
                      onChange={e => setMcAddSource(e.target.value)}
                      placeholder={mcAddType === 'webcam' ? '0' : mcAddType === 'rtsp' ? 'rtsp://…' : '/path/to/video.mp4'}
                      style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', color: 'var(--text-1)', padding: '6px 10px', fontSize: '12px', width: mcAddType === 'webcam' ? '60px' : '200px', fontFamily: 'var(--font-geist-mono, monospace)' }}
                    />
                  </div>
                  <button
                    onClick={addMultiCamera}
                    disabled={mcAdding || !mcAddName.trim()}
                    style={{
                      padding: '7px 16px', borderRadius: '7px', fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)',
                      border: '1px solid rgba(124,58,237,0.4)', color: 'var(--violet)',
                      background: 'rgba(124,58,237,0.1)', cursor: mcAdding || !mcAddName.trim() ? 'default' : 'pointer',
                      opacity: !mcAddName.trim() ? 0.4 : 1,
                    }}
                  >
                    {mcAdding ? '…' : '+ Add Camera'}
                  </button>
                </div>

                {/* Camera cards */}
                {multiCameras.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '16px 0', fontSize: '11px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                    No cameras registered. Add one above to begin multi-camera monitoring.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '10px' }}>
                    {multiCameras.map(cam => (
                      <div key={cam.camera_id} style={{
                        background: 'rgba(255,255,255,0.02)',
                        border: `1px solid ${cam.running ? 'rgba(16,217,132,0.25)' : cam.error ? 'rgba(244,63,94,0.2)' : 'rgba(255,255,255,0.07)'}`,
                        borderRadius: '10px',
                        padding: '12px 14px',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                          <span style={{ fontSize: '9px', fontFamily: 'var(--font-geist-mono, monospace)', color: cam.running ? 'var(--emerald)' : 'var(--text-4)', letterSpacing: '0.1em' }}>
                            {cam.running ? '● LIVE' : '○ IDLE'}
                          </span>
                          <span style={{ fontSize: '12px', color: 'var(--text-1)', fontWeight: 600, flex: 1 }}>{cam.name}</span>
                          <span style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)' }}>{cam.camera_id}</span>
                        </div>
                        <div style={{ fontSize: '10px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', marginBottom: '6px' }}>
                          {cam.source_type.toUpperCase()} · {cam.source} · {cam.detection_mode}
                        </div>
                        {cam.error && (
                          <div style={{ fontSize: '10px', color: 'var(--rose)', marginBottom: '6px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                            ⚠ {cam.error}
                          </div>
                        )}
                        {cam.last_event_time && (
                          <div style={{ fontSize: '9px', color: 'var(--text-4)', marginBottom: '8px' }}>
                            Last event: {formatDateShort(cam.last_event_time)} · {cam.event_count} total
                          </div>
                        )}
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            onClick={() => startMultiCam(cam.camera_id)}
                            disabled={cam.running}
                            style={{ padding: '4px 10px', fontSize: '10px', borderRadius: '5px', fontFamily: 'var(--font-geist-mono, monospace)', border: `1px solid ${cam.running ? 'rgba(16,217,132,0.1)' : 'rgba(16,217,132,0.4)'}`, color: cam.running ? 'rgba(16,217,132,0.3)' : 'var(--emerald)', background: 'transparent', cursor: cam.running ? 'default' : 'pointer' }}
                          >Start</button>
                          <button
                            onClick={() => stopMultiCam(cam.camera_id)}
                            disabled={!cam.running}
                            style={{ padding: '4px 10px', fontSize: '10px', borderRadius: '5px', fontFamily: 'var(--font-geist-mono, monospace)', border: `1px solid ${!cam.running ? 'rgba(244,63,94,0.1)' : 'rgba(244,63,94,0.4)'}`, color: !cam.running ? 'rgba(244,63,94,0.3)' : 'var(--rose)', background: 'transparent', cursor: !cam.running ? 'default' : 'pointer' }}
                          >Stop</button>
                          <span style={{ flex: 1 }} />
                          <button
                            onClick={() => deleteMultiCam(cam.camera_id)}
                            style={{ padding: '4px 10px', fontSize: '10px', borderRadius: '5px', fontFamily: 'var(--font-geist-mono, monospace)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-4)', background: 'transparent', cursor: 'pointer' }}
                          >✕</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* ── World Model Panel ── */}
              <div style={{
                background: 'rgba(16,217,132,0.02)',
                border: '1px solid rgba(16,217,132,0.14)',
                borderRadius: '14px',
                padding: '18px 20px',
                marginBottom: '8px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
                  <span style={{ fontSize: '13px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.14em', color: 'var(--emerald)', fontWeight: 700 }}>
                    ◈ WORLD MODEL
                  </span>
                  <span style={{ fontSize: '9px', padding: '2px 6px', borderRadius: '3px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                    HEURISTIC
                  </span>
                  <span style={{ flex: 1 }} />
                  <button
                    onClick={fetchWorldState}
                    disabled={loadingWorld}
                    className="btn-ghost"
                    style={{ fontSize: '10px', padding: '3px 10px' }}
                  >
                    {loadingWorld ? '⟳' : '↺ Refresh'}
                  </button>
                </div>

                {!worldState ? (
                  <div style={{ textAlign: 'center', padding: '16px 0', fontSize: '11px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                    Click Refresh to load world state, or start a camera to build live scene awareness.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '12px' }}>

                    {/* World state text + confidence */}
                    <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                      <div style={{ fontSize: '13px', color: 'var(--text-1)', flex: 1, lineHeight: 1.5, fontFamily: 'var(--font-geist-mono, monospace)' }}>
                        {worldState.world_state}
                      </div>
                      <div style={{ textAlign: 'right' as const, flexShrink: 0 }}>
                        <div style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '2px' }}>CONFIDENCE</div>
                        <div style={{ fontSize: '16px', fontWeight: 700, color: worldState.confidence >= 0.6 ? 'var(--emerald)' : worldState.confidence >= 0.4 ? 'var(--amber)' : 'var(--text-4)' }}>
                          {Math.round(worldState.confidence * 100)}%
                        </div>
                      </div>
                    </div>

                    {/* Disclaimer */}
                    <div style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', padding: '5px 8px', background: 'rgba(255,255,255,0.02)', borderRadius: '5px', border: '1px solid rgba(255,255,255,0.04)' }}>
                      ⚠ {worldState.disclaimer}
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '10px' }}>

                      {/* Active Entities */}
                      {worldState.active_entities.length > 0 && (
                        <div style={{ padding: '10px 12px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px' }}>
                          <div style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '6px' }}>ACTIVE ENTITIES</div>
                          <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: '5px' }}>
                            {worldState.active_entities.map((e, i) => (
                              <span key={i} style={{ padding: '3px 8px', borderRadius: '4px', background: 'rgba(16,217,132,0.08)', border: '1px solid rgba(16,217,132,0.25)', color: 'var(--emerald)', fontSize: '10px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                                {e.label} ×{e.count}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Zones */}
                      {Object.keys(worldState.zones).length > 0 && (
                        <div style={{ padding: '10px 12px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px' }}>
                          <div style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '6px' }}>ZONES</div>
                          {Object.entries(worldState.zones).map(([zone, labels]) => (
                            <div key={zone} style={{ fontSize: '10px', color: 'var(--text-3)', fontFamily: 'var(--font-geist-mono, monospace)', marginBottom: '3px' }}>
                              <span style={{ color: 'var(--cyan)' }}>{zone}</span>: {(labels as string[]).join(', ')}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Risk notes */}
                      {worldState.risk_notes.length > 0 && (
                        <div style={{ padding: '10px 12px', background: 'rgba(244,63,94,0.03)', border: '1px solid rgba(244,63,94,0.15)', borderRadius: '8px' }}>
                          <div style={{ fontSize: '9px', color: 'var(--rose)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '6px' }}>RISK NOTES</div>
                          {worldState.risk_notes.map((note, i) => (
                            <div key={i} style={{ fontSize: '10px', color: 'var(--text-3)', fontFamily: 'var(--font-geist-mono, monospace)', marginBottom: '3px', lineHeight: 1.4 }}>{note}</div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Movement predictions */}
                    {worldState.movement_predictions.length > 0 && (
                      <div>
                        <div style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '6px' }}>MOVEMENT PREDICTIONS (ESTIMATED)</div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '6px' }}>
                          {worldState.movement_predictions.slice(0, 6).map((p, i) => {
                            const dirIcon: Record<string, string> = { approaching: '↗', leaving: '↙', left: '←', right: '→', up: '↑', down: '↓', stationary: '◉' }
                            return (
                              <div key={i} style={{ padding: '8px 10px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '7px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  <span style={{ fontSize: '12px', color: 'var(--cyan)' }}>{dirIcon[p.direction] ?? '?'}</span>
                                  <span style={{ fontSize: '11px', color: 'var(--text-2)', fontWeight: 600 }}>{p.label}</span>
                                  <span style={{ fontSize: '9px', color: 'var(--text-4)', marginLeft: 'auto', fontFamily: 'var(--font-geist-mono, monospace)' }}>{Math.round(p.confidence * 100)}%</span>
                                </div>
                                <div style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', marginTop: '3px' }}>
                                  {p.direction} · speed {p.speed.toFixed(3)}
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )}

                    {/* Event timeline */}
                    {worldState.recent_events.length > 0 && (
                      <div>
                        <div style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '6px' }}>ACTIVITY TIMELINE</div>
                        <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '3px', maxHeight: '180px', overflowY: 'auto' as const }}>
                          {worldState.recent_events.map((ev, i) => (
                            <div key={i} style={{ display: 'flex', gap: '8px', alignItems: 'center', fontSize: '10px', color: 'var(--text-3)', fontFamily: 'var(--font-geist-mono, monospace)', padding: '4px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.01)' }}>
                              <span style={{ color: 'var(--text-4)', minWidth: '80px' }}>{ev.created_at ? formatDateShort(ev.created_at) : ''}</span>
                              <span style={{ color: 'var(--cyan)' }}>{ev.event_type.replace(/_/g, ' ')}</span>
                              <span>{ev.labels.slice(0, 3).join(', ')}</span>
                              {ev.camera_name && <span style={{ color: 'var(--text-4)', marginLeft: 'auto' }}>{ev.camera_name}</span>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Video list */}
              {loadingVideos ? (
                <div className="empty-state">
                  <span className="spin-ring">⟳</span>
                  <div className="empty-title" style={{ marginTop: '16px' }}>LOADING VIDEOS…</div>
                </div>
              ) : videos.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-4)' }}>
                  <div style={{ fontSize: '13px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.15em', marginBottom: '8px' }}>NO VIDEOS YET</div>
                  <div style={{ fontSize: '12px' }}>Use the <strong style={{ color: 'var(--violet)' }}>Upload Video</strong> button above to analyse your first video.</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-4)', marginTop: '8px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                    Optional: pip install opencv-python-headless ultralytics numpy
                  </div>
                </div>
              ) : (
                <>
                  <div className="section-title">Uploaded Videos — {videos.length} total</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
                    {videos.map(v => (
                      <VideoCard
                        key={v.id}
                        video={v}
                        onClick={() => openVideoDetail(v)}
                        onDelete={() => deleteVideo(v.id)}
                      />
                    ))}
                  </div>
                </>
              )}
              {videoUploadError && <p className="error-text">{videoUploadError}</p>}
              {visionVideoError  && <p className="error-text">{visionVideoError}</p>}
            </div>
          )
        )}

        {/* ── Replay Studio tab ── */}
        {activeTab === 'replay' && (
          <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '24px' }}>

            {/* Header */}
            <div>
              <div style={{ fontSize: '20px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 700, color: 'var(--cyan)', letterSpacing: '0.1em' }}>
                REPLAY STUDIO
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', marginTop: '3px' }}>
                Chronological replay by date · topic · modality
              </div>
            </div>

            {/* Mode selector */}
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' as const }}>
              {(['day', 'topic', 'modality'] as const).map(mode => (
                <button
                  key={mode}
                  onClick={() => { setReplayTab(mode); setReplayResult(null) }}
                  className={`tab-btn ${replayTab === mode ? 'active' : 'inactive'}`}
                  style={{ padding: '7px 18px', fontSize: '11px' }}
                >
                  {mode === 'day' ? '◈ By Date' : mode === 'topic' ? '◉ By Topic' : '◫ By Modality'}
                </button>
              ))}
            </div>

            {/* Controls */}
            <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-end', flexWrap: 'wrap' as const }}>
              {replayTab === 'day' && (
                <input
                  type="date"
                  value={replayDate}
                  onChange={e => setReplayDate(e.target.value)}
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', color: 'var(--text-1)', padding: '8px 12px', fontSize: '13px', fontFamily: 'var(--font-geist-mono, monospace)' }}
                />
              )}
              {replayTab === 'topic' && (
                <input
                  value={replayQuery}
                  onChange={e => setReplayQuery(e.target.value)}
                  placeholder="e.g. YOLO debugging, FastAPI, meeting notes…"
                  onKeyDown={e => e.key === 'Enter' && runReplay()}
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', color: 'var(--text-1)', padding: '8px 14px', fontSize: '13px', width: '320px', fontFamily: 'var(--font-geist-mono, monospace)' }}
                />
              )}
              {replayTab === 'modality' && (
                <select
                  value={replayModality}
                  onChange={e => setReplayModality(e.target.value)}
                  style={{ background: '#0a1428', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', color: 'var(--text-2)', padding: '8px 12px', fontSize: '13px', fontFamily: 'var(--font-geist-mono, monospace)' }}
                >
                  {['screenshot', 'pdf', 'voice', 'video', 'image', 'text'].map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              )}
              <button
                onClick={runReplay}
                disabled={loadingReplay}
                style={{
                  padding: '9px 22px', borderRadius: '8px', fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 700,
                  border: '1px solid rgba(0,212,255,0.4)', color: 'var(--cyan)', background: 'rgba(0,212,255,0.08)',
                  cursor: loadingReplay ? 'default' : 'pointer',
                }}
              >
                {loadingReplay ? '⟳ Replaying…' : '▶ Run Replay'}
              </button>
            </div>

            {/* Results */}
            {loadingReplay ? (
              <div className="empty-state">
                <span className="spin-ring" style={{ fontSize: '32px' }}>⟳</span>
                <div className="empty-title" style={{ marginTop: '16px' }}>REPLAYING MEMORY…</div>
              </div>
            ) : replayResult ? (
              <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '18px' }}>

                {/* Summary card */}
                <div className="glass-card" style={{ padding: '16px 20px', borderLeft: '3px solid rgba(0,212,255,0.4)' }}>
                  <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--cyan)', marginBottom: '6px' }}>{replayResult.replay_title}</div>
                  <div style={{ fontSize: '13px', color: 'var(--text-2)', lineHeight: 1.7, fontFamily: 'var(--font-geist-mono, monospace)' }}>{replayResult.summary}</div>
                  <div style={{ display: 'flex', gap: '16px', marginTop: '12px', flexWrap: 'wrap' as const }}>
                    {[
                      { k: 'Events', v: replayResult.total_count },
                      { k: 'Key Moments', v: replayResult.key_moments.length },
                      { k: 'Apps', v: replayResult.apps_used.length },
                      { k: 'Confidence', v: `${Math.round(replayResult.confidence * 100)}%` },
                    ].map(row => (
                      <div key={row.k}>
                        <div style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em' }}>{row.k.toUpperCase()}</div>
                        <div style={{ fontSize: '14px', color: 'var(--text-1)', fontWeight: 700 }}>{row.v}</div>
                      </div>
                    ))}
                    <div>
                      <div style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em' }}>APPS USED</div>
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' as const, marginTop: '2px' }}>
                        {replayResult.apps_used.slice(0, 6).map(a => <AppBadge key={a} appName={a} />)}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Key Moments */}
                {replayResult.key_moments.length > 0 && (
                  <div>
                    <div className="section-title" style={{ marginBottom: '10px' }}>Key Moments</div>
                    <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '8px' }}>
                      {replayResult.key_moments.map((km, i) => (
                        <div key={i} style={{ display: 'flex', gap: '12px', alignItems: 'flex-start', padding: '10px 14px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px' }}>
                          <span style={{
                            fontSize: '9px', padding: '3px 7px', borderRadius: '4px', whiteSpace: 'nowrap' as const,
                            background: km.moment_type === 'debug_start' ? 'rgba(244,63,94,0.1)' : km.moment_type === 'ai_research' ? 'rgba(139,92,246,0.1)' : 'rgba(0,212,255,0.08)',
                            border: `1px solid ${km.moment_type === 'debug_start' ? 'rgba(244,63,94,0.3)' : km.moment_type === 'ai_research' ? 'rgba(139,92,246,0.3)' : 'rgba(0,212,255,0.2)'}`,
                            color: km.moment_type === 'debug_start' ? 'var(--rose)' : km.moment_type === 'ai_research' ? 'var(--violet)' : 'var(--cyan)',
                            fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.08em',
                          }}>
                            {km.moment_type.replace(/_/g, ' ')}
                          </span>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: '12px', color: 'var(--text-1)', fontWeight: 600 }}>{km.title}</div>
                            <div style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: '2px', fontFamily: 'var(--font-geist-mono, monospace)' }}>{km.description}</div>
                          </div>
                          <div style={{ fontSize: '10px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', whiteSpace: 'nowrap' as const }}>
                            {formatDateShort(km.created_at)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Chronological Timeline */}
                <div>
                  <div className="section-title" style={{ marginBottom: '10px' }}>
                    Chronological Timeline — {replayResult.ordered_events.length} events
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '4px', maxHeight: '480px', overflowY: 'auto' as const, paddingRight: '4px' }}>
                    {replayResult.ordered_events.map((ev, i) => (
                      <div key={ev.id ?? i} style={{ display: 'flex', gap: '10px', alignItems: 'center', padding: '7px 12px', background: 'rgba(255,255,255,0.015)', border: '1px solid rgba(255,255,255,0.04)', borderRadius: '6px' }}>
                        <span style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', minWidth: '100px' }}>
                          {formatDateShort(ev.created_at)}
                        </span>
                        <TypeBadge type={ev.type} />
                        <span style={{ fontSize: '12px', color: 'var(--text-2)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                          {ev.title}
                        </span>
                        {ev.app_name && <AppBadge appName={ev.app_name} />}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-icon">◈</div>
                <div className="empty-title">REPLAY STUDIO</div>
                <div className="empty-sub">Choose a mode above and run replay to explore your memory timeline.</div>
              </div>
            )}
          </div>
        )}

        {/* ── Digital Soul tab ── */}
        {activeTab === 'soul' && (
          <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '24px' }}>

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <div>
                <div style={{ fontSize: '20px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 700, color: 'var(--violet)', letterSpacing: '0.1em' }}>
                  DIGITAL SOUL
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', marginTop: '3px' }}>
                  Behavioral intelligence from local memory metadata · Privacy-first
                </div>
              </div>
              <span style={{ flex: 1 }} />
              <button onClick={fetchSoulData} disabled={loadingSoul} className="btn-outline" style={{ padding: '6px 14px', fontSize: '11px' }}>
                {loadingSoul ? '⟳' : '↺ Refresh'}
              </button>
            </div>

            {loadingSoul && !soulLoaded ? (
              <div className="empty-state">
                <span className="spin-ring" style={{ fontSize: '32px' }}>⟳</span>
                <div className="empty-title" style={{ marginTop: '16px' }}>COMPUTING SOUL PROFILE…</div>
              </div>
            ) : !soulLoaded ? (
              <div className="empty-state">
                <div className="empty-icon" style={{ color: 'var(--violet)' }}>◉</div>
                <div className="empty-title">DIGITAL SOUL</div>
                <div className="empty-sub">Analyzes behavioral patterns from your local memory metadata.</div>
                <button onClick={fetchSoulData} className="btn-outline" style={{ marginTop: '20px' }}>Load Soul Profile</button>
              </div>
            ) : (
              <>
                {/* Behavioral Patterns */}
                <div>
                  <div className="section-title" style={{ marginBottom: '12px' }}>Behavioral Patterns — {soulPatterns.length} detected</div>
                  {soulPatterns.length === 0 ? (
                    <div style={{ fontSize: '12px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                      Not enough memories yet to detect patterns. Capture more memories first.
                    </div>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '12px' }}>
                      {soulPatterns.map((p, i) => (
                        <div key={i} style={{
                          background: 'rgba(139,92,246,0.04)',
                          border: `1px solid rgba(139,92,246,${0.1 + p.strength * 0.25})`,
                          borderRadius: '12px', padding: '14px 16px',
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-1)' }}>{p.name}</span>
                            <span style={{
                              fontSize: '9px', padding: '2px 7px', borderRadius: '4px',
                              background: p.type === 'workflow' ? 'rgba(0,212,255,0.1)' : p.type === 'modality' ? 'rgba(245,158,11,0.1)' : 'rgba(16,217,132,0.1)',
                              border: `1px solid ${p.type === 'workflow' ? 'rgba(0,212,255,0.3)' : p.type === 'modality' ? 'rgba(245,158,11,0.3)' : 'rgba(16,217,132,0.3)'}`,
                              color: p.type === 'workflow' ? 'var(--cyan)' : p.type === 'modality' ? 'var(--amber)' : 'var(--emerald)',
                              fontFamily: 'var(--font-geist-mono, monospace)',
                            }}>{p.type}</span>
                            <span style={{ flex: 1 }} />
                            <span style={{ fontSize: '10px', color: p.strength >= 0.7 ? 'var(--emerald)' : p.strength >= 0.4 ? 'var(--amber)' : 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                              {Math.round(p.strength * 100)}%
                            </span>
                          </div>
                          {/* Strength bar */}
                          <div style={{ height: '3px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px', marginBottom: '10px' }}>
                            <div style={{ height: '100%', width: `${p.strength * 100}%`, background: 'var(--violet)', borderRadius: '2px', transition: 'width 0.4s' }} />
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--text-2)', lineHeight: 1.5, marginBottom: '6px' }}>{p.description}</div>
                          <div style={{ fontSize: '10px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', padding: '5px 8px', background: 'rgba(255,255,255,0.02)', borderRadius: '5px' }}>
                            Evidence: {p.evidence}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Workflow Rhythm */}
                {workflowRhythm && (
                  <div>
                    <div className="section-title" style={{ marginBottom: '12px' }}>Workflow Rhythm</div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>

                      {/* Peak hours */}
                      <div className="glass-card" style={{ padding: '14px 16px' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '8px' }}>PEAK HOURS</div>
                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' as const }}>
                          {workflowRhythm.peak_hours.map(h => (
                            <span key={h} style={{ padding: '4px 10px', borderRadius: '6px', background: 'rgba(0,212,255,0.1)', border: '1px solid rgba(0,212,255,0.3)', color: 'var(--cyan)', fontSize: '12px', fontFamily: 'var(--font-geist-mono, monospace)' }}>{h}</span>
                          ))}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: '8px' }}>
                          Most active day: <span style={{ color: 'var(--text-1)', fontWeight: 600 }}>{workflowRhythm.most_active_day}</span>
                        </div>
                      </div>

                      {/* Day of week */}
                      <div className="glass-card" style={{ padding: '14px 16px' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '8px' }}>DAY OF WEEK</div>
                        <div style={{ display: 'flex', gap: '4px', alignItems: 'flex-end', height: '48px' }}>
                          {Object.entries(workflowRhythm.day_of_week).map(([day, cnt]) => {
                            const maxVal = Math.max(...Object.values(workflowRhythm.day_of_week), 1)
                            const pct = (cnt as number) / maxVal
                            return (
                              <div key={day} style={{ flex: 1, display: 'flex', flexDirection: 'column' as const, alignItems: 'center', gap: '2px' }}>
                                <div style={{ width: '100%', background: pct > 0.6 ? 'var(--violet)' : pct > 0.3 ? 'rgba(139,92,246,0.5)' : 'rgba(139,92,246,0.2)', borderRadius: '2px', height: `${Math.max(4, pct * 44)}px`, transition: 'height 0.3s' }} />
                                <span style={{ fontSize: '8px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)' }}>{day.slice(0, 2)}</span>
                              </div>
                            )
                          })}
                        </div>
                      </div>

                      {/* Top activity periods */}
                      {workflowRhythm.peak_activities.length > 0 && (
                        <div className="glass-card" style={{ padding: '14px 16px', gridColumn: 'span 1' as const }}>
                          <div style={{ fontSize: '11px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '8px' }}>TOP ACTIVITY PERIODS</div>
                          <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '5px' }}>
                            {workflowRhythm.peak_activities.slice(0, 4).map((a, i) => (
                              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span style={{ fontSize: '11px', color: 'var(--cyan)', fontFamily: 'var(--font-geist-mono, monospace)', minWidth: '38px' }}>{a.hour_label}</span>
                                <div style={{ flex: 1, height: '6px', background: 'rgba(255,255,255,0.04)', borderRadius: '3px' }}>
                                  <div style={{ height: '100%', width: `${Math.min(100, (a.count / (workflowRhythm.peak_activities[0]?.count || 1)) * 100)}%`, background: 'rgba(0,212,255,0.5)', borderRadius: '3px' }} />
                                </div>
                                <span style={{ fontSize: '10px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', minWidth: '28px' }}>{a.count}</span>
                                <span style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)' }}>{a.top_scene}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Project Memory */}
                {projectMemory && (
                  <div>
                    <div className="section-title" style={{ marginBottom: '12px' }}>Project Memory</div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>

                      {/* Top projects */}
                      {projectMemory.top_projects.length > 0 && (
                        <div className="glass-card" style={{ padding: '14px 16px' }}>
                          <div style={{ fontSize: '11px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '8px' }}>RECURRING PROJECTS</div>
                          <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '6px' }}>
                            {projectMemory.top_projects.slice(0, 6).map((p, i) => (
                              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span style={{ fontSize: '12px', color: 'var(--text-2)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{p.name}</span>
                                <span style={{ fontSize: '10px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)' }}>{p.mentions}×</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Recent keywords */}
                      {projectMemory.recent_keywords.length > 0 && (
                        <div className="glass-card" style={{ padding: '14px 16px' }}>
                          <div style={{ fontSize: '11px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '8px' }}>RECENT KEYWORDS</div>
                          <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' as const }}>
                            {projectMemory.recent_keywords.map(kw => (
                              <span key={kw} style={{ padding: '3px 8px', borderRadius: '4px', background: 'rgba(0,212,255,0.06)', border: '1px solid rgba(0,212,255,0.15)', color: 'var(--text-3)', fontSize: '10px', fontFamily: 'var(--font-geist-mono, monospace)' }}>{kw}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Unfinished sessions */}
                      {projectMemory.unfinished_sessions.length > 0 && (
                        <div className="glass-card" style={{ padding: '14px 16px' }}>
                          <div style={{ fontSize: '11px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.1em', marginBottom: '8px' }}>UNFINISHED SESSIONS</div>
                          <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '7px' }}>
                            {projectMemory.unfinished_sessions.map((s, i) => (
                              <div key={i} style={{ padding: '8px 10px', background: 'rgba(245,158,11,0.04)', border: '1px solid rgba(245,158,11,0.15)', borderRadius: '7px' }}>
                                <div style={{ fontSize: '12px', color: 'var(--text-1)', marginBottom: '3px' }}>{s.title}</div>
                                <div style={{ fontSize: '10px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                                  {s.duration_str} · {formatDateShort(s.ended_at)}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Sessions tab */}
        {activeTab === 'sessions' && (
          activeSession ? (
            /* Session detail */
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Back + metadata */}
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                <button
                  onClick={() => setActiveSession(null)}
                  style={{
                    background: 'transparent',
                    border: '1px solid #0c1e38',
                    color: '#2a5070',
                    fontSize: '11px',
                    padding: '5px 12px',
                    borderRadius: '5px',
                    cursor: 'pointer',
                    fontFamily: 'var(--font-geist-mono, monospace)',
                    flexShrink: 0,
                  }}
                >
                  ← Sessions
                </button>
                <button
                  onClick={() => openReplay(activeSession.session_id)}
                  style={{
                    background: '#00b4ff0a',
                    border: '1px solid #00b4ff22',
                    color: '#00b4ff',
                    fontSize: '11px',
                    padding: '5px 14px',
                    borderRadius: '5px',
                    cursor: 'pointer',
                    fontFamily: 'var(--font-geist-mono, monospace)',
                    flexShrink: 0,
                  }}
                >
                  ▶ Replay
                </button>
                <div style={{
                  flex: 1,
                  background: '#06060f',
                  border: '1px solid #0a1e38',
                  borderRadius: '6px',
                  padding: '12px 16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                }}>
                  <span style={{ color: '#dde8ff', fontWeight: 600, fontSize: '13px' }}>{activeSession.title}</span>
                  <span style={{ color: '#2a5070', fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                    {activeSession.duration_str} · {activeSession.memory_count} memories
                  </span>
                  <p style={{ color: '#2a4060', fontSize: '11px', margin: 0, fontFamily: 'var(--font-geist-mono, monospace)' }}>
                    {activeSession.summary}
                  </p>
                  {activeSession.topics && activeSession.topics.length > 0 && (
                    <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' as const, marginTop: '4px' }}>
                      {activeSession.topics.map(topic => {
                        const colors = APP_COLORS[topic] ?? { bg: '#0a1828', border: '#0e2438', text: '#3a6a8a' }
                        return (
                          <span key={topic} style={{
                            background: colors.bg,
                            border: `1px solid ${colors.border}`,
                            color: colors.text,
                            fontSize: '9px',
                            padding: '1px 7px',
                            borderRadius: '3px',
                            fontFamily: 'var(--font-geist-mono, monospace)',
                          }}>
                            {topic}
                          </span>
                        )
                      })}
                    </div>
                  )}
                  {activeSession.keywords.length > 0 && (
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' as const, marginTop: '2px' }}>
                      {activeSession.keywords.map(kw => (
                        <span key={kw} style={{ color: '#1e4060', fontSize: '10px', fontFamily: 'var(--font-geist-mono, monospace)' }}>{kw}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Session memories grid */}
              {loadingSession ? (
                <div style={{ textAlign: 'center', padding: '40px 0', color: '#1e4060' }}>
                  <div style={{ fontSize: '24px', animation: 'spin 1.5s linear infinite', display: 'inline-block' }}>⟳</div>
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))', gap: '14px' }}>
                  {activeSession.memories.map(item => (
                    <MemoryCard
                      key={item.id}
                      item={item}
                      onAskPdf={item.type === 'pdf' ? () => setPdfChatTarget(item) : undefined}
                    />
                  ))}
                </div>
              )}
            </div>
          ) : (
            /* Sessions list */
            loadingSessions ? (
              <div className="empty-state">
                <span className="spin-ring">⟳</span>
                <div className="empty-title" style={{ marginTop: '16px' }}>DETECTING SESSIONS…</div>
              </div>
            ) : sessions.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">◫</div>
                <div className="empty-title">NO SESSIONS YET</div>
                <div className="empty-sub">Start the screen watcher to capture memories and auto-detect sessions.</div>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '14px' }}>
                {sessions.map(s => (
                  <SessionCard
                    key={s.session_id}
                    session={s}
                    onClick={() => openSession(s.session_id)}
                    onReplay={() => openReplay(s.session_id)}
                  />
                ))}
              </div>
            )
          )
        )}

        {/* ── Agent Console tab ── */}
        {activeTab === 'agent' && (
          <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '24px' }}>

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <div>
                <div style={{ fontSize: '20px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 700, color: 'var(--cyan)', letterSpacing: '0.1em' }}>
                  EIDOLON AGENT
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', marginTop: '3px' }}>
                  Local-only · Safe action registry · No cloud
                </div>
              </div>
              <span style={{ flex: 1 }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: '5px',
                  fontSize: '10px', padding: '4px 10px', borderRadius: '6px',
                  background: screenWatchRunning ? 'rgba(16,217,132,0.1)' : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${screenWatchRunning ? 'rgba(16,217,132,0.3)' : 'rgba(255,255,255,0.08)'}`,
                  color: screenWatchRunning ? 'var(--emerald)' : 'var(--text-4)',
                  fontFamily: 'var(--font-geist-mono, monospace)',
                }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: screenWatchRunning ? 'var(--emerald)' : 'rgba(255,255,255,0.2)' }} />
                  {screenWatchRunning ? 'SCREEN WATCH ON' : 'SCREEN WATCH OFF'}
                </span>
                <button
                  onClick={fetchAgentData}
                  className="btn-outline"
                  style={{ padding: '6px 14px', fontSize: '11px' }}
                >
                  ↺ Refresh
                </button>
              </div>
            </div>

            {/* Action result banner */}
            {agentResult && (
              <div style={{
                padding: '12px 16px', borderRadius: '10px',
                background: agentResult.success ? 'rgba(16,217,132,0.07)' : 'rgba(244,63,94,0.07)',
                border: `1px solid ${agentResult.success ? 'rgba(16,217,132,0.25)' : 'rgba(244,63,94,0.25)'}`,
                display: 'flex', alignItems: 'flex-start', gap: '10px',
              }}>
                <span style={{ fontSize: '14px', marginTop: '1px' }}>{agentResult.success ? '✓' : '⚠'}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '12px', color: agentResult.success ? 'var(--emerald)' : 'var(--rose)', fontWeight: 600, marginBottom: '4px' }}>
                    {agentResult.success ? 'Action Completed' : 'Action Failed'}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-2)' }}>{agentResult.message}</div>
                  {/* Show summary_text if present */}
                  {(agentResult as unknown as DailySummary).summary_text && (
                    <div style={{ fontSize: '11px', color: 'var(--cyan)', marginTop: '6px', fontStyle: 'italic' }}>
                      {(agentResult as unknown as DailySummary).summary_text}
                    </div>
                  )}
                  {/* Show search results count if present */}
                  {typeof (agentResult as AgentResult & { count?: number }).count === 'number' && (
                    <div style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: '4px' }}>
                      Found {(agentResult as AgentResult & { count?: number }).count} result(s)
                    </div>
                  )}
                </div>
                <button onClick={() => setAgentResult(null)} style={{ background: 'none', border: 'none', color: 'var(--text-4)', cursor: 'pointer', fontSize: '14px', padding: '0' }}>×</button>
              </div>
            )}

            {/* Two-column layout: Actions + Summary */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>

              {/* Quick Actions */}
              <div style={{
                background: 'rgba(0,212,255,0.03)', border: '1px solid rgba(0,212,255,0.12)',
                borderRadius: '14px', padding: '18px 20px',
              }}>
                <div style={{ fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.14em', color: 'var(--cyan)', fontWeight: 700, marginBottom: '14px' }}>
                  QUICK ACTIONS
                </div>
                <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '8px' }}>
                  {([
                    { id: 'open_vscode',   icon: '⬡', label: 'Open VSCode',          sub: 'Launch VS Code in project folder', action: () => runQuickAction('open_vscode',   'open_app',              { app_name: 'vscode' }) },
                    { id: 'open_folder',   icon: '◫', label: 'Open Project Folder',   sub: 'Open project root in Explorer',   action: () => runQuickAction('open_folder',   'open_folder',           {}) },
                    { id: 'open_browser',  icon: '⊕', label: 'Open Browser',          sub: 'Open EIDOLON at localhost:3000',  action: () => runQuickAction('open_browser',  'open_app',              { app_name: 'browser' }) },
                    { id: 'summarize',     icon: '◈', label: 'Summarize Today',        sub: 'Generate activity summary',       action: () => runQuickAction('summarize',      'summarize_today',       {}) },
                    { id: 'last_session',  icon: '◎', label: 'Continue Last Session',  sub: 'Resume most recent work session', action: () => runQuickAction('last_session',  'continue_last_session', {}) },
                  ] as const).map(btn => {
                    const loading = quickBtnLoading === btn.id
                    return (
                      <button
                        key={btn.id}
                        onClick={btn.action}
                        disabled={quickBtnLoading !== null}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '10px',
                          padding: '10px 14px', borderRadius: '9px',
                          background: loading ? 'rgba(0,212,255,0.1)' : 'rgba(255,255,255,0.03)',
                          border: `1px solid ${loading ? 'rgba(0,212,255,0.35)' : 'rgba(255,255,255,0.07)'}`,
                          color: 'var(--text-2)', cursor: quickBtnLoading !== null ? 'wait' : 'pointer',
                          textAlign: 'left' as const, width: '100%', transition: 'all 0.15s',
                          opacity: quickBtnLoading !== null && !loading ? 0.5 : 1,
                        }}
                      >
                        <span style={{ fontSize: '14px', opacity: 0.7 }}>{btn.icon}</span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-1)' }}>
                            {loading ? '⟳ Running…' : btn.label}
                          </div>
                          <div style={{ fontSize: '10px', color: 'var(--text-4)', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                            {btn.sub}
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Daily Summary */}
              <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '14px' }}>
                <div style={{
                  background: 'rgba(139,92,246,0.05)', border: '1px solid rgba(139,92,246,0.18)',
                  borderRadius: '14px', padding: '18px 20px',
                }}>
                  <div style={{ fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.14em', color: 'var(--violet)', fontWeight: 700, marginBottom: '12px' }}>
                    TODAY&apos;S SUMMARY
                  </div>
                  {dailySummary ? (
                    <>
                      <div style={{ fontSize: '13px', color: 'var(--text-2)', marginBottom: '12px', lineHeight: 1.5, fontStyle: 'italic' }}>
                        {dailySummary.summary_text}
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: '12px' }}>
                        {[
                          { label: 'Active', value: `${dailySummary.active_hours}h` },
                          { label: 'Captures', value: String(dailySummary.screenshot_count) },
                          { label: 'Workflows', value: String(dailySummary.workflow_periods) },
                        ].map(s => (
                          <div key={s.label} style={{ textAlign: 'center', padding: '8px 4px', background: 'rgba(255,255,255,0.03)', borderRadius: '8px' }}>
                            <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-1)' }}>{s.value}</div>
                            <div style={{ fontSize: '9px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)' }}>{s.label.toUpperCase()}</div>
                          </div>
                        ))}
                      </div>
                      {dailySummary.top_apps.length > 0 && (
                        <div style={{ marginBottom: '8px' }}>
                          <div style={{ fontSize: '10px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', marginBottom: '6px' }}>TOP APPS</div>
                          <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: '5px' }}>
                            {dailySummary.top_apps.slice(0, 4).map(a => (
                              <span key={a.app} className="chip chip-ghost" style={{ fontSize: '10px' }}>{a.app}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {dailySummary.key_activities.length > 0 && (
                        <div>
                          <div style={{ fontSize: '10px', color: 'var(--text-4)', fontFamily: 'var(--font-geist-mono, monospace)', marginBottom: '6px' }}>KEY ACTIVITIES</div>
                          <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '4px' }}>
                            {dailySummary.key_activities.slice(0, 4).map((act, i) => (
                              <div key={i} style={{ fontSize: '11px', color: 'var(--text-3)', paddingLeft: '8px', borderLeft: '2px solid rgba(139,92,246,0.3)' }}>
                                {act}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <div style={{ color: 'var(--text-4)', fontSize: '12px', textAlign: 'center', padding: '20px 0' }}>
                      No activity data yet. Start the screen watcher to begin capturing.
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Workflow Timeline */}
            {workflowPeriods.length > 0 && (
              <div style={{
                background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.07)',
                borderRadius: '14px', padding: '18px 20px',
              }}>
                <div style={{ fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.14em', color: 'var(--text-2)', fontWeight: 700, marginBottom: '14px' }}>
                  WORKFLOW TIMELINE — LAST 24H
                  <span style={{ marginLeft: '8px', fontWeight: 400, color: 'var(--text-4)' }}>{workflowPeriods.length} periods</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '8px' }}>
                  {workflowPeriods.slice(0, 10).map((p, i) => {
                    const wfColors: Record<string, string> = {
                      development: 'var(--cyan)', research: 'var(--violet)',
                      communication: 'var(--amber)', creative: 'var(--rose)',
                      learning: 'var(--emerald)', security: 'var(--rose)', other: 'var(--text-4)',
                    }
                    const col = wfColors[p.workflow_type] ?? 'var(--text-4)'
                    const startHm = new Date(p.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    return (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'center', gap: '12px',
                        padding: '8px 12px', borderRadius: '8px',
                        background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)',
                      }}>
                        <div style={{ width: '3px', height: '32px', borderRadius: '2px', background: col, flexShrink: 0 }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-1)' }}>{p.label}</div>
                          <div style={{ fontSize: '10px', color: 'var(--text-4)', marginTop: '2px' }}>
                            {startHm} · {p.duration_mins < 60 ? `${Math.round(p.duration_mins)}m` : `${(p.duration_mins/60).toFixed(1)}h`} · {p.dominant_app}
                          </div>
                        </div>
                        {p.active_tools.length > 0 && (
                          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' as const, maxWidth: '120px', justifyContent: 'flex-end' }}>
                            {p.active_tools.slice(0, 3).map(t => (
                              <span key={t} style={{
                                fontSize: '9px', padding: '2px 5px', borderRadius: '4px',
                                background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.2)',
                                color: 'var(--cyan)', fontFamily: 'var(--font-geist-mono, monospace)',
                              }}>{t}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Autonomous Insights panel */}
            <div style={{
              background: 'rgba(16,217,132,0.03)', border: '1px solid rgba(16,217,132,0.12)',
              borderRadius: '14px', padding: '18px 20px',
            }}>
              <div style={{ fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.14em', color: 'var(--emerald)', fontWeight: 700, marginBottom: '14px' }}>
                AUTONOMOUS INSIGHTS
                <span style={{ marginLeft: '8px', fontSize: '9px', fontWeight: 400, color: 'var(--text-4)' }}>grounded · no hallucination</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '8px' }}>
                {dailySummary && dailySummary.active_hours > 0 ? (
                  <>
                    {dailySummary.active_hours > 0 && (
                      <div style={{ fontSize: '12px', color: 'var(--text-2)', padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', borderLeft: '3px solid var(--emerald)' }}>
                        {dailySummary.screenshot_count > 0
                          ? `Active for ${dailySummary.active_hours}h — ${dailySummary.screenshot_count} screen captures.`
                          : `Active for ~${dailySummary.active_hours}h based on recorded memories.`}
                      </div>
                    )}
                    {dailySummary.top_apps[0] && (
                      <div style={{ fontSize: '12px', color: 'var(--text-2)', padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', borderLeft: '3px solid var(--cyan)' }}>
                        Most time spent in {dailySummary.top_apps[0].app}.
                      </div>
                    )}
                    {Object.keys(dailySummary.workflow_breakdown).length > 0 && (() => {
                      const topWf = Object.entries(dailySummary.workflow_breakdown).sort((a,b) => b[1]-a[1])[0]
                      return topWf ? (
                        <div style={{ fontSize: '12px', color: 'var(--text-2)', padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', borderLeft: '3px solid var(--violet)' }}>
                          Primary workflow: <strong style={{ color: 'var(--violet)' }}>{topWf[0]}</strong> ({Math.round(topWf[1])}m).
                        </div>
                      ) : null
                    })()}
                    {dailySummary.top_tools[0] && (
                      <div style={{ fontSize: '12px', color: 'var(--text-2)', padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', borderLeft: '3px solid var(--amber)' }}>
                        Tools detected: {dailySummary.top_tools.slice(0,3).map(t => t.tool).join(', ')}.
                      </div>
                    )}
                  </>
                ) : (
                  <div style={{ color: 'var(--text-4)', fontSize: '12px', textAlign: 'center', padding: '16px 0' }}>
                    Start the screen watcher to generate insights from your activity.
                  </div>
                )}
              </div>
            </div>

          {/* ── Brain Chat Panel (Phase 18) ── */}
          <div style={{
            background: 'rgba(139,92,246,0.03)',
            border: '1px solid rgba(139,92,246,0.18)',
            borderRadius: '14px',
            padding: '18px 20px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <span style={{ fontSize: '13px', fontFamily: 'var(--font-geist-mono, monospace)', letterSpacing: '0.14em', color: 'var(--violet)', fontWeight: 700 }}>
                ◈ BRAIN CHAT
              </span>
              {brainStatus && (
                <span style={{
                  fontSize: '9px', padding: '2px 7px', borderRadius: '4px',
                  background: brainStatus.llm_active
                    ? 'rgba(139,92,246,0.12)'
                    : brainStatus.quota_limited
                    ? 'rgba(234,179,8,0.08)'
                    : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${brainStatus.llm_active
                    ? 'rgba(139,92,246,0.3)'
                    : brainStatus.quota_limited
                    ? 'rgba(234,179,8,0.25)'
                    : 'rgba(255,255,255,0.08)'}`,
                  color: brainStatus.llm_active
                    ? 'var(--violet)'
                    : brainStatus.quota_limited
                    ? '#eab308'
                    : 'var(--text-4)',
                  fontFamily: 'var(--font-geist-mono, monospace)',
                }}>
                  {brainStatus.quota_limited
                    ? `Gemini limited · local fallback active${brainStatus.retry_after_seconds ? ` · retry ${brainStatus.retry_after_seconds}s` : ''}`
                    : `${brainStatus.brain_provider} · ${brainStatus.mode}${brainStatus.fallback_used ? ' (fallback)' : ''}`}
                </span>
              )}
              <button onClick={fetchBrainStatus} className="btn-ghost" style={{ fontSize: '9px', padding: '2px 8px', marginLeft: 'auto' }}>↺ Status</button>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-3)', marginBottom: '10px', lineHeight: 1.5 }}>
              Ask anything — what you worked on, what you saw, who you spoke to.
            </div>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
              <input
                value={brainChatMsg}
                onChange={e => setBrainChatMsg(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendBrainChat()}
                placeholder="Ask your memory brain…"
                style={{ flex: 1, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: 'var(--text-1)', padding: '8px 12px', fontSize: '13px', fontFamily: 'var(--font-geist-mono, monospace)' }}
              />
              <button
                onClick={sendBrainChat}
                disabled={brainChatLoading || !brainChatMsg.trim()}
                style={{ padding: '8px 18px', borderRadius: '8px', fontSize: '11px', fontFamily: 'var(--font-geist-mono, monospace)', fontWeight: 700, border: '1px solid rgba(139,92,246,0.4)', color: 'var(--violet)', background: 'rgba(139,92,246,0.1)', cursor: brainChatLoading || !brainChatMsg.trim() ? 'default' : 'pointer', opacity: !brainChatMsg.trim() ? 0.4 : 1 }}
              >
                {brainChatLoading ? '⟳' : 'Ask'}
              </button>
            </div>
            {brainChatAnswer && (
              <div style={{ padding: '12px 14px', background: 'rgba(139,92,246,0.05)', border: '1px solid rgba(139,92,246,0.2)', borderRadius: '8px', fontSize: '13px', color: 'var(--text-2)', lineHeight: 1.7, fontFamily: 'var(--font-geist-mono, monospace)' }}>
                {brainChatAnswer}
              </div>
            )}
            {brainChatNotice && (
              <div style={{ marginTop: '8px', padding: '8px 12px', background: 'rgba(234,179,8,0.06)', border: '1px solid rgba(234,179,8,0.22)', borderRadius: '6px', fontSize: '11px', color: '#eab308', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                {brainChatNotice}
              </div>
            )}
            {brainChatError && (
              <div style={{ marginTop: '8px', padding: '8px 12px', background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.22)', borderRadius: '6px', fontSize: '11px', color: '#ef4444', fontFamily: 'var(--font-geist-mono, monospace)' }}>
                {brainChatError}
              </div>
            )}
          </div>

          </div>
        )}

      </main>

      {/* ── Replay overlay ── */}
      {activeReplay && (
        <ReplayPlayer data={activeReplay} onClose={() => setActiveReplay(null)} />
      )}

      {/* ── PDF Chat panel ── */}
      {pdfChatTarget !== null && (
        <>
          {/* Dim backdrop — clicking it closes the panel */}
          <div
            onClick={() => setPdfChatTarget(null)}
            style={{
              position:   'fixed',
              inset:      0,
              background: 'rgba(0,0,0,0.45)',
              zIndex:     89,
            }}
          />
          <PdfChatPanel
            target={pdfChatTarget}
            onClose={() => setPdfChatTarget(null)}
          />
        </>
      )}

      </div>{/* end content layer */}
    </div>
  )
}
