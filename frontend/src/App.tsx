/**
 * CEREVIORA — Root Application Component
 *
 * App.tsx is the top-level component. It sets up:
 * - Client-side routing with React Router
 * - The navigation bar (shared across all pages)
 * - The route definitions that map URLs to page components
 *
 * Think of it as the "skeleton" that all pages hang from.
 */
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        {/* ── Top navigation bar ── */}
        <header className="nav-bar">
          <div className="nav-brand">
            <span className="nav-logo">◈</span>
            <span className="nav-title">CEREVIORA</span>
          </div>
          <nav className="nav-links">
            <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Dashboard
            </NavLink>
            <NavLink to="/tasks" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Tasks
            </NavLink>
            <NavLink to="/history" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              History
            </NavLink>
          </nav>
          <div className="nav-status" id="api-status-indicator">
            {/* Populated by Dashboard component via API health check */}
          </div>
        </header>

        {/* ── Main page content ── */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            {/* Additional routes added as we build pages */}
            <Route path="/tasks" element={<Dashboard />} />
            <Route path="/history" element={<Dashboard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
