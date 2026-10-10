// Turns the backend's /analyze response into a shape the UI can render directly.
//
// Backend contract (Backend/rca_engine.py):
//   mode            "RAG" when a known issue is similar enough, otherwise "LLM_ONLY"
//   analysis        { root_causes, solutions, confidence, explanation }
//                   or { error, raw_output } when the model's reply was not valid JSON
//   similar_issues  [{ content, similarity_score }], empty in LLM_ONLY mode

function asList(value) {
  if (Array.isArray(value)) return value.map((v) => String(v).trim()).filter(Boolean)
  if (typeof value === 'string' && value.trim()) return [value.trim()]
  return []
}

function asConfidence(value) {
  let n = typeof value === 'string' ? parseFloat(value) : value
  if (typeof n !== 'number' || Number.isNaN(n)) return null
  if (n > 1 && n <= 100) n /= 100
  return Math.min(1, Math.max(0, n))
}

// The model sometimes wraps its JSON in a code fence or adds a sentence around it,
// which the backend reports as an error. The object inside is usually still usable.
function recoverJson(raw) {
  if (typeof raw !== 'string') return null
  const start = raw.indexOf('{')
  const end = raw.lastIndexOf('}')
  if (start === -1 || end <= start) return null
  try {
    return JSON.parse(raw.slice(start, end + 1))
  } catch {
    return null
  }
}

function field(content, name) {
  const match = content.match(new RegExp(`^\\s*${name}:\\s*(.+)$`, 'm'))
  return match ? match[1].trim() : ''
}

// The backend joins each issue's causes and solutions with ", ". Split them back,
// leaving commas inside parentheses or mid-sentence ("checks HTTP, not dependencies") alone.
function splitItems(text) {
  const items = []
  let depth = 0
  let current = ''
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (ch === '(') depth++
    if (ch === ')') depth = Math.max(0, depth - 1)
    if (ch === ',' && depth === 0 && text[i + 1] === ' ' && /[A-Z]/.test(text[i + 2] ?? '')) {
      items.push(current.trim())
      current = ''
      i++
      continue
    }
    current += ch
  }
  if (current.trim()) items.push(current.trim())
  return items
}

function parseSimilar(entry) {
  const content = typeof entry?.content === 'string' ? entry.content : ''
  const title = field(content, 'Issue')
  return {
    title: title || content.trim(),
    causes: splitItems(field(content, 'Causes')),
    solutions: splitItems(field(content, 'Solutions')),
    score: asConfidence(entry?.similarity_score),
  }
}

export function normalizeResponse(data) {
  let analysis = data?.analysis ?? {}
  let rawOutput = null

  if (analysis.error) {
    const recovered = recoverJson(analysis.raw_output)
    if (recovered) {
      analysis = recovered
    } else {
      rawOutput = typeof analysis.raw_output === 'string' ? analysis.raw_output : analysis.error
      analysis = {}
    }
  }

  return {
    mode: data?.mode ?? 'UNKNOWN',
    rootCauses: asList(analysis.root_causes),
    solutions: asList(analysis.solutions),
    confidence: asConfidence(analysis.confidence),
    explanation: typeof analysis.explanation === 'string' ? analysis.explanation.trim() : '',
    rawOutput,
    similar: Array.isArray(data?.similar_issues) ? data.similar_issues.map(parseSimilar) : [],
  }
}

export function toPlainText(issue, result) {
  const lines = [`Issue: ${issue}`, '']
  const section = (heading, items) => {
    if (!items.length) return
    lines.push(heading)
    items.forEach((item, i) => lines.push(`${i + 1}. ${item}`))
    lines.push('')
  }
  section('Likely root causes', result.rootCauses)
  section('Recommended fixes', result.solutions)
  if (result.explanation) lines.push(`Why: ${result.explanation}`, '')
  if (result.confidence !== null) lines.push(`Model confidence: ${Math.round(result.confidence * 100)}%`)
  if (result.rawOutput) lines.push(result.rawOutput)
  return lines.join('\n').trim()
}
