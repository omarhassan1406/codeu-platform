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

export default function CodeViewer({ filename, language, code }) {
  const [copied, setCopied] = useState(false)
  const pattern = language === 'Python' ? PYTHON_TOKENS : C_LIKE_TOKENS
  const lines = code.split('\n')

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
    <div className="flex h-full min-h-0 flex-col bg-[#0c0e14]">
      <div className="flex shrink-0 items-center gap-2.5 border-b border-white/[0.06] px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-[#FF5F57]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#FEBC2E]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#28C840]" />

        <div className="ml-2 flex min-w-0 items-center gap-2 rounded-lg bg-abyss-950/60 px-3 py-1.5 ring-1 ring-white/[0.05]">
          <span className="status-pulse h-1.5 w-1.5 shrink-0 rounded-full bg-ember-400" />
          <span className="truncate font-mono text-[11px] text-slate-300">{filename}</span>
        </div>

        <span className="ml-auto hidden rounded-md border border-white/[0.07] px-2 py-1 text-[10px] font-medium text-slate-500 sm:block">
          {language}
        </span>

        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1.5 rounded-md border border-white/[0.07] bg-white/[0.03] px-2.5 py-1.5 text-[10px] font-semibold text-slate-400 transition hover:border-ember-500/30 hover:text-ember-300"
        >
          {copied ? <CheckIcon /> : <CopyIcon />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-auto bg-[#0b0d13] px-2 py-4 font-mono text-[12.5px] leading-6 sm:text-[13px] sm:leading-7">
        {lines.map((line, lineIndex) => (
          <div key={lineIndex} className="flex min-w-max px-2">
            <span className="w-8 shrink-0 select-none pr-4 text-right text-[11px] text-slate-700">
              {lineIndex + 1}
            </span>
            <code className="whitespace-pre">
              {line.length === 0
                ? '\u00A0'
                : tokenizeLine(line, pattern).map((token, tokenIndex) => (
                    <span key={tokenIndex} className={TOKEN_CLASSES[token.type]}>
                      {token.text}
                    </span>
                  ))}
            </code>
          </div>
        ))}
      </div>

      <div className="flex shrink-0 items-center justify-between border-t border-white/[0.05] px-4 py-2 text-[9px] font-medium uppercase tracking-[0.18em] text-slate-600">
        <span className="code-footer-label">AI sandbox · synced with lesson</span>
        <span className="font-mono normal-case tracking-normal">{lines.length} lines</span>
      </div>
    </div>
  )
}
