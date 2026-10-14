/**
 * CEREVIORA — Tasks Page
 *
 * This page is the full task management UI. It:
 * 1. Loads and displays all tasks from the real backend API.
 * 2. Shows a task creation form that POSTs to /tasks.
 * 3. Lets users delete tasks (with confirmation).
 * 4. Updates the list after every create/delete without a page refresh.
 * 5. Shows real status badges, timestamps and descriptions.
 *
 * Key React concepts used here:
 *
 * useState  — holds data that changes over time (task list, form values,
 *             loading state, error messages). When state changes, React
 *             re-renders only the affected parts of the page.
 *
 * useEffect — runs a side-effect (fetching data) after the component
 *             appears on screen. The empty [] dependency array means
 *             "run once on mount, not on every render".
 *
 * async/await — fetchTasks() is async because it makes a network request.
 *               We await the result so the rest of the function runs only
 *               after the data arrives.
 */
import { useEffect, useState, FormEvent } from 'react'
import { getTasks, createTask, deleteTask, planTask, approveTask, executeTask, getTaskHistory } from '../services/api'
import type { Task, TaskStatus, StepStatus, ExecutionRecord } from '../types'
import './Tasks.css'

// ── Status badge helper ────────────────────────────────────────────────────────
const STATUS_CSS: Record<TaskStatus, string> = {
  PENDING:           'badge badge--pending',
  AWAITING_APPROVAL: 'badge badge--awaiting',
  RUNNING:           'badge badge--running',
  SUCCEEDED:         'badge badge--succeeded',
  FAILED:            'badge badge--failed',
}

const STATUS_LABELS: Record<TaskStatus, string> = {
  PENDING:           'Pending',
  AWAITING_APPROVAL: 'Awaiting Approval',
  RUNNING:           'Running',
  SUCCEEDED:         'Succeeded',
  FAILED:            'Failed',
}

const STEP_TYPE_ICONS: Record<string, string> = {
  interpret: '◎',
  research:  '🔍',
  generate:   '◈',
  extract:   '⚡',
  save:      '⊞',
  verify:    '✓',
  general:   '⚙',
}

const STEP_STATUS_LABELS: Record<StepStatus, string> = {
  PENDING:   'Pending',
  RUNNING:   'Running',
  SUCCEEDED: 'Succeeded',
  FAILED:    'Failed',
  SKIPPED:   'Skipped',
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function Tasks() {
  // ── State: task list ──────────────────────────────────────────────────────
  const [tasks, setTasks]         = useState<Task[]>([])
  const [total, setTotal]         = useState(0)
  const [loading, setLoading]     = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  // ── State: create form ────────────────────────────────────────────────────
  const [showForm, setShowForm]     = useState(false)
  const [title, setTitle]           = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating]     = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  // ── State: delete ─────────────────────────────────────────────────────────
  const [deletingId, setDeletingId] = useState<string | null>(null)

  // ── State: planning & expansion ───────────────────────────────────────────
  const [planningId, setPlanningId] = useState<string | null>(null)
  const [expandedTaskIds, setExpandedTaskIds] = useState<Set<string>>(new Set())
  const [historyByTask, setHistoryByTask] = useState<Record<string, ExecutionRecord[]>>({})
  const [busyAction, setBusyAction] = useState<string | null>(null)

  function toggleExpand(id: string) {
    setExpandedTaskIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // ── Plan handler ──────────────────────────────────────────────────────────
  async function handlePlan(id: string) {
    setPlanningId(id)
    try {
      const updated = await planTask(id)
      setTasks(prev => prev.map(t => t.id === id ? updated : t))
      // Automatically expand newly planned task so user sees the 5 steps immediately
      setExpandedTaskIds(prev => new Set(prev).add(id))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to generate plan')
    } finally {
      setPlanningId(null)
    }
  }

  async function handleTaskAction(id: string, action: 'approve' | 'execute') {
    setBusyAction(`${action}:${id}`)
    try {
      const updated = action === 'approve' ? await approveTask(id) : await executeTask(id)
      setTasks(prev => prev.map(t => t.id === id ? updated : t))
      setExpandedTaskIds(prev => new Set(prev).add(id))
      const history = await getTaskHistory(id)
      setHistoryByTask(prev => ({ ...prev, [id]: history }))
    } catch (err) {
      alert(err instanceof Error ? err.message : `Failed to ${action} task`)
    } finally {
      setBusyAction(null)
    }
  }

  async function handleHistory(id: string) {
    try {
      const history = await getTaskHistory(id)
      setHistoryByTask(prev => ({ ...prev, [id]: history }))
      setExpandedTaskIds(prev => new Set(prev).add(id))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to load execution history')
    }
  }

  // ── Fetch tasks on mount ──────────────────────────────────────────────────
  async function loadTasks() {
    setLoading(true)
    setListError(null)
    try {
      const data = await getTasks()
      setTasks(data.tasks)
      setTotal(data.total)
    } catch (err) {
      setListError(err instanceof Error ? err.message : 'Failed to load tasks')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadTasks() }, [])

  // ── Create handler ────────────────────────────────────────────────────────
  async function handleCreate(e: FormEvent) {
    e.preventDefault()  // prevent the browser from reloading the page
    if (!title.trim()) return

    setCreating(true)
    setCreateError(null)
    try {
      const newTask = await createTask({ title: title.trim(), description: description.trim() })
      // Prepend new task to the top of the list (no refetch needed)
      setTasks(prev => [newTask, ...prev])
      setTotal(prev => prev + 1)
      setTitle('')
      setDescription('')
      setShowForm(false)
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create task')
    } finally {
      setCreating(false)
    }
  }

  // ── Delete handler ────────────────────────────────────────────────────────
  async function handleDelete(id: string) {
    if (!confirm('Delete this task? This action cannot be undone.')) return
    setDeletingId(id)
    try {
      await deleteTask(id)
      setTasks(prev => prev.filter(t => t.id !== id))
      setTotal(prev => prev - 1)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete task')
    } finally {
      setDeletingId(null)
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="tasks-page">

      {/* ── Page header ──────────────────────────────────────────────────── */}
      <div className="tasks-header container">
        <div className="tasks-title-group">
          <h1>Tasks</h1>
          <span className="tasks-count-badge">{total}</span>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => { setShowForm(!showForm); setCreateError(null) }}
          aria-expanded={showForm}
        >
          {showForm ? '✕ Cancel' : '+ New Task'}
        </button>
      </div>

      {/* ── Create form ──────────────────────────────────────────────────── */}
      {showForm && (
        <div className="container">
          <form className="create-form glass-card" onSubmit={handleCreate} noValidate>
            <h2>Create Task</h2>

            <div className="form-group">
              <label htmlFor="task-title">Title <span aria-hidden="true">*</span></label>
              <input
                id="task-title"
                type="text"
                className="form-input"
                placeholder="What needs to be done?"
                value={title}
                onChange={e => setTitle(e.target.value)}
                maxLength={200}
                required
                autoFocus
              />
              <span className="char-count">{title.length}/200</span>
            </div>

            <div className="form-group">
              <label htmlFor="task-desc">Description <span className="optional">(optional)</span></label>
              <textarea
                id="task-desc"
                className="form-input form-textarea"
                placeholder="Add details, context or acceptance criteria…"
                value={description}
                onChange={e => setDescription(e.target.value)}
                maxLength={5000}
                rows={4}
              />
            </div>

            {createError && (
              <div className="form-error" role="alert">{createError}</div>
            )}

            <div className="form-actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={creating || !title.trim()}
              >
                {creating ? 'Creating…' : 'Create Task'}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => { setShowForm(false); setTitle(''); setDescription('') }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ── Task list ────────────────────────────────────────────────────── */}
      <div className="container">
        {loading && (
          <div className="task-loading">
            <div className="loading-spinner" aria-label="Loading tasks…" />
            <span>Loading tasks…</span>
          </div>
        )}

        {listError && (
          <div className="task-list-error glass-card" role="alert">
            <span>⚠ {listError}</span>
            <button className="btn btn-ghost" onClick={loadTasks}>Retry</button>
          </div>
        )}

        {!loading && !listError && tasks.length === 0 && (
          <div className="empty-state glass-card">
            <span className="empty-icon">◈</span>
            <p>No tasks yet.</p>
            <p className="empty-sub">Click <strong>+ New Task</strong> to create your first one.</p>
          </div>
        )}

        {!loading && tasks.length > 0 && (
          <ul className="task-list" role="list" aria-label="Task list">
            {tasks.map(task => {
              const isExpanded = expandedTaskIds.has(task.id)
              const hasSteps = task.steps && task.steps.length > 0
              const isPlanning = planningId === task.id

              return (
                <li key={task.id} className="task-card glass-card" role="listitem">

                  <div className="task-card-main">
                    <div className="task-card-header">
                      <span className={STATUS_CSS[task.status]} aria-label={`Status: ${STATUS_LABELS[task.status]}`}>
                        {STATUS_LABELS[task.status]}
                      </span>
                      <span className="task-card-id" title={task.id}>
                        #{task.id.slice(0, 8)}
                      </span>
                      {hasSteps && (
                        <span className="task-steps-indicator" onClick={() => toggleExpand(task.id)}>
                          {task.steps.length} Steps {isExpanded ? '▲' : '▼'}
                        </span>
                      )}
                    </div>

                    <h3 className="task-card-title">{task.title}</h3>

                    {task.description && (
                      <p className="task-card-desc">{task.description}</p>
                    )}

                    <div className="task-card-meta">
                      <span title={`Created: ${task.created_at}`}>
                        Created {formatDate(task.created_at)}
                      </span>
                      {task.updated_at !== task.created_at && (
                        <span title={`Updated: ${task.updated_at}`}>
                          · Updated {formatDate(task.updated_at)}
                        </span>
                      )}
                    </div>

                    {/* ── Collapsible Structured Steps Pipeline ── */}
                    {hasSteps && isExpanded && (
                      <div className="task-steps-container">
                        <div className="task-steps-header">
                          <span className="steps-header-title">EXECUTION PLAN</span>
                          <span className="steps-header-badge">POLICY VALIDATED</span>
                        </div>
                        <ol className="step-pipeline" role="list" aria-label="Task execution steps">
                          {task.steps.map(step => (
                            <li key={step.id} className={`step-item step-item--${step.status.toLowerCase()}`}>
                              <div className="step-node-col">
                                <span className="step-number">{step.step_number}</span>
                                <div className="step-connector" />
                              </div>
                              <div className="step-content">
                                <div className="step-top-line">
                                  <span className="step-type-pill">
                                    <span className="step-type-icon">{STEP_TYPE_ICONS[step.step_type] || '⚙'}</span>
                                    {step.step_type}
                                  </span>
                                  <span className={`step-status-tag step-status-tag--${step.status.toLowerCase()}`}>
                                    {STEP_STATUS_LABELS[step.status as StepStatus] || step.status}
                                  </span>
                                </div>
                                <h4 className="step-title">{step.title}</h4>
                                {step.description && (
                                  <p className="step-desc">{step.description}</p>
                                )}
                              </div>
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}
                    {isExpanded && historyByTask[task.id] && (
                      <section className="task-steps-container" aria-label="Execution history">
                        <div className="task-steps-header"><span className="steps-header-title">APPROVAL &amp; EXECUTION HISTORY</span></div>
                        {historyByTask[task.id].length === 0 ? <p>No execution attempts recorded.</p> : (
                          <ol className="step-pipeline">
                            {historyByTask[task.id].map(record => (
                              <li className="step-item" key={record.id}><div className="step-content">
                                <div className="step-top-line"><strong>{record.event_type}{record.step_id ? ` · attempt ${record.attempt}` : ''}</strong><span>{record.status} · {formatDate(record.created_at)}</span></div>
                                {record.output_summary && <p className="step-desc">{record.output_summary}</p>}
                                {record.verification_result && <p className="step-desc">Verification: {record.verification_result}</p>}
                                {record.error_details && <p className="form-error">{record.error_details}</p>}
                              </div></li>
                            ))}
                          </ol>
                        )}
                      </section>
                    )}
                  </div>

                  <div className="task-card-actions">
                    {task.status === 'PENDING' && (
                      <button
                        className="btn btn-primary btn-plan"
                        onClick={() => handlePlan(task.id)}
                        disabled={isPlanning}
                        aria-label={`Generate plan for task: ${task.title}`}
                      >
                        {isPlanning ? (
                          <>
                            <span className="loading-spinner-sm" />
                            Planning…
                          </>
                        ) : (
                          '⚡ Plan Task'
                        )}
                      </button>
                    )}

                    {hasSteps && (
                      <button
                        className="btn btn-ghost"
                        onClick={() => toggleExpand(task.id)}
                        aria-expanded={isExpanded}
                        aria-label="Toggle plan view"
                      >
                        {isExpanded ? 'Hide Steps' : `View Steps (${task.steps.length})`}
                      </button>
                    )}

                    {task.status === 'AWAITING_APPROVAL' && !task.approved_at && (
                      <button className="btn btn-primary" onClick={() => handleTaskAction(task.id, 'approve')} disabled={busyAction !== null}>
                        {busyAction === `approve:${task.id}` ? 'Approving…' : 'Approve Plan'}
                      </button>
                    )}
                    {task.status === 'AWAITING_APPROVAL' && task.approved_at && (
                      <button className="btn btn-primary" onClick={() => handleTaskAction(task.id, 'execute')} disabled={busyAction !== null}>
                        {busyAction === `execute:${task.id}` ? 'Executing…' : 'Run Approved Plan'}
                      </button>
                    )}
                    {(task.approved_at || task.status === 'SUCCEEDED' || task.status === 'FAILED') && (
                      <button className="btn btn-ghost" onClick={() => handleHistory(task.id)}>Execution History</button>
                    )}

                    {(task.status === 'AWAITING_APPROVAL' || task.status === 'FAILED') && (
                      <button
                        className="btn btn-ghost"
                        onClick={() => handlePlan(task.id)}
                        disabled={isPlanning}
                        title="Regenerate plan with fresh steps"
                        aria-label={`Replan task: ${task.title}`}
                      >
                        {isPlanning ? 'Planning…' : '↺ Replan'}
                      </button>
                    )}

                    <button
                      className="btn btn-danger"
                      onClick={() => handleDelete(task.id)}
                      disabled={deletingId === task.id || isPlanning}
                      aria-label={`Delete task: ${task.title}`}
                    >
                      {deletingId === task.id ? '…' : 'Delete'}
                    </button>
                  </div>

                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
