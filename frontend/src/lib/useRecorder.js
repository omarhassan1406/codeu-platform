import { useCallback, useEffect, useRef, useState } from 'react'

const MAX_SECONDS = 60
const MIN_BYTES = 1500 // shorter than ~0.2s of Opus: treat as an accidental tap
const MIN_SECONDS = 0.6
// Peak RMS (0-1) a recording must reach to count as speech. Silence or a muted
// mic stays far below; normal speech peaks well above. Whisper turns silent
// clips into phrases like "Thank you.", so silent clips are never uploaded.
const SPEECH_LEVEL = 0.02

function pickMimeType() {
  if (typeof MediaRecorder === 'undefined') return null
  const options = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
  return options.find((type) => MediaRecorder.isTypeSupported?.(type)) ?? ''
}

const supported = () =>
  typeof window !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia) && typeof MediaRecorder !== 'undefined'

/**
 * Microphone recording for one question at a time, with a live input level.
 * start() asks for permission and records. stop() resolves to
 * { blob, reason }: blob is null and reason is 'silent' or 'too_short' when
 * the clip should not be sent. Recording stops by itself after MAX_SECONDS.
 */
export function useRecorder() {
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [level, setLevel] = useState(0) // 0-1, for the meter
  const [error, setError] = useState(null)
  const recorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const resolveRef = useRef(null)
  const audioCtxRef = useRef(null)
  const peakRef = useRef(0)
  const startedRef = useRef(0)

  const release = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    recorderRef.current = null
    audioCtxRef.current?.close().catch(() => {})
    audioCtxRef.current = null
  }

  useEffect(() => {
    if (!recording) return undefined
    const timer = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedRef.current) / 1000)
      setSeconds(elapsed)
      if (elapsed >= MAX_SECONDS) recorderRef.current?.stop()
    }, 250)
    return () => window.clearInterval(timer)
  }, [recording])

  // Never leave the microphone on after the component goes away.
  useEffect(() => () => release(), [])

  const meter = (stream) => {
    try {
      const ctx = new AudioContext()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 1024
      ctx.createMediaStreamSource(stream).connect(analyser)
      audioCtxRef.current = ctx
      const samples = new Float32Array(analyser.fftSize)
      const tick = () => {
        if (audioCtxRef.current !== ctx) return
        analyser.getFloatTimeDomainData(samples)
        let sum = 0
        for (const s of samples) sum += s * s
        const rms = Math.sqrt(sum / samples.length)
        peakRef.current = Math.max(peakRef.current, rms)
        setLevel(Math.min(1, rms * 8))
        window.setTimeout(tick, 80)
      }
      tick()
    } catch {
      // No Web Audio: skip metering and assume the clip has sound.
      peakRef.current = 1
    }
  }

  const start = useCallback(async () => {
    setError(null)
    if (!supported()) {
      setError('Voice input is not supported in this browser. Type your question instead.')
      return false
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = pickMimeType()
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      chunksRef.current = []
      peakRef.current = 0
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        const duration = (Date.now() - startedRef.current) / 1000
        const peak = peakRef.current
        release()
        setRecording(false)
        setLevel(0)
        // Silence is checked before size: a quiet mic compresses to a tiny file.
        let reason = null
        if (duration < MIN_SECONDS) reason = 'too_short'
        else if (peak < SPEECH_LEVEL) reason = 'silent'
        else if (blob.size < MIN_BYTES) reason = 'too_short'
        resolveRef.current?.({ blob: reason ? null : blob, reason })
        resolveRef.current = null
      }
      streamRef.current = stream
      recorderRef.current = recorder
      meter(stream)
      startedRef.current = Date.now()
      recorder.start()
      setSeconds(0)
      setRecording(true)
      return true
    } catch (err) {
      release()
      setError(
        err?.name === 'NotAllowedError'
          ? 'Microphone access was blocked. Allow it in the browser to ask by voice.'
          : 'No microphone was found. Type your question instead.',
      )
      return false
    }
  }, [])

  const stop = useCallback(
    () =>
      new Promise((resolve) => {
        const recorder = recorderRef.current
        if (!recorder || recorder.state === 'inactive') {
          resolve({ blob: null, reason: 'too_short' })
          return
        }
        resolveRef.current = resolve
        recorder.stop()
      }),
    [],
  )

  return { recording, seconds, level, error, start, stop, maxSeconds: MAX_SECONDS, supported: supported() }
}
