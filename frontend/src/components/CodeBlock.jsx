import { useState } from 'react'

const KEYWORDS = new Set([
  'and',
  'as',
  'async',
  'await',
  'class',
  'const',
  'def',
  'elif',
  'else',
  'except',
  'export',
  'extends',
  'False',
  'false',
  'final',
  'for',
  'from',
  'function',
  'if',
  'import',
  'in',
  'lambda',
  'let',
  'new',
  'None',
  'not',
  'null',
  'or',
  'override',
  'pass',
  'print',
  'required',
  'return',
  'super',
  'this',
  'True',
  'true',
  'try',
  'var',
  'void',
  'while',
  'with',
  'yield',
])

const PYTHON_TOKENS = /(#.*$)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]\w*\b/g
const C_LIKE_TOKENS = /(\/\/.*$)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]\w*\b/g

const TOKEN_CLASSES = {
  plain: 'text-slate-300',
  comment: 'text-slate-500 italic',
  string: 'text-emerald-300',
  keyword: 'text-ember-400',
  number: 'text-amber-300',
  function: 'text-sky-300',
}

function tokenizeLine(line, pattern) {
  const tokens = []
  let cursor = 0

  for (const match of line.matchAll(pattern)) {
    const index = match.index ?? 0
    if (index > cursor) tokens.push({ text: line.slice(cursor, index), type: 'plain' })

    const value = match[0]
    let type = 'plain'

    if (match[1]) type = 'comment'
    else if (match[2]) type = 'string'
    else if (/^\d/.test(value)) type = 'number'
    else if (KEYWORDS.has(value)) type = 'keyword'
    else if (/^\s*\(/.test(line.slice(index + value.length))) type = 'function'

    tokens.push({ text: value, type })
    cursor = index + value.length
  }

  if (cursor < line.length) tokens.push({ text: line.slice(cursor), type: 'plain' })
  return tokens
}

function CopyIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3.5 w-3.5">
      <rect x="9" y="9" width="10" height="10" rx="2" />
      <path d="M15 9V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h4" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
      <path d="m5 12 4.5 4.5L19 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

const PYTHON_LIKE = new Set(['python', 'py', 'bash', 'sh', 'shell', 'yaml', 'yml', 'ruby', 'r'])

export default function CodeBlock({ language = '', code }) {
  const [copied, setCopied] = useState(false)
  const lang = language.toLowerCase()
  const pattern = PYTHON_LIKE.has(lang) ? PYTHON_TOKENS : C_LIKE_TOKENS
  const lines = code.replace(/\n$/, '').split('\n')

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      setCopied(false)
    }
  }

  return (
    <figure dir="ltr" className="my-6overflow-hidden rounded-xl border border-white/[0.07] bg-abyss-950">
      <figcaption className="flex items-center justify-between gap-3 border-b border-white/[0.06] bg-white/[0.02] px-4 py-2">
        <span className="font-mono text-[11px] text-slate-400">{lang || 'code'}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-semibold text-slate-400 transition hover:bg-white/[0.05] hover:text-ember-300"
        >
          {copied ? <CheckIcon /> : <CopyIcon />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </figcaption>

      <pre className="scrollbar-thin overflow-x-auto py-3 font-mono text-[13px] leading-6">
        {lines.map((line, lineIndex) => (
          <div key={lineIndex} className="flex min-w-max px-2">
            <span className="w-9 shrink-0 select-none pr-4 text-right text-[11px] tabular-nums text-slate-600">
              {lineIndex + 1}
            </span>
            <code className="whitespace-pre pr-4">
              {line.length === 0
                ? ' '
                : tokenizeLine(line, pattern).map((token, tokenIndex) => (
                    <span key={tokenIndex} className={TOKEN_CLASSES[token.type]}>
                      {token.text}
                    </span>
                  ))}
            </code>
          </div>
        ))}
      </pre>
    </figure>
  )
}
