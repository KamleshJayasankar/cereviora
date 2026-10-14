import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getHealth, getTaskCounts, getTasks, getTaskHistory } from '../services/api'
import type { ExecutionRecord, HealthResponse, Task, TaskCounts, WorkflowNode, WorkflowNodeId, WorkflowNodeStatus } from '../types'
import './Dashboard.css'

const WorkflowScene = lazy(() => import('../components/WorkflowScene'))

const NODE_INFO = [
  { id: 'interpret', label: 'Interpret', icon: '◎', description: 'Turn a request into clear, structured intent.', color: '#38d9ff' },
  { id: 'plan', label: 'Plan', icon: '◈', description: 'Build an ordered task plan that can be reviewed.', color: '#9d83ff' },
  { id: 'approve', label: 'Approve', icon: '◉', description: 'Require explicit approval before protected operations.', color: '#ffbd59' },
  { id: 'execute', label: 'Execute', icon: '▶', description: 'Run only the application’s allowlisted operations.', color: '#31d69a' },
  { id: 'verify', label: 'Verify', icon: '✓', description: 'Check saved results against actual database state.', color: '#55b7ff' },
  { id: 'store', label: 'Store', icon: '⊞', description: 'Keep task results and an audit trail in persistent storage.', color: '#c6a0ff' },
] as const

type Activity = { record: ExecutionRecord; taskTitle: string }

function nodeStatus(value: WorkflowNodeStatus): string {
  return ({ idle: 'Standby', awaiting: 'Awaiting action', running: 'In progress', success: 'Operational', failed: 'Attention needed' })[value]
}

function makeNodes(tasks: Task[], history: Activity[]): WorkflowNode[] {
  const running = tasks.some(task => task.status === 'RUNNING')
  const failed = tasks.some(task => task.status === 'FAILED')
  const waiting = tasks.some(task => task.status === 'AWAITING_APPROVAL')
  const success = tasks.some(task => task.status === 'SUCCEEDED')
  const hasWork = tasks.length > 0
  const records = history.map(item => item.record)
  const saved = records.some(record => record.step_id && record.output_summary?.startsWith('Saved task artifact'))
  const verified = records.some(record => record.event_type === 'STEP' && record.verified)
  const stageStatus = (active: boolean): WorkflowNodeStatus => !hasWork ? 'idle' : active ? (failed ? 'failed' : running ? 'running' : waiting ? 'awaiting' : 'success') : 'idle'
  const values: Record<WorkflowNodeId, { status: WorkflowNodeStatus; value: string; detail: string }> = {
    interpret: { status: stageStatus(tasks.some(task => task.steps.some(step => step.step_type === 'interpret'))), value: `${tasks.length} tasks`, detail: 'Requests enter as tasks and become structured work when a plan is created.' },
    plan: { status: stageStatus(tasks.some(task => task.steps.length > 0)), value: `${tasks.filter(task => task.steps.length > 0).length} planned`, detail: `${tasks.filter(task => task.status === 'AWAITING_APPROVAL').length} task(s) are currently awaiting review.` },
    approve: { status: !hasWork ? 'idle' : waiting ? 'awaiting' : success || failed ? 'success' : 'idle', value: `${tasks.filter(task => task.approved_at).length} approved`, detail: `${tasks.filter(task => task.status === 'AWAITING_APPROVAL' && !task.approved_at).length} plan(s) still need approval.` },
    execute: { status: !hasWork ? 'idle' : running ? 'running' : failed ? 'failed' : success ? 'success' : waiting ? 'awaiting' : 'idle', value: `${tasks.filter(task => task.status === 'RUNNING' || task.status === 'SUCCEEDED').length} active or complete`, detail: `${tasks.filter(task => task.status === 'FAILED').length} task(s) have an execution failure.` },
    verify: { status: verified ? 'success' : failed ? 'failed' : running ? 'running' : 'idle', value: `${records.filter(record => record.event_type === 'STEP' && record.verified).length} verified`, detail: 'Verification is based on recorded database checks from execution history.' },
    store: { status: saved ? 'success' : hasWork ? 'awaiting' : 'idle', value: `${tasks.length} task records`, detail: `${records.length} approval and execution audit event(s) loaded.` },
  }
  return NODE_INFO.map(node => ({ ...node, status: values[node.id].status, statusLabel: nodeStatus(values[node.id].status), value: values[node.id].value, detail: values[node.id].detail }))
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false)
  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    if (!media) return
    const update = () => setReduced(media.matches)
    media.addEventListener?.('change', update)
    return () => media.removeEventListener?.('change', update)
  }, [])
  return reduced
}

export default function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [counts, setCounts] = useState<TaskCounts | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [activity, setActivity] = useState<Activity[]>([])
  const [loading, setLoading] = useState(true)
  const [dataError, setDataError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<WorkflowNodeId>('interpret')
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const navigate = useNavigate()
  const reducedMotion = useReducedMotion()

  const refresh = useCallback(async () => {
    setDataError(null)
    const [countResult, taskResult] = await Promise.allSettled([getTaskCounts(), getTasks()])
    if (countResult.status === 'fulfilled') setCounts(countResult.value)
    if (taskResult.status === 'fulfilled') {
      setTasks(taskResult.value.tasks)
      const recentTasks = taskResult.value.tasks.slice(0, 8)
      const histories = await Promise.allSettled(recentTasks.map(task => getTaskHistory(task.id)))
      const nextActivity: Activity[] = []
      let historyFailed = false
      histories.forEach((result, index) => {
        if (result.status === 'fulfilled') result.value.forEach(record => nextActivity.push({ record, taskTitle: recentTasks[index].title }))
        else historyFailed = true
      })
      nextActivity.sort((a, b) => b.record.created_at.localeCompare(a.record.created_at))
      setActivity(nextActivity.slice(0, 8))
      if (historyFailed) setDataError('Some execution history could not be loaded.')
    }
    if (countResult.status === 'rejected' || taskResult.status === 'rejected') {
      setDataError('Could not refresh task data. Showing the most recently loaded information.')
    }
    if (countResult.status === 'fulfilled' || taskResult.status === 'fulfilled') setLastUpdated(new Date())
    setLoading(false)
  }, [])

  useEffect(() => {
    let mounted = true
    getHealth().then(data => { if (mounted) { setHealth(data); setHealthError(null) } }).catch(error => { if (mounted) setHealthError(error instanceof Error ? error.message : 'Backend unreachable') })
    void refresh()
    const timer = window.setInterval(() => { void refresh() }, 20000)
    const onFocus = () => { void refresh() }
    window.addEventListener('focus', onFocus)
    return () => { mounted = false; window.clearInterval(timer); window.removeEventListener('focus', onFocus) }
  }, [refresh])

  const nodes = useMemo(() => makeNodes(tasks, activity), [tasks, activity])
  const selected = nodes.find(node => node.id === selectedNode) ?? nodes[0]
  const taskTitleById = useMemo(() => new Map(tasks.map(task => [task.id, task.title])), [tasks])

  return <div className="dashboard">
    <section className="dashboard-hero">
      <div className="hero-content">
        <div className="hero-badge">INTELLIGENCE PLATFORM · LIVE SYSTEM VIEW</div>
        <h1 className="hero-title">CEREVIORA<span className="hero-subtitle">Command Center</span></h1>
        <p className="hero-description">A live view of planned, approved and verified work across your task system.</p>
      </div>
      <div className={`api-status glass-card ${healthError ? 'offline' : health ? 'online' : 'loading'}`} role="status">
        <div className="status-dot" />
        <div className="status-info"><span className="status-label">{healthError ? 'API Offline' : health ? 'API Online' : 'Connecting…'}</span>
          <span className="status-detail">{health ? `${health.app} v${health.version}` : healthError || 'Checking backend connection'}</span>
        </div>
      </div>
    </section>

    <section className="stats-row container" aria-label="Live task totals">
      {[
        { label: 'Total Tasks', value: counts?.total, icon: '◈', color: 'var(--color-accent)' },
        { label: 'Awaiting Approval', value: counts?.AWAITING_APPROVAL, icon: '◉', color: '#f59e0b' },
        { label: 'Running', value: counts?.RUNNING, icon: '▶', color: '#10b981' },
        { label: 'Completed', value: counts?.SUCCEEDED, icon: '✓', color: '#10b981' },
        { label: 'Failed', value: counts?.FAILED, icon: '✕', color: '#ef4444' },
      ].map(stat => <div key={stat.label} className="stat-card glass-card"><span className="stat-icon" style={{ color: stat.color }}>{stat.icon}</span><span className="stat-value">{loading ? '…' : stat.value ?? '—'}</span><span className="stat-label">{stat.label}</span></div>)}
    </section>

    <section className="workflow-section container">
      <div className="section-heading-row workflow-heading-row">
        <div className="section-heading-text">
          <h2>Interactive Workflow</h2>
          <p className="section-desc">Select a node to inspect live state from your tasks and audit trail.</p>
        </div>
        <button className="btn btn-ghost dashboard-refresh" onClick={() => void refresh()} disabled={loading} aria-label="Refresh dashboard data">↻ Refresh</button>
      </div>
      {dataError && <div className="dashboard-notice" role="alert">{dataError}</div>}
      {loading && <div className="dashboard-loading" role="status">Loading task state and execution history…</div>}
      {!loading && !dataError && tasks.length === 0 && <div className="dashboard-notice">No tasks yet. Create a task to see its state move through the workflow.</div>}
      <div className="workflow-scene-frame"><Suspense fallback={<div className="scene-fallback">Loading intelligence visualization…</div>}><WorkflowScene nodes={nodes} selectedNode={selectedNode} onSelect={setSelectedNode} reducedMotion={reducedMotion} /></Suspense><div className="scene-core-caption" aria-hidden="true"><span>CORE</span><small>INTELLIGENCE ENGINE</small></div></div>
      <div className="workflow-controls" role="group" aria-label="Select workflow stage">
        {nodes.map((node, index) => <button key={node.id} className={`workflow-control ${selectedNode === node.id ? 'selected' : ''}`} onClick={() => setSelectedNode(node.id)} aria-pressed={selectedNode === node.id} style={{ '--node-color': node.color } as React.CSSProperties}>
          <span className={`workflow-control-dot workflow-control-dot--${node.status}`} /><span className="workflow-control-number">0{index + 1}</span><span className="workflow-control-name">{node.label}</span><span className="workflow-control-value">{node.value}</span>
        </button>)}
      </div>
      <div className="node-detail glass-card" role="region" aria-live="polite" aria-label={`${selected.label} workflow details`}>
        <div className="node-detail-header" style={{ color: selected.color }}><span className="node-detail-icon">{selected.icon}</span><div><h3>{selected.label}</h3><span className={`workflow-state workflow-state--${selected.status}`}>{selected.statusLabel}</span></div></div>
        <p>{selected.description} {selected.detail}</p>
        <strong className="node-detail-value">{selected.value}</strong>
        <button className="btn btn-primary" onClick={() => navigate('/tasks')}>Open Tasks</button>
      </div>
    </section>

    <section className="quick-actions container">
      <div className="section-heading-row"><div><h2>Command Shortcuts</h2><p className="section-desc">Continue work in the task workspace.</p></div></div>
      <div className="action-grid">
        <button className="action-card glass-card" onClick={() => navigate('/tasks')}><span className="action-icon" style={{ color: 'var(--color-accent)' }}>＋</span><span className="action-label">Create or Plan</span><span className="action-desc">Create a task or generate its plan</span></button>
        <button className="action-card glass-card" onClick={() => navigate('/tasks')}><span className="action-icon" style={{ color: '#f59e0b' }}>◉</span><span className="action-label">Review Approval</span><span className="action-desc">{counts?.AWAITING_APPROVAL ?? '—'} plan(s) awaiting review</span></button>
        <button className="action-card glass-card" onClick={() => document.getElementById('recent-audit')?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' })}><span className="action-icon" style={{ color: '#9d83ff' }}>⌁</span><span className="action-label">Inspect Audit</span><span className="action-desc">View latest execution and verification records</span></button>
      </div>
    </section>

    <section className="activity-section container" id="recent-audit">
      <div className="glass-card activity-panel">
        <div className="section-heading-row activity-heading"><div><h2>Recent Audit Activity</h2><p className="section-desc">Persistent approval and execution events from the backend.</p></div><span className="activity-updated">{lastUpdated ? `Updated ${formatTime(lastUpdated.toISOString())}` : ''}</span></div>
        {loading ? <div className="dashboard-loading">Loading execution history…</div> : activity.length === 0 ? <div className="empty-state"><span className="empty-icon">◈</span><p>{tasks.length ? 'No execution attempts recorded yet.' : 'No tasks yet. Create your first task to get started.'}</p><p className="empty-sub">Approval records, execution outcomes and database verification appear here.</p></div> : <ol className="audit-list">
          {activity.map(({ record }) => <li className="audit-item" key={record.id}>
            <span className={`audit-status audit-status--${record.status.toLowerCase()}`} aria-hidden="true" />
            <div className="audit-main"><div className="audit-topline"><strong>{record.event_type === 'APPROVAL' ? 'Plan approved' : `${record.status === 'FAILED' ? 'Step failed' : 'Step execution'}${record.attempt > 1 ? ` · attempt ${record.attempt}` : ''}`}</strong><time dateTime={record.created_at}>{formatTime(record.created_at)}</time></div>
              <span className="audit-task">{taskTitleById.get(record.task_id) ?? 'Task'}</span>
              {record.output_summary && <p>{record.output_summary}</p>}{record.error_details && <p className="audit-error">{record.error_details}</p>}
              {record.verification_result && <p className={record.verified ? 'audit-verified' : 'audit-error'}>{record.verified ? 'Verified · ' : 'Not verified · '}{record.verification_result}</p>}
            </div>
          </li>)}
        </ol>}
      </div>
    </section>
  </div>
}
