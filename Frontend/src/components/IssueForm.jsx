const EXAMPLES = [
  'Kubernetes pod stuck in CrashLoopBackOff',
  'Redis out of memory errors',
  'High number of 5xx errors after code release',
  'Checkout API returns 502 after the last deploy',
]

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

export default function IssueForm({ value, onChange, onSubmit, onExample, busy }) {
  const canSubmit = value.trim().length > 0 && !busy

  function handleSubmit(event) {
    event.preventDefault()
    if (canSubmit) onSubmit()
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) handleSubmit(event)
  }

  return (
    <form className="card issue-form" onSubmit={handleSubmit}>
      <label htmlFor="issue">What is going wrong?</label>
      <textarea
        id="issue"
        rows={3}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="e.g. Database replication lag keeps increasing on the read replicas"
        autoFocus
      />
      <div className="form-row">
        <div className="examples">
          <span className="muted">Try:</span>
          {EXAMPLES.map((example) => (
            <button key={example} type="button" className="chip" onClick={() => onExample(example)} disabled={busy}>
              {example}
            </button>
          ))}
        </div>
        <button type="submit" className="button button-primary" disabled={!canSubmit}>
          {busy ? 'Analysing…' : 'Analyse'}
          {!busy && <kbd>{isMac ? '⌘' : 'Ctrl'} ↵</kbd>}
        </button>
      </div>
    </form>
  )
}
