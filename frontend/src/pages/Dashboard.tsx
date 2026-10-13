/**
 * CEREVIORA — Dashboard Page (Day 1 milestone)
 *
 * This is the landing page. For Day 1, it:
 * 1. Calls the backend /health endpoint to prove frontend ↔ backend comms work.
 * 2. Shows the CEREVIORA system overview with status indicators.
 * 3. Provides a workflow node diagram (2D fallback — 3D added Day 5).
 *
 * The useEffect hook runs once when the component mounts (appears on screen).
 * It's like asking "fetch the data when the page loads".
 */
import { useEffect, useState } from 'react'
import { getHealth } from '../services/api'
import type { HealthResponse } from '../types'
import './Dashboard.css'

// ── Workflow node data (placeholder counts until real tasks exist) ──────────
const WORKFLOW_NODES = [
  { id: 'interpret', label: 'Interpret', icon: '◎', description: 'Parse natural language requests into structured intent', color: '#00d4ff' },
  { id: 'plan',      label: 'Plan',      icon: '◈', description: 'Generate ordered, validated execution steps',          color: '#7c3aed' },
  { id: 'approve',   label: 'Approve',   icon: '◉', description: 'Require explicit human sign-off before protected ops', color: '#f59e0b' },
  { id: 'execute',   label: 'Execute',   icon: '▶',  description: 'Run allowlisted operations safely',                   color: '#10b981' },
  { id: 'verify',    label: 'Verify',    icon: '✓',  description: 'Confirm actual outcome matches expected state',       color: '#ec4899' },
  { id: 'store',     label: 'Store',     icon: '⊞',  description: 'Persist results and audit records to SQLite',         color: '#64748b' },
] as const

type NodeId = typeof WORKFLOW_NODES[number]['id']

export default function Dashboard() {
  // State: what did the health check return?
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)

  // State: which workflow node is the user inspecting?
  const [selectedNode, setSelectedNode] = useState<NodeId | null>(null)

  // ── Fetch health on mount ──────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false  // prevent state updates if component unmounts

    async function checkHealth() {
      try {
        const data = await getHealth()
        if (!cancelled) {
          setHealth(data)
          setHealthError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setHealthError(err instanceof Error ? err.message : 'Backend unreachable')
        }
      } finally {
        if (!cancelled) setHealthLoading(false)
      }
    }

    checkHealth()
    return () => { cancelled = true }  // cleanup on unmount
  }, [])

  const selectedNodeData = WORKFLOW_NODES.find(n => n.id === selectedNode)

  return (
    <div className="dashboard">

      {/* ── Hero banner ──────────────────────────────────────────────────── */}
      <section className="dashboard-hero">
        <div className="hero-content">
          <div className="hero-badge">INTELLIGENCE PLATFORM</div>
          <h1 className="hero-title">
            CEREVIORA
            <span className="hero-subtitle">Command Center</span>
          </h1>
          <p className="hero-description">
            Transform requests into structured, verified actions. Every step planned, approved, executed and confirmed.
          </p>
        </div>

        {/* API Status Indicator */}
        <div className={`api-status glass-card ${healthLoading ? 'loading' : health ? 'online' : 'offline'}`}>
          <div className="status-dot" />
          <div className="status-info">
            <span className="status-label">
              {healthLoading ? 'Connecting…' : health ? 'API Online' : 'API Offline'}
            </span>
            {health && (
              <span className="status-detail">{health.app} v{health.version}</span>
            )}
            {healthError && (
              <span className="status-detail error">
                {healthError} — is the backend running?
              </span>
            )}
          </div>
        </div>
      </section>

      {/* ── Stats overview ───────────────────────────────────────────────── */}
      <section className="stats-row container">
        {[
          { label: 'Total Tasks',   value: '—', icon: '◈', color: 'var(--color-accent)' },
          { label: 'Running',       value: '—', icon: '▶', color: '#10b981' },
          { label: 'Pending',       value: '—', icon: '◎', color: '#6366f1' },
          { label: 'Completed',     value: '—', icon: '✓', color: '#10b981' },
          { label: 'Failed',        value: '—', icon: '✕', color: '#ef4444' },
        ].map(stat => (
          <div key={stat.label} className="stat-card glass-card">
            <span className="stat-icon" style={{ color: stat.color }}>{stat.icon}</span>
            <span className="stat-value">{stat.value}</span>
            <span className="stat-label">{stat.label}</span>
          </div>
        ))}
      </section>

      {/* ── Workflow pipeline (2D node diagram) ──────────────────────────── */}
      <section className="workflow-section container">
        <div className="section-header">
          <h2>Intelligence Workflow</h2>
          <p className="section-desc">
            Click a node to inspect its role in the execution pipeline.
            The 3D visualization will be added in Day 5.
          </p>
        </div>

        <div className="workflow-grid">
          {WORKFLOW_NODES.map((node, i) => (
            <div key={node.id} className="workflow-node-wrapper">
              <button
                className={`workflow-node glass-card ${selectedNode === node.id ? 'selected' : ''}`}
                onClick={() => setSelectedNode(selectedNode === node.id ? null : node.id)}
                style={{ '--node-color': node.color } as React.CSSProperties}
                aria-pressed={selectedNode === node.id}
                aria-label={`${node.label} node — ${node.description}`}
              >
                <span className="node-icon">{node.icon}</span>
                <span className="node-step">Step {i + 1}</span>
                <span className="node-label">{node.label}</span>
              </button>
              {/* Arrow connector (not after last node) */}
              {i < WORKFLOW_NODES.length - 1 && (
                <div className="workflow-arrow" aria-hidden="true">→</div>
              )}
            </div>
          ))}
        </div>

        {/* Node detail panel */}
        {selectedNodeData && (
          <div className="node-detail glass-card" role="region" aria-label="Node detail">
            <div className="node-detail-header" style={{ color: selectedNodeData.color }}>
              <span className="node-detail-icon">{selectedNodeData.icon}</span>
              <h3>{selectedNodeData.label}</h3>
            </div>
            <p>{selectedNodeData.description}</p>
            <button
              className="btn btn-ghost"
              onClick={() => setSelectedNode(null)}
              aria-label="Close node detail"
            >
              Close ✕
            </button>
          </div>
        )}
      </section>

      {/* ── Quick actions ────────────────────────────────────────────────── */}
      <section className="quick-actions container">
        <h2>Quick Actions</h2>
        <div className="action-grid">
          <button className="action-card glass-card" disabled>
            <span className="action-icon" style={{ color: 'var(--color-accent)' }}>+</span>
            <span className="action-label">New Task</span>
            <span className="action-desc">Coming in Day 2</span>
          </button>
          <button className="action-card glass-card" disabled>
            <span className="action-icon" style={{ color: '#10b981' }}>▶</span>
            <span className="action-label">Execute Plan</span>
            <span className="action-desc">Coming in Day 4</span>
          </button>
          <button className="action-card glass-card" disabled>
            <span className="action-icon" style={{ color: '#7c3aed' }}>◎</span>
            <span className="action-label">View History</span>
            <span className="action-desc">Coming in Day 4</span>
          </button>
        </div>
      </section>

      {/* ── Recent activity placeholder ──────────────────────────────────── */}
      <section className="activity-section container">
        <div className="glass-card activity-panel">
          <h2>Recent Activity</h2>
          <div className="empty-state">
            <span className="empty-icon">◈</span>
            <p>No tasks yet. Create your first task to get started.</p>
            <p className="empty-sub">Tasks, execution history and audit logs will appear here.</p>
          </div>
        </div>
      </section>

    </div>
  )
}
