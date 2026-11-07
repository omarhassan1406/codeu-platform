import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alignment, Fit, Layout, Rive, useRive } from '@rive-app/react-canvas'

// The exported .riv runs a ~2s branded splash on entry of its state machine,
// which would flash on every refresh. Playing its linear animations directly
// renders the professor instantly; suppress the runtime's deprecation notices
// for that supported-but-legacy path.
Rive.suppressDeprecationWarnings = ['animations-param', 'animation-names', 'names-array']

const STATUS_ANIMATIONS = {
  idle: 'idle with blinking',
  listening: 'listening',
  thinking: 'thinking',
  talking: 'talking',
  explaining: 'explaining',
}
const IDLE_ANIMATION = STATUS_ANIMATIONS.idle

function FallbackAvatar({ status }) {
  const active = status !== 'idle'

  return (
    <div className="relative flex h-full w-full items-center justify-center">
      <div
        className={`absolute h-[55%] w-[55%] rounded-full bg-ember-500/20 blur-3xl ${
          active ? 'status-pulse' : 'opacity-60'
        }`}
      />
      <div className="absolute h-[68%] w-[68%] rounded-full border border-white/[0.05]" />
      <div className="absolute h-[82%] w-[82%] rounded-full border border-dashed border-ember-500/15" />

      <svg
        className="bot-float relative z-10 h-[92%] w-[92%] max-h-[290px] max-w-[290px] drop-shadow-[0_30px_45px_rgba(255,87,34,0.22)]"
        viewBox="0 0 240 240"
        role="img"
        aria-label="CodeU robot professor"
      >
        <defs>
          <linearGradient id="codeu-head" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#FF8A65" />
            <stop offset="55%" stopColor="#FF5722" />
            <stop offset="100%" stopColor="#E64A19" />
          </linearGradient>
          <linearGradient id="codeu-visor" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#242A34" />
            <stop offset="100%" stopColor="#0D0F14" />
          </linearGradient>
          <radialGradient id="codeu-eye" cx="50%" cy="35%" r="70%">
            <stop offset="0%" stopColor="#FFFFFF" />
            <stop offset="70%" stopColor="#FFD9C9" />
            <stop offset="100%" stopColor="#FFB199" />
          </radialGradient>
        </defs>

        <ellipse cx="120" cy="218" rx="62" ry="10" fill="rgba(0,0,0,0.45)" />

        <line x1="120" y1="36" x2="120" y2="16" stroke="#FFB199" strokeWidth="4" strokeLinecap="round" />
        <circle cx="120" cy="12" r="7" fill="#FF7043" />

        <rect x="20" y="96" width="22" height="52" rx="11" fill="#E64A19" />
        <rect x="198" y="96" width="22" height="52" rx="11" fill="#E64A19" />

        <rect x="40" y="38" width="160" height="156" rx="54" fill="url(#codeu-head)" />
        <rect x="58" y="62" width="124" height="108" rx="42" fill="url(#codeu-visor)" />

        <g className="bot-eye">
          <ellipse cx="96" cy="110" rx="14" ry="17" fill="url(#codeu-eye)" />
          <ellipse cx="148" cy="110" rx="14" ry="17" fill="url(#codeu-eye)" />
          <circle cx="99" cy="113" r="5" fill="#1A1D24" />
          <circle cx="151" cy="113" r="5" fill="#1A1D24" />
          <circle cx="102" cy="108" r="2" fill="#FFFFFF" />
          <circle cx="154" cy="108" r="2" fill="#FFFFFF" />
        </g>

        <path
          d="M104 140c5 7 27 7 32 0"
          fill="none"
          stroke="#FF9A76"
          strokeWidth="5"
          strokeLinecap="round"
        />

        <text
          x="120"
          y="187"
          textAnchor="middle"
          fill="#FFE1D6"
          fontSize="10"
          fontFamily="JetBrains Mono, monospace"
          fontWeight="700"
          letterSpacing="1"
        >
          &lt;CODEU&gt;
        </text>
      </svg>
    </div>
  )
}

function RiveStage({ src, artboard, status, onLoadError }) {
  const [loaded, setLoaded] = useState(false)
  const handleLoad = useCallback(() => setLoaded(true), [])

  const riveParams = useMemo(
    () => ({
      src,
      ...(artboard ? { artboard } : {}),
      animations: IDLE_ANIMATION,
      autoplay: true,
      layout: new Layout({ fit: Fit.Contain, alignment: Alignment.Center }),
      onLoad: handleLoad,
      onLoadError,
    }),
    [src, artboard, handleLoad, onLoadError],
  )

  const { rive, RiveComponent } = useRive(riveParams)
  const [revealed, setRevealed] = useState(false)

  useEffect(() => {
    if (!rive || !loaded) return
    rive.play(STATUS_ANIMATIONS[status] ?? IDLE_ANIMATION)
  }, [rive, loaded, status])

  useEffect(() => {
    if (!rive || !loaded) return undefined

    let revealFrame = 0
    const sizeFrame = window.requestAnimationFrame(() => {
      rive.resizeDrawingSurfaceToCanvas()
      revealFrame = window.requestAnimationFrame(() => setRevealed(true))
    })

    return () => {
      window.cancelAnimationFrame(sizeFrame)
      window.cancelAnimationFrame(revealFrame)
    }
  }, [rive, loaded])

  return (
    <div
      className={`absolute inset-0 transition-opacity duration-500 ${
        revealed ? 'opacity-100' : 'opacity-0'
      }`}
      aria-hidden={revealed ? undefined : 'true'}
    >
      <RiveComponent aria-label="CodeU AI professor avatar" className="h-full w-full" />
    </div>
  )
}

export default function RiveAvatar({
  status = 'idle',
  src = '/codeu_avatar.riv',
  artboardName = 'full body',
  className = '',
}) {
  const [asset, setAsset] = useState(null)
  const [failedKey, setFailedKey] = useState(null)
  const [retriedArtboardKey, setRetriedArtboardKey] = useState(null)

  const assetState = asset?.src === src ? asset.status : 'checking'
  const explicitKey = artboardName ? `${src}::${artboardName}` : null
  const useDefaultArtboard = explicitKey !== null && retriedArtboardKey === explicitKey
  const activeArtboard = artboardName && !useDefaultArtboard ? artboardName : undefined
  const stageKey = `${src}::${activeArtboard ?? '__default__'}`
  const loadFailed = failedKey === stageKey

  useEffect(() => {
    let cancelled = false

    fetch(src, { method: 'HEAD' })
      .then((response) => {
        if (!cancelled) {
          setAsset({ src, status: response.ok ? 'ready' : 'missing' })
        }
      })
      .catch(() => {
        if (!cancelled) setAsset({ src, status: 'missing' })
      })

    return () => {
      cancelled = true
    }
  }, [src])

  const handleLoadError = useCallback(() => {
    if (explicitKey && retriedArtboardKey !== explicitKey) {
      setRetriedArtboardKey(explicitKey)
      return
    }
    setFailedKey(stageKey)
  }, [explicitKey, retriedArtboardKey, stageKey])

  return (
    <div
      className={`relative flex items-center justify-center overflow-hidden ${className}`}
      data-avatar-status={status}
    >
      {assetState === 'ready' && !loadFailed ? (
        // useRive only rebuilds on a fresh canvas, so retries remount via key.
        <RiveStage
          key={stageKey}
          src={src}
          artboard={activeArtboard}
          status={status}
          onLoadError={handleLoadError}
        />
      ) : assetState === 'checking' ? null : (
        <FallbackAvatar status={status} />
      )}
    </div>
  )
}
