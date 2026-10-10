import { useMemo, useState } from 'react'
import { normalizeResponse, toPlainText } from '../parse.js'

const MODES = {
  RAG: {
    label: 'Matched known issues',
    tone: 'match',
    blurb: 'Grounded in the most similar issues from the knowledge base, listed below.',
  },
  LLM_ONLY: {
    label: 'Model reasoning only',
    tone: 'solo',
    blurb:
      'No known issue was similar enough, so this is the model’s general reasoning with no past cases behind it. Treat it as a starting point.',
  },
}

export default function Result({ issue, data }) {
  const result = useMemo(() => normalizeResponse(data), [data])
  const mode = MODES[result.mode] ?? { label: result.mode, tone: 'solo', blurb: '' }
  const hasAnalysis = result.rootCauses.length > 0 || result.solutions.length > 0

  return (
    <section className="card result" aria-live="polite">
      <header className="result-head">
        <div>
          <p className="eyebrow">Analysis of</p>
          <h2>{issue}</h2>
        </div>
        <CopyButton text={toPlainText(issue, result)} />
      </header>

      <div className={`mode mode-${mode.tone}`}>
        <span className="mode-badge">{mode.label}</span>
        {mode.blurb && <p>{mode.blurb}</p>}
      </div>

      {result.rawOutput && (
        <div className="notice notice-warn">
          <h3>The model’s reply could not be read as structured data</h3>
          <p className="muted">This is what it returned, unformatted:</p>
          <pre className="code">{result.rawOutput}</pre>
        </div>
      )}

      {hasAnalysis && (
        <div className="findings">
          <Findings title="Likely root causes" tone="cause" items={result.rootCauses} />
          <Findings title="Recommended fixes" tone="fix" items={result.solutions} />
        </div>
      )}

      {(result.explanation || result.confidence !== null) && (
        <div className="reasoning">
          {result.explanation && (
            <div>
              <h3>Why these causes</h3>
              <p>{result.explanation}</p>
            </div>
          )}
          {result.confidence !== null && <Confidence value={result.confidence} />}
        </div>
      )}

      {result.similar.length > 0 && (
        <div className="similar">
          <h3>Similar known issues</h3>
          <ul>
            {result.similar.map((item, index) => (
              <SimilarIssue key={`${item.title}-${index}`} item={item} open={index === 0} />
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function Findings({ title, tone, items }) {
  return (
    <div className={`findings-col findings-${tone}`}>
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="muted">None returned.</p>
      ) : (
        <ol>
          {items.map((item, index) => (
            <li key={index}>
              <span className="num">{index + 1}</span>
              <span>{item}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function Confidence({ value }) {
  const percent = Math.round(value * 100)
  const level = value >= 0.8 ? 'High' : value >= 0.5 ? 'Medium' : 'Low'
  return (
    <div className="confidence">
      <div className="confidence-head">
        <h3>Model confidence</h3>
        <strong>{percent}%</strong>
      </div>
      <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-label="Model confidence">
        <span style={{ width: `${percent}%` }} />
      </div>
      <p className="muted">{level}. Self-reported by the model, not measured.</p>
    </div>
  )
}

function SimilarIssue({ item, open }) {
  return (
    <li className="similar-item">
      <details open={open}>
        <summary>
          <span className="similar-title">{item.title}</span>
          {item.score !== null && (
            <span className="score" title="Similarity to your description, from 0 to 1">
              <span className="meter meter-small" aria-hidden="true">
                <span style={{ width: `${Math.round(item.score * 100)}%` }} />
              </span>
              {item.score.toFixed(2)}
            </span>
          )}
        </summary>
        <div className="similar-body">
          <SimilarList title="Recorded causes" items={item.causes} />
          <SimilarList title="Recorded fixes" items={item.solutions} />
        </div>
      </details>
    </li>
  )
}

function SimilarList({ title, items }) {
  if (items.length === 0) return null
  return (
    <div>
      <h4>{title}</h4>
      <ul>
        {items.map((entry, index) => (
          <li key={index}>{entry}</li>
        ))}
      </ul>
    </div>
  )
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <button type="button" className="button button-quiet" onClick={copy}>
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}
