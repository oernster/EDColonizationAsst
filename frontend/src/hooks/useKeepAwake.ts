import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// Types are not always present in TS lib.dom depending on config.
type WakeLockSentinelLike = {
  released: boolean;
  release: () => Promise<void>;
  addEventListener?: (type: string, listener: () => void) => void;
  removeEventListener?: (type: string, listener: () => void) => void;
};

type WakeLockLike = {
  request: (type: 'screen') => Promise<WakeLockSentinelLike>;
};

export type KeepAwakeMode = 'wake-lock' | 'fallback-video' | 'off';

export type KeepAwakeStatus =
  | { state: 'off'; message: string }
  | { state: 'active'; mode: KeepAwakeMode; message: string }
  | { state: 'needs-user-gesture'; message: string }
  | { state: 'unsupported'; message: string }
  | { state: 'error'; message: string };

type Options = {
  enabled: boolean;
  // When Wake Lock isn't available (e.g. HTTP LAN URL), we can fall back to a
  // hidden looping video. Autoplay restrictions mean it needs a user gesture.
  allowFallbackVideo: boolean;
};

const canUseWakeLock = (): boolean => {
  const nav = navigator as unknown as { wakeLock?: WakeLockLike };
  return typeof window !== 'undefined' && !!nav.wakeLock && typeof nav.wakeLock.request === 'function';
};

const isSecureContextForWakeLock = (): boolean => {
  // Wake Lock requires a secure context (https or localhost).
  return typeof window !== 'undefined' && (window.isSecureContext ?? false);
};

/**
 * Generic "tablet-ish" heuristic.
 * We keep this conservative:
 * - Prefer UA-CH mobile flag (where available)
 * - Otherwise rely on coarse pointer / touch / screen size
 */
const isMobileOrTabletLike = (): boolean => {
  if (typeof window === 'undefined') return false;

  const nav = navigator as unknown as { userAgentData?: { mobile?: boolean } };
  if (typeof nav.userAgentData?.mobile === 'boolean') return nav.userAgentData.mobile;

  const hasTouch =
    'ontouchstart' in window || (navigator.maxTouchPoints ?? 0) > 0;

  const coarsePointer = typeof window.matchMedia === 'function'
    ? window.matchMedia('(pointer: coarse)').matches
    : false;

  // Use viewport as a soft hint (avoids classifying small desktop windows).
  const minDim = Math.min(window.screen?.width ?? 0, window.screen?.height ?? 0);
  const screenLooksHandheld = minDim > 0 && minDim <= 1400;

  return (hasTouch || coarsePointer) && screenLooksHandheld;
};

const TINY_MP4_DATA_URL =
  'data:video/mp4;base64,AAAAHGZ0eXBtcDQyAAAAAG1wNDJtcDQxaXNvbThtcDQyAAACAGlzb21pc28yYXZjMW1wNDEAAABsbW9vdgAAAGxtdmhkAAAAANr3xWna98VpAAABAAABR0gAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAABR0cmFrAAAAXHRraGQAAAAD2vfFadr3xWkAAAABAAAAAAAAAUdIAAEAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAABAAAAAQAAAAAAAEAAQAAAAEAAAAAAAAAAAAAAAAAAAAAACR0a2hkAAAAA9r3xWna98VpAAAAAQAAAAAAAAFHSAABAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAABAAAAAQAAAAAAAEAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAABdHJha2QAAAAcZHRzZAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAAAAAAA';

const createHiddenVideoElement = (): HTMLVideoElement => {
  const video = document.createElement('video');
  video.setAttribute('playsinline', 'true');
  video.muted = true;
  video.loop = true;
  video.preload = 'auto';

  // Prefer canvas capture stream (codec-free) and *force* frame production.
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 1;
    canvas.height = 1;

    const captureStream = (canvas as unknown as { captureStream?: (fps?: number) => MediaStream }).captureStream;
    if (typeof captureStream === 'function' && 'srcObject' in video) {
      const stream = captureStream.call(canvas, 1);
      (video as unknown as { srcObject: MediaStream | null }).srcObject = stream;

      const ctx = canvas.getContext('2d');
      let on = false;
      const intervalId = window.setInterval(() => {
        if (!ctx) return;
        on = !on;
        ctx.fillStyle = on ? '#000' : '#001';
        ctx.fillRect(0, 0, 1, 1);
      }, 1000);

      (video as unknown as { _edcaKeepAwake?: { intervalId: number; stream: MediaStream } })._edcaKeepAwake = {
        intervalId,
        stream,
      };
    } else {
      video.src = TINY_MP4_DATA_URL;
    }
  } catch {
    video.src = TINY_MP4_DATA_URL;
  }

  Object.assign(video.style, {
    position: 'fixed',
    width: '1px',
    height: '1px',
    opacity: '0',
    pointerEvents: 'none',
    left: '0',
    top: '0',
    zIndex: '-1',
  } as Partial<CSSStyleDeclaration>);

  return video;
};

export const useKeepAwake = ({ enabled, allowFallbackVideo }: Options) => {
  const [status, setStatus] = useState<KeepAwakeStatus>({ state: 'off', message: 'Off' });

  const sentinelRef = useRef<WakeLockSentinelLike | null>(null);
  const sentinelReleaseListenerRef = useRef<(() => void) | null>(null);

  const fallbackVideoRef = useRef<HTMLVideoElement | null>(null);
  const gestureListenerBoundRef = useRef(false);

  // Optional 2 (device-agnostic): compositor heartbeat while Wake Lock is active,
  // but only on mobile/tablet-like environments to avoid touching desktop unnecessarily.
  const enableHeartbeatRef = useRef(false);
  const repaintHeartbeatRef = useRef<number | null>(null);

  useEffect(() => {
    enableHeartbeatRef.current = isMobileOrTabletLike();
  }, []);

  const startRepaintHeartbeat = useCallback(() => {
    if (!enableHeartbeatRef.current) return;
    if (repaintHeartbeatRef.current !== null) return;

    repaintHeartbeatRef.current = window.setInterval(() => {
      try {
        document.body.style.transform = `translateZ(${Math.random() * 0.0001}px)`;
      } catch {
        // ignore
      }
    }, 2000);
  }, []);

  const stopRepaintHeartbeat = useCallback(() => {
    if (repaintHeartbeatRef.current === null) return;
    try {
      window.clearInterval(repaintHeartbeatRef.current);
    } catch {
      // ignore
    } finally {
      repaintHeartbeatRef.current = null;
    }
    try {
      document.body.style.transform = '';
    } catch {
      // ignore
    }
  }, []);

  const wakeLockPossible = useMemo(() => {
    return canUseWakeLock() && isSecureContextForWakeLock();
  }, []);

  const releaseWakeLock = useCallback(async () => {
    try {
      // Remove any release listener we attached.
      if (sentinelRef.current && sentinelReleaseListenerRef.current) {
        try {
          sentinelRef.current.removeEventListener?.('release', sentinelReleaseListenerRef.current);
        } catch {
          // ignore
        }
      }
      sentinelReleaseListenerRef.current = null;

      if (sentinelRef.current && !sentinelRef.current.released) {
        await sentinelRef.current.release();
      }
    } catch {
      // Best-effort.
    } finally {
      sentinelRef.current = null;
      stopRepaintHeartbeat();
    }
  }, [stopRepaintHeartbeat]);

  const stopFallbackVideo = useCallback(() => {
    const video = fallbackVideoRef.current;
    if (!video) return;

    try {
      const meta =
        (video as unknown as { _edcaKeepAwake?: { intervalId: number; stream: MediaStream } })
          ._edcaKeepAwake;

      if (meta) {
        try { window.clearInterval(meta.intervalId); } catch {}
        try { meta.stream.getTracks().forEach((t) => t.stop()); } catch {}
        try { (video as unknown as { srcObject: MediaStream | null }).srcObject = null; } catch {}
        delete (video as unknown as { _edcaKeepAwake?: unknown })._edcaKeepAwake;
      }
    } catch {
      // ignore
    }

    try { video.pause(); } catch {}
    try { video.remove(); } catch {}
    fallbackVideoRef.current = null;
  }, []);

  const stopAll = useCallback(async () => {
    await releaseWakeLock();
    stopFallbackVideo();
    stopRepaintHeartbeat();
    setStatus({ state: 'off', message: 'Off' });
  }, [releaseWakeLock, stopFallbackVideo, stopRepaintHeartbeat]);

  const requestWakeLock = useCallback(async () => {
    const nav = navigator as unknown as { wakeLock?: WakeLockLike };
    if (!nav.wakeLock) {
      setStatus({ state: 'unsupported', message: 'Wake Lock API not available' });
      return false;
    }
    if (!isSecureContextForWakeLock()) {
      setStatus({ state: 'unsupported', message: 'Wake Lock requires HTTPS/localhost' });
      return false;
    }

    try {
      const sentinel = await nav.wakeLock.request('screen');
      sentinelRef.current = sentinel;

      // If the OS releases the lock, reflect that and allow re-acquire on visibility changes.
      const onRelease = () => {
        // Only update if we still consider keep-awake enabled.
        setStatus({ state: 'error', message: 'Wake Lock was released by the system' });
        stopRepaintHeartbeat();
      };
      sentinelReleaseListenerRef.current = onRelease;
      sentinel.addEventListener?.('release', onRelease);

      setStatus({ state: 'active', mode: 'wake-lock', message: 'Keep-awake active (Wake Lock)' });

      // Optional 2: heartbeat while Wake Lock is active.
      startRepaintHeartbeat();

      return true;
    } catch {
      setStatus({ state: 'error', message: 'Failed to acquire Wake Lock' });
      return false;
    }
  }, [startRepaintHeartbeat, stopRepaintHeartbeat]);

  const startFallbackVideo = useCallback(async () => {
    if (!allowFallbackVideo) {
      setStatus({ state: 'unsupported', message: 'Keep-awake fallback disabled' });
      return false;
    }

    if (!fallbackVideoRef.current) {
      fallbackVideoRef.current = createHiddenVideoElement();
      document.body.appendChild(fallbackVideoRef.current);
    }
    const video = fallbackVideoRef.current;

    try {
      await video.play();
      setStatus({ state: 'active', mode: 'fallback-video', message: 'Keep-awake active (Fallback)' });
      // Fallback already produces frames; heartbeat unnecessary.
      stopRepaintHeartbeat();
      return true;
    } catch {
      setStatus({ state: 'needs-user-gesture', message: 'Tap once to enable keep-awake' });
      stopRepaintHeartbeat();
      return false;
    }
  }, [allowFallbackVideo, stopRepaintHeartbeat]);

  const ensureEnabled = useCallback(async () => {
    if (!enabled) {
      await stopAll();
      return;
    }

    // Prefer Wake Lock when possible.
    if (wakeLockPossible) {
      const ok = await requestWakeLock();
      if (ok) {
        stopFallbackVideo();
        return;
      }
    }

    // Otherwise, fall back.
    await releaseWakeLock();
    await startFallbackVideo();
  }, [enabled, wakeLockPossible, requestWakeLock, startFallbackVideo, releaseWakeLock, stopAll, stopFallbackVideo]);

  // Attempt to enable within a user-gesture call stack.
  // Avoid "await" before trying to play media, as it can lose the gesture.
  const enableFromUserGesture = useCallback(() => {
    if (!enabled) return Promise.resolve(false);

    if (wakeLockPossible) {
      return requestWakeLock().then((ok) => {
        if (ok) {
          stopFallbackVideo();
          return true;
        }
        void releaseWakeLock();
        return startFallbackVideo();
      });
    }

    void releaseWakeLock();
    return startFallbackVideo();
  }, [enabled, wakeLockPossible, requestWakeLock, stopFallbackVideo, releaseWakeLock, startFallbackVideo]);

  // Bind "tap anywhere once" listeners whenever fallback playback is blocked.
  useEffect(() => {
    if (!enabled) return;

    const shouldArmGesture = status.state === 'needs-user-gesture' && allowFallbackVideo;
    if (!shouldArmGesture) return;
    if (gestureListenerBoundRef.current) return;
    gestureListenerBoundRef.current = true;

    const onGesture = async () => {
      const ok = await startFallbackVideo();
      if (ok) {
        document.removeEventListener('click', onGesture, true);
        document.removeEventListener('touchstart', onGesture, true);
        document.removeEventListener('keydown', onGesture, true);
        gestureListenerBoundRef.current = false;
      }
    };

    document.addEventListener('click', onGesture, true);
    document.addEventListener('touchstart', onGesture, true);
    document.addEventListener('keydown', onGesture, true);

    return () => {
      gestureListenerBoundRef.current = false;
      document.removeEventListener('click', onGesture, true);
      document.removeEventListener('touchstart', onGesture, true);
      document.removeEventListener('keydown', onGesture, true);
    };
  }, [enabled, status.state, allowFallbackVideo, startFallbackVideo]);

  // Re-acquire on visibility change.
  useEffect(() => {
    if (!enabled) return;

    const onVisibility = async () => {
      if (document.visibilityState === 'visible') {
        await ensureEnabled();
      } else {
        // Be polite when hidden.
        await releaseWakeLock();
        if (fallbackVideoRef.current) {
          try { fallbackVideoRef.current.pause(); } catch {}
        }
      }
    };

    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [enabled, ensureEnabled, releaseWakeLock]);

  // Main on/off effect.
  useEffect(() => {
    void ensureEnabled();
    return () => {
      void stopAll();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  // Defensive: stop heartbeat if we’re no longer in wake-lock mode.
  useEffect(() => {
    if (!enabled) {
      stopRepaintHeartbeat();
      return;
    }
    if (status.state === 'active' && 'mode' in status && status.mode === 'wake-lock') return;
    stopRepaintHeartbeat();
  }, [enabled, status, stopRepaintHeartbeat]);

  return {
    status,
    ensureEnabled,
    enableFromUserGesture,
    stopAll,
    wakeLockPossible,
    secureContext: isSecureContextForWakeLock(),
  };
};
