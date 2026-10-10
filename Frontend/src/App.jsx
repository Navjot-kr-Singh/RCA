import { useEffect, useRef, useState } from 'react'
import { API_URL, analyzeIssue, checkHealth } from './api.js'
import IssueForm from './components/IssueForm.jsx'
import Result from './components/Result.jsx'
import History from './components/History.jsx'

const HISTORY_KEY = 'rca.history'
const HISTORY_LIMIT = 10
const START_COMMAND = 'cd Backend && .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000'

const STATUS_LABELS = {
  checking: 'Checking API',
  online: 'API online',
  offline: 'API offline',
}

function loadHistory() {
  try {
    const saved = JSON.parse(localStorage.getItem(HISTORY_KEY))
    return Array.isArray(saved) ? saved : []
  } catch {
    return []
  }
}

export default function App() {
  const [apiStatus, setApiStatus] = useState('checking')
  const [issue, setIssue] = useState('')
  const [view, setView] = useState({ state: 'idle' })
  const [history, setHistory] = useState(loadHistory)
  const inFlight = useRef(null)

  useEffect(() => {
    const controller = new AbortController()
    const ping = () =>
      checkHealth(controller.signal).then((ok) => {
        if (!controller.signal.aborted) setApiStatus(ok ? 'online' : 'offline')
      })
    ping()
    const timer = setInterval(ping, 15000)
    return () => {
      controller.abort()
      clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history))
    } catch {
      // Storage can be unavailable (private mode); history then lasts for the session only.
    }
  }, [history])

  async function submit(text) {
    const query = text.trim()
    if (!query) return

    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    setView({ state: 'loading', issue: query })

    try {
      const data = await analyzeIssue(query, controller.signal)
      const entry = { id: String(Date.now()), issue: query, at: Date.now(), data }
      setApiStatus('online')
      setHistory((prev) => [entry, ...prev.filter((h) => h.issue !== query)].slice(0, HISTORY_LIMIT))
      setView({ state: 'done', id: entry.id, issue: query, data })
    } catch (err) {
      if (err.name === 'AbortError') return
      if (err.kind === 'unreachable') setApiStatus('offline')
      setView({ state: 'error', issue: query, message: err.message, unreachable: err.kind === 'unreachable' })
    }
  }

  function cancel() {
    inFlight.current?.abort()
    setView({ state: 'idle' })
  }

  function runExample(text) {
    setIssue(text)
    submit(text)
  }

  function openHistory(entry) {
    inFlight.current?.abort()
    setIssue(entry.issue)
    setView({ state: 'done', id: entry.id, issue: entry.issue, data: entry.data })
  }

  function clearHistory() {
    setHistory([])
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" width="20" height="20">
              <path d="M16 6v8m0 0-7 11m7-11 7 11" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" fill="none" />
            </svg>
          </span>
          <div>
            <h1>Root Cause Analysis</h1>
            <p>Describe a production issue and get likely causes and fixes.</p>
          </div>
        </div>
        <span className={`status status-${apiStatus}`} title={API_URL}>
          <span className="status-dot" aria-hidden="true" />
          {STATUS_LABELS[apiStatus]}
        </span>
      </header>

      <main className="layout">
        <div className="main-column">
          <IssueForm
            value={issue}
            onChange={setIssue}
            onSubmit={() => submit(issue)}
            onExample={runExample}
            busy={view.state === 'loading'}
          />

          {view.state === 'idle' && apiStatus === 'offline' && (
            <Offline onRetry={() => checkHealth().then((ok) => setApiStatus(ok ? 'online' : 'offline'))} />
          )}
          {view.state === 'idle' && apiStatus !== 'offline' && <HowItWorks />}
          {view.state === 'loading' && <Loading issue={view.issue} onCancel={cancel} />}
          {view.state === 'error' && (
            <section className="card notice notice-error" role="alert">
              <h2>Analysis failed</h2>
              <p>{view.message}</p>
              {view.unreachable && <StartCommand />}
              <button type="button" className="button" onClick={() => submit(view.issue)}>
                Try again
              </button>
            </section>
          )}
          {view.state === 'done' && <Result key={view.id} issue={view.issue} data={view.data} />}
        </div>

        <aside className="side-column">
          <History
            entries={history}
            activeId={view.state === 'done' ? view.id : null}
            onOpen={openHistory}
            onClear={clearHistory}
          />
        </aside>
      </main>
    </div>
  )
}

function StartCommand() {
  return (
    <>
      <p className="muted">Start the backend from the project root, then try again:</p>
      <pre className="code">{START_COMMAND}</pre>
    </>
  )
}

function Offline({ onRetry }) {
  return (
    <section className="card notice notice-error" role="alert">
      <h2>The RCA API is not reachable</h2>
      <p>
        Nothing answered at <code>{API_URL}</code>.
      </p>
      <StartCommand />
      <button type="button" className="button" onClick={onRetry}>
        Check again
      </button>
    </section>
  )
}

function HowItWorks() {
  return (
    <section className="card how">
      <h2>How an analysis is produced</h2>
      <ol className="steps">
        <li>
          <strong>Search.</strong> Your description is compared with a knowledge base of known production issues,
          each with its recorded causes and fixes.
        </li>
        <li>
          <strong>Ground.</strong> If a known issue is similar enough, the three closest ones are handed to the
          model as evidence and shown alongside the answer.
        </li>
        <li>
          <strong>Fall back.</strong> If nothing is close, the model answers from general knowledge alone, and the
          result is labelled that way.
        </li>
      </ol>
    </section>
  )
}

function Loading({ issue, onCancel }) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <section className="card loading" aria-live="polite" aria-busy="true">
      <div className="loading-head">
        <span className="spinner" aria-hidden="true" />
        <div>
          <h2>Analysing…</h2>
          <p className="muted">
            Searching known issues, then asking the model. This usually takes a few seconds ({seconds}s).
          </p>
        </div>
        <button type="button" className="button button-quiet" onClick={onCancel}>
          Cancel
        </button>
      </div>
      <p className="loading-issue">{issue}</p>
      <div className="skeleton" />
      <div className="skeleton short" />
    </section>
  )
}
