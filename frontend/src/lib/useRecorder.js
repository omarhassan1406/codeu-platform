import { useCallback, useEffect, useRef, useState } from 'react'

const MAX_SECONDS = 60
const MIN_BYTES = 1500 // shorter than ~0.2s of Opus: treat as an accidental tap

function pickMimeType() {
  if (typeof MediaRecorder === 'undefined') return null
  const options = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
  return options.find((type) => MediaRecorder.isTypeSupported?.(type)) ?? ''
}

const supported = () =>
  typeof window !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia) && typeof MediaRecorder !== 'undefined'

/**
 * Microphone recording for one question at a time.
 * start() asks for permission and records; stop() resolves to the audio Blob
 * (or null for an empty/accidental recording). Recording stops by itself
 * after MAX_SECONDS.
 */
export function useRecorder() {
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState(null)
  const recorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const resolveRef = useRef(null)

  const release = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    recorderRef.current = null
  }

  useEffect(() => {
    if (!recording) return undefined
    const started = Date.now()
    const timer = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - started) / 1000)
      setSeconds(elapsed)
      if (elapsed >= MAX_SECONDS) recorderRef.current?.stop()
    }, 250)
    return () => window.clearInterval(timer)
  }, [recording])

  // Never leave the microphone on after the component goes away.
  useEffect(() => () => release(), [])

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
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        release()
        setRecording(false)
        resolveRef.current?.(blob.size >= MIN_BYTES ? blob : null)
        resolveRef.current = null
      }
      streamRef.current = stream
      recorderRef.current = recorder
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
          resolve(null)
          return
        }
        resolveRef.current = resolve
        recorder.stop()
      }),
    [],
  )

  return { recording, seconds, error, start, stop, maxSeconds: MAX_SECONDS, supported: supported() }
}
