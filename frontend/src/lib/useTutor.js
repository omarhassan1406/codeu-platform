import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { loadJSON, saveJSON } from './storage'

const MAX_CAPTION_CHARS = 120
const MS_PER_CHAR = 55
const MIN_CAPTION_MS = 2200
// Matches the backend's TTS_MAX_CHARS default with a little headroom.
const MAX_SPOKEN_CHARS = 2900

const hasArabic = (text) => /[؀-ۿ]/.test(text)

// Answers arrive as Markdown. Captions and speech are spoken text, so code
// blocks become a pointer to the answer panel and formatting marks are dropped.
export function toSpokenText(markdown) {
  const codeNote = hasArabic(markdown) ? ' (شاهد الكود في لوحة الإجابة) ' : ' (see the code in the answer panel) '
  return markdown
    .replace(/```[\s\S]*?(```|$)/g, codeNote)
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/(\*\*|__|\*|_|~~)(?=\S)([\s\S]*?\S)\1/g, '$2')
    .replace(/^\s{0,3}(#{1,6}|>|[-*+]|\d+\.)\s+/gm, '')
    .replace(/^\s*[-*_]{3,}\s*$/gm, '')
}

// Break an answer into short subtitle lines: sentences first, then commas or
// spaces when a sentence is too long to read at a glance.
export function toCaptions(text) {
  const sentences = toSpokenText(text)
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

// Keep whole caption lines up to the speech length limit, so captions and
// audio always cover the same words. The answer panel still shows everything.
function limitSpoken(lines) {
  const kept = []
  let total = 0
  for (const line of lines) {
    if (kept.length && total + line.length + 1 > MAX_SPOKEN_CHARS) break
    kept.push(line)
    total += line.length + 1
  }
  return kept
}

// Each caption gets a share of the audio proportional to its length.
function captionEnds(lines) {
  const total = lines.reduce((sum, line) => sum + line.length, 0) || 1
  let acc = 0
  return lines.map((line) => (acc += line.length) / total)
}

const captionDuration = (line) => Math.max(MIN_CAPTION_MS, line.length * MS_PER_CHAR)

/**
 * Professor state machine for one lesson:
 *   idle -> listening (question box open / recording)
 *        -> thinking (transcribing, answering, preparing voice)
 *        -> talking/explaining (voice + captions, or captions alone) -> idle
 *
 * With voice on, captions follow the audio clock. If speech is unavailable or
 * the browser blocks playback, captions fall back to a reading-speed timer.
 */
export function useTutor({ courseTitle, stepId }) {
  const [status, setStatus] = useState('idle')
  const [exchange, setExchange] = useState(null) // { question, answer, grounded, sources }
  const [error, setError] = useState(null)
  const [captions, setCaptions] = useState([])
  const [captionIndex, setCaptionIndex] = useState(-1)
  const [mode, setMode] = useState('timer') // 'timer' | 'audio'
  const [voiceOn, setVoiceOnState] = useState(() => loadJSON('voice', true) !== false)
  const [voiceNotice, setVoiceNotice] = useState(null)
  const requestRef = useRef(0)
  const audioRef = useRef(null)
  const audioUrlsRef = useRef(new Map()) // answer text -> object URL, reused by Replay

  const stopAudio = useCallback(() => {
    const audio = audioRef.current
    if (audio) {
      audio.ontimeupdate = audio.onended = audio.onerror = null
      audio.pause()
    }
    audioRef.current = null
  }, [])

  const releaseAudio = useCallback(() => {
    stopAudio()
    audioUrlsRef.current.forEach((url) => URL.revokeObjectURL(url))
    audioUrlsRef.current.clear()
  }, [stopAudio])

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
    setMode('timer')
  }

  // Ignore answers to questions asked about the previous lesson, and silence it.
  useEffect(() => {
    requestRef.current += 1
    return releaseAudio
  }, [lessonKey, releaseAudio])

  const speaking = captionIndex >= 0 && captionIndex < captions.length

  // Timer mode: advance captions at reading speed; idle after the last one.
  useEffect(() => {
    if (!speaking || mode !== 'timer') return undefined
    const timer = window.setTimeout(() => {
      setCaptionIndex((index) => {
        const next = index + 1
        if (next >= captions.length) setStatus('idle')
        return next
      })
    }, captionDuration(captions[captionIndex]))
    return () => window.clearTimeout(timer)
  }, [speaking, mode, captionIndex, captions])

  const playCaptionsOnly = useCallback((lines, speakingState, fromIndex = 0) => {
    setMode('timer')
    setCaptions(lines)
    setCaptionIndex(lines.length ? fromIndex : -1)
    setStatus(lines.length ? speakingState : 'idle')
  }, [])

  const speak = useCallback(
    async (text, speakingState, id) => {
      stopAudio()
      const lines = limitSpoken(toCaptions(text))
      if (!lines.length || !voiceOn) {
        playCaptionsOnly(toCaptions(text), speakingState)
        return
      }

      let url = audioUrlsRef.current.get(text)
      if (!url) {
        setStatus('thinking') // preparing the voice
        try {
          url = URL.createObjectURL(await api.speak(lines.join(' ')))
          audioUrlsRef.current.set(text, url)
        } catch (err) {
          if (id !== requestRef.current) return
          setVoiceNotice(err.message || 'Voice is unavailable right now, showing captions only.')
          playCaptionsOnly(lines, speakingState)
          return
        }
      }
      if (id !== requestRef.current) return

      const ends = captionEnds(lines)
      const audio = new Audio(url)
      audioRef.current = audio
      audio.ontimeupdate = () => {
        if (!audio.duration || !Number.isFinite(audio.duration)) return
        const progress = audio.currentTime / audio.duration
        const index = ends.findIndex((end) => progress < end)
        setCaptionIndex(index === -1 ? lines.length - 1 : index)
      }
      audio.onended = () => {
        audioRef.current = null
        setCaptionIndex(-1)
        setStatus('idle')
      }
      audio.onerror = () => {
        stopAudio()
        playCaptionsOnly(lines, speakingState)
      }

      setVoiceNotice(null)
      setMode('audio')
      setCaptions(lines)
      setCaptionIndex(0)
      setStatus(speakingState)
      try {
        await audio.play()
      } catch {
        // Autoplay blocked or decode failure: keep the answer readable.
        if (audioRef.current !== audio) return
        stopAudio()
        setVoiceNotice('The browser blocked audio playback. Press Replay to hear the answer.')
        playCaptionsOnly(lines, speakingState)
      }
    },
    [voiceOn, stopAudio, playCaptionsOnly],
  )

  const startListening = useCallback(() => {
    stopAudio()
    setError(null)
    setCaptionIndex(-1)
    setStatus('listening')
  }, [stopAudio])

  const stop = useCallback(() => {
    requestRef.current += 1
    stopAudio()
    setCaptionIndex(-1)
    setStatus('idle')
  }, [stopAudio])

  const ask = useCallback(
    async (question) => {
      const id = ++requestRef.current
      stopAudio()
      setError(null)
      setCaptionIndex(-1)
      setStatus('thinking')
      try {
        const result = await api.raiseHand({ courseTitle, stepId, question })
        if (id !== requestRef.current) return
        const grounded = result.avatar_state !== 'idle'
        setExchange({ question, answer: result.answer_text, grounded, sources: result.context_used ?? [] })
        await speak(result.answer_text, grounded ? 'explaining' : 'talking', id)
      } catch (err) {
        if (id !== requestRef.current) return
        setError(err.message)
        setStatus('idle')
      }
    },
    [courseTitle, stepId, speak, stopAudio],
  )

  // Spoken question: transcribe, then ask. Resolves to the transcript (or null).
  const askByVoice = useCallback(
    async (audioBlob) => {
      const id = ++requestRef.current
      setError(null)
      setStatus('thinking')
      try {
        const result = await api.transcribe(audioBlob)
        if (id !== requestRef.current) return null
        const text = (result.text || '').trim()
        if (text.length < 2) {
          setError('I didn’t catch that. Try again, or type your question.')
          setStatus('idle')
          return null
        }
        ask(text)
        return text
      } catch (err) {
        if (id !== requestRef.current) return null
        setError(err.message)
        setStatus('idle')
        return null
      }
    },
    [ask],
  )

  const replay = useCallback(() => {
    if (!exchange) return
    const id = ++requestRef.current
    speak(exchange.answer, exchange.grounded ? 'explaining' : 'talking', id)
  }, [exchange, speak])

  const setVoiceOn = useCallback(
    (on) => {
      setVoiceOnState(on)
      saveJSON('voice', on)
      if (!on && audioRef.current) {
        // Keep the remaining captions going without sound.
        stopAudio()
        setMode('timer')
      }
    },
    [stopAudio],
  )

  return {
    status,
    exchange,
    error,
    caption: speaking ? captions[captionIndex] : null,
    captionKey: captionIndex,
    speaking,
    voiceOn,
    voiceNotice,
    setVoiceOn,
    startListening,
    stop,
    ask,
    askByVoice,
    replay,
  }
}
