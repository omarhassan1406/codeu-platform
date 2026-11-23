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
    // Single underscores stay: they appear in code names like my_var.
    .replace(/(\*\*|__|\*|~~)(?=\S)([\s\S]*?\S)\1/g, '$2')
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

// Group caption lines into speech segments (arrays of line indexes). The first
// is short so playback starts fast; later ones are longer to limit requests.
const FIRST_SEGMENT_CHARS = 180
const SEGMENT_CHARS = 420

export function toSegments(lines) {
  const segments = []
  let current = []
  let length = 0
  lines.forEach((line, i) => {
    const cap = segments.length === 0 ? FIRST_SEGMENT_CHARS : SEGMENT_CHARS
    if (current.length && length + line.length > cap) {
      segments.push(current)
      current = []
      length = 0
    }
    current.push(i)
    length += line.length + 1
  })
  if (current.length) segments.push(current)
  return segments
}

// Each caption gets a share of the audio proportional to its length.
function captionEnds(lines) {
  const total = lines.reduce((sum, line) => sum + line.length, 0) || 1
  let acc = 0
  return lines.map((line) => (acc += line.length) / total)
}

const captionDuration = (line) => Math.max(MIN_CAPTION_MS, line.length * MS_PER_CHAR)

// Why a spoken question was not used (recorder or /voice/transcribe `rejected`).
export const VOICE_REJECTION_MESSAGES = {
  silent: 'I didn’t hear anything. Check that the right microphone is on and unmuted, then try again.',
  too_short: 'That was too short. Tap the mic, ask your question, then tap it again to send.',
  no_speech: 'I didn’t hear a question, only silence or background noise. Try again closer to the mic.',
  unsupported_language: 'I can understand questions in Arabic or English. Please try again in one of those.',
  low_confidence: 'That was hard to make out. Try again more clearly, or type your question.',
}

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
  // What the professor is busy with: 'transcribing' | 'answering' | 'voice' | null
  const [activity, setActivity] = useState(null)
  const [heard, setHeard] = useState(null) // last transcript, shown while answering
  const [speechKind, setSpeechKind] = useState(null) // 'answer' | 'lecture'
  const [lectureError, setLectureError] = useState(null)
  const [quota, setQuota] = useState(null) // { limit, used, remaining, resets_at }
  const requestRef = useRef(0)

  // Daily question allowance, refreshed after every answer.
  useEffect(() => {
    let cancelled = false
    api
      .getQuota()
      .then((q) => !cancelled && setQuota(q))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])
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
    setActivity(null)
    setHeard(null)
    setSpeechKind(null)
    setLectureError(null)
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
    setActivity(null)
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

      // Speech is synthesised per segment: the first plays after ~2s while the
      // next is fetched, instead of waiting ~20s for a whole lecture.
      const segments = toSegments(lines)
      const pending = new Map()
      const fetchSegment = (k) => {
        if (!pending.has(k)) {
          const segmentText = segments[k].map((i) => lines[i]).join(' ')
          const cached = audioUrlsRef.current.get(segmentText)
          pending.set(
            k,
            cached
              ? Promise.resolve(cached)
              : api.speak(segmentText).then((blob) => {
                  const url = URL.createObjectURL(blob)
                  audioUrlsRef.current.set(segmentText, url)
                  return url
                }),
          )
        }
        return pending.get(k)
      }

      setStatus('thinking') // preparing the voice
      setActivity('voice')
      let firstUrl
      try {
        firstUrl = await fetchSegment(0)
      } catch (err) {
        if (id !== requestRef.current) return
        setVoiceNotice(err.message || 'Voice is unavailable right now, showing captions only.')
        playCaptionsOnly(lines, speakingState)
        return
      }
      if (id !== requestRef.current) return

      const fallBackToCaptions = (fromLine, notice) => {
        stopAudio()
        if (notice) setVoiceNotice(notice)
        playCaptionsOnly(lines, speakingState, fromLine)
      }

      const playSegment = async (k, url) => {
        if (id !== requestRef.current) return
        if (k + 1 < segments.length) fetchSegment(k + 1).catch(() => {}) // prefetch
        const lineIdx = segments[k]
        const ends = captionEnds(lineIdx.map((i) => lines[i]))
        const audio = new Audio(url)
        audioRef.current = audio
        audio.ontimeupdate = () => {
          if (!audio.duration || !Number.isFinite(audio.duration)) return
          const progress = audio.currentTime / audio.duration
          const index = ends.findIndex((end) => progress < end)
          setCaptionIndex(lineIdx[index === -1 ? lineIdx.length - 1 : index])
        }
        audio.onended = async () => {
          if (audioRef.current !== audio) return // stopped meanwhile
          if (k + 1 >= segments.length) {
            audioRef.current = null
            setCaptionIndex(-1)
            setStatus('idle')
            return
          }
          let nextUrl
          try {
            nextUrl = await fetchSegment(k + 1)
          } catch {
            if (audioRef.current === audio) fallBackToCaptions(segments[k + 1][0])
            return
          }
          if (audioRef.current !== audio || id !== requestRef.current) return
          playSegment(k + 1, nextUrl)
        }
        audio.onerror = () => {
          if (audioRef.current === audio) fallBackToCaptions(lineIdx[0])
        }
        setCaptionIndex(lineIdx[0])
        try {
          await audio.play()
        } catch {
          // Autoplay blocked or decode failure: keep the answer readable.
          if (audioRef.current === audio) {
            fallBackToCaptions(lineIdx[0], 'The browser blocked audio playback. Press Replay to hear it.')
          }
        }
      }

      setVoiceNotice(null)
      setActivity(null)
      setMode('audio')
      setCaptions(lines)
      setStatus(speakingState)
      await playSegment(0, firstUrl)
    },
    [voiceOn, stopAudio, playCaptionsOnly],
  )

  const startListening = useCallback(() => {
    // Raising a hand cancels anything still being prepared or spoken.
    requestRef.current += 1
    stopAudio()
    setError(null)
    setCaptionIndex(-1)
    setStatus('listening')
  }, [stopAudio])

  const stop = useCallback(() => {
    requestRef.current += 1
    stopAudio()
    setActivity(null)
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
      setActivity('answering')
      setSpeechKind('answer')
      try {
        const result = await api.raiseHand({ courseTitle, stepId, question })
        if (id !== requestRef.current) return
        const grounded = result.avatar_state !== 'idle'
        setExchange({ question, answer: result.answer_text, grounded, sources: result.context_used ?? [] })
        setHeard(null)
        if (result.questions_remaining != null) {
          setQuota((q) => (q ? { ...q, remaining: result.questions_remaining, used: q.used + 1 } : q))
        }
        await speak(result.answer_text, grounded ? 'explaining' : 'talking', id)
      } catch (err) {
        if (id !== requestRef.current) return
        if (err.status === 429) setQuota((q) => (q ? { ...q, remaining: 0 } : q))
        setError(err.message)
        setActivity(null)
        setStatus('idle')
      }
    },
    [courseTitle, stepId, speak, stopAudio],
  )

  // A recording the recorder refused to send (silent / too short).
  const rejectRecording = useCallback((reason) => {
    setError(VOICE_REJECTION_MESSAGES[reason] ?? VOICE_REJECTION_MESSAGES.no_speech)
    setActivity(null)
    setStatus('idle')
  }, [])

  // Spoken question: transcribe, then ask. Resolves to the transcript (or null).
  const askByVoice = useCallback(
    async (audioBlob) => {
      const id = ++requestRef.current
      stopAudio()
      setError(null)
      setHeard(null)
      setStatus('thinking')
      setActivity('transcribing')
      try {
        const result = await api.transcribe(audioBlob)
        if (id !== requestRef.current) return null
        const text = (result.text || '').trim()
        if (result.rejected || text.length < 2) {
          rejectRecording(result.rejected ?? 'no_speech')
          return null
        }
        setHeard(text)
        ask(text)
        return text
      } catch (err) {
        if (id !== requestRef.current) return null
        setError(err.message)
        setActivity(null)
        setStatus('idle')
        return null
      }
    },
    [ask, rejectRecording, stopAudio],
  )

  // Spoken walkthrough of the current lesson. Raising a hand (startListening)
  // or asking stops it, because every new request stops the current audio.
  const explainLesson = useCallback(async () => {
    const id = ++requestRef.current
    stopAudio()
    setError(null)
    setLectureError(null)
    setCaptionIndex(-1)
    setStatus('thinking')
    setActivity('lecture')
    setSpeechKind('lecture')
    try {
      const result = await api.explainLesson({ courseTitle, stepId })
      if (id !== requestRef.current) return
      await speak(result.script, 'explaining', id)
    } catch (err) {
      if (id !== requestRef.current) return
      setLectureError(err.message)
      setActivity(null)
      setSpeechKind(null)
      setStatus('idle')
    }
  }, [courseTitle, stepId, speak, stopAudio])

  const replay = useCallback(() => {
    if (!exchange) return
    const id = ++requestRef.current
    setSpeechKind('answer')
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
    activity,
    heard,
    quota,
    lecturing: speaking && speechKind === 'lecture',
    // Writing the script, then synthesising its voice.
    preparingLecture: speechKind === 'lecture' && (activity === 'lecture' || activity === 'voice'),
    lectureError,
    explainLesson,
    setVoiceOn,
    startListening,
    stop,
    ask,
    askByVoice,
    rejectRecording,
    replay,
  }
}
