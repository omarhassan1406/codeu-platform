import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'

const MAX_CAPTION_CHARS = 120
const MS_PER_CHAR = 55
const MIN_CAPTION_MS = 2200

// Break an answer into short subtitle lines: sentences first, then commas or
// spaces when a sentence is too long to read at a glance.
export function toCaptions(text) {
  const sentences = text
    .replace(/\s+/g, ' ')
    .split(/(?<=[.!?؟؛])\s+/)
    .map((s) => s.trim())
    .filter(Boolean)

  const lines = []
  for (const sentence of sentences) {
    let rest = sentence
    while (rest.length > MAX_CAPTION_CHARS) {
      const window = rest.slice(0, MAX_CAPTION_CHARS)
      const cut = Math.max(window.lastIndexOf('، '), window.lastIndexOf(', '), window.lastIndexOf(' '))
      const at = cut > MAX_CAPTION_CHARS / 2 ? cut + 1 : MAX_CAPTION_CHARS
      lines.push(rest.slice(0, at).trim())
      rest = rest.slice(at).trim()
    }
    if (rest) lines.push(rest)
  }
  return lines
}

const captionDuration = (line) => Math.max(MIN_CAPTION_MS, line.length * MS_PER_CHAR)

/**
 * Professor state machine for one lesson:
 *   idle -> listening (question box open) -> thinking (request in flight)
 *        -> talking/explaining (captions play) -> idle
 */
export function useTutor({ courseTitle, stepId }) {
  const [status, setStatus] = useState('idle')
  const [exchange, setExchange] = useState(null) // { question, answer, grounded, sources }
  const [error, setError] = useState(null)
  const [captions, setCaptions] = useState([])
  const [captionIndex, setCaptionIndex] = useState(-1)
  const requestRef = useRef(0)

  // A new lesson starts a fresh conversation (adjusting state during render,
  // as React recommends, instead of remounting the avatar).
  const lessonKey = `${courseTitle}|${stepId}`
  const [activeLesson, setActiveLesson] = useState(lessonKey)
  if (activeLesson !== lessonKey) {
    setActiveLesson(lessonKey)
    setStatus('idle')
    setExchange(null)
    setError(null)
    setCaptions([])
    setCaptionIndex(-1)
  }

  // Ignore answers to questions asked about the previous lesson.
  useEffect(() => {
    requestRef.current += 1
  }, [lessonKey])

  const speaking = captionIndex >= 0 && captionIndex < captions.length

  // Advance captions on a timer; return to idle when the last one ends.
  useEffect(() => {
    if (!speaking) return undefined
    const timer = window.setTimeout(() => {
      setCaptionIndex((index) => {
        const next = index + 1
        if (next >= captions.length) setStatus('idle')
        return next
      })
    }, captionDuration(captions[captionIndex]))
    return () => window.clearTimeout(timer)
  }, [speaking, captionIndex, captions])

  const speak = useCallback((text, speakingState) => {
    const lines = toCaptions(text)
    setCaptions(lines)
    setCaptionIndex(lines.length ? 0 : -1)
    setStatus(lines.length ? speakingState : 'idle')
  }, [])

  const startListening = useCallback(() => {
    setError(null)
    setCaptionIndex(-1)
    setStatus('listening')
  }, [])

  const stop = useCallback(() => {
    requestRef.current += 1
    setCaptionIndex(-1)
    setStatus('idle')
  }, [])

  const ask = useCallback(
    async (question) => {
      const id = ++requestRef.current
      setError(null)
      setCaptionIndex(-1)
      setStatus('thinking')
      try {
        const result = await api.raiseHand({ courseTitle, stepId, question })
        if (id !== requestRef.current) return
        const grounded = result.avatar_state !== 'idle'
        setExchange({
          question,
          answer: result.answer_text,
          grounded,
          sources: result.context_used ?? [],
        })
        speak(result.answer_text, grounded ? 'explaining' : 'talking')
      } catch (err) {
        if (id !== requestRef.current) return
        setError(err.message)
        setStatus('idle')
      }
    },
    [courseTitle, stepId, speak],
  )

  const replay = useCallback(() => {
    if (exchange) speak(exchange.answer, exchange.grounded ? 'explaining' : 'talking')
  }, [exchange, speak])

  return {
    status,
    exchange,
    error,
    caption: speaking ? captions[captionIndex] : null,
    captionKey: captionIndex,
    speaking,
    startListening,
    stop,
    ask,
    replay,
  }
}
