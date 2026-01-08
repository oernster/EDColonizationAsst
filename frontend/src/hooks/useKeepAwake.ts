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
  // window.isSecureContext is the most reliable check.
  return typeof window !== 'undefined' && (window.isSecureContext ?? false);
};

// Minimal no-sleep video: a tiny, silent 1x1 mp4 (base64) that loops.
// Source: generated blank frame mp4; kept small to reduce bandwidth.
// Note: even if supported, browsers require a user gesture to start playback
// in most cases, hence the "needs-user-gesture" state.
const TINY_MP4_DATA_URL =
  'data:video/mp4;base64,AAAAHGZ0eXBtcDQyAAAAAG1wNDJtcDQxaXNvbThtcDQyAAACAGlzb21pc28yYXZjMW1wNDEAAABsbW9vdgAAAGxtdmhkAAAAANr3xWna98VpAAABAAABR0gAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAABR0cmFrAAAAXHRraGQAAAAD2vfFadr3xWkAAAABAAAAAAAAAUdIAAEAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAABAAAAAQAAAAAAAEAAQAAAAEAAAAAAAAAAAAAAAAAAAAAACR0a2hkAAAAA9r3xWna98VpAAAAAQAAAAAAAAFHSAABAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAABAAAAAQAAAAAAAEAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAABdHJha2QAAAAcZHRzZAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAEAAAABAAAAAQAAAAAAAAABAAAAAQAAAAAAAAAA';

const createHiddenVideoElement = (): HTMLVideoElement => {
  const video = document.createElement('video');
  video.setAttribute('playsinline', 'true');
  video.muted = true;
  video.loop = true;
  video.preload = 'auto';

  // Prefer a codec-free canvas capture stream where supported.
  // This avoids relying on MP4 decode support on devices/browsers.
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

      // Stash cleanup metadata on the element.
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

  // Keep it totally invisible and non-interactive.
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
  const fallbackVideoRef = useRef<HTMLVideoElement | null>(null);
  const gestureListenerBoundRef = useRef(false);

  const wakeLockPossible = useMemo(() => {
    return canUseWakeLock() && isSecureContextForWakeLock();
  }, []);

  const releaseWakeLock = useCallback(async () => {
    try {
      if (sentinelRef.current && !sentinelRef.current.released) {
        await sentinelRef.current.release();
      }
    } catch {
      // Best-effort.
    } finally {
      sentinelRef.current = null;
    }
  }, []);

  const stopFallbackVideo = useCallback(() => {
    const video = fallbackVideoRef.current;
    if (!video) return;

    // If we used a canvas capture stream, stop it.
    try {
      const meta = (video as unknown as { _edcaKeepAwake?: { intervalId: number; stream: MediaStream } })._edcaKeepAwake;
      if (meta) {
        try {
          window.clearInterval(meta.intervalId);
        } catch {
          // ignore
        }
        try {
          meta.stream.getTracks().forEach((t) => t.stop());
        } catch {
          // ignore
        }
        try {
          (video as unknown as { srcObject: MediaStream | null }).srcObject = null;
        } catch {
          // ignore
        }
        delete (video as unknown as { _edcaKeepAwake?: unknown })._edcaKeepAwake;
      }
    } catch {
      // ignore
    }

    try {
      video.pause();
    } catch {
      // ignore
    }
    try {
      video.remove();
    } catch {
      // ignore
    }
    fallbackVideoRef.current = null;
  }, []);

  const stopAll = useCallback(async () => {
    await releaseWakeLock();
    stopFallbackVideo();
    setStatus({ state: 'off', message: 'Off' });
  }, [releaseWakeLock, stopFallbackVideo]);

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
      setStatus({ state: 'active', mode: 'wake-lock', message: 'Keep-awake active (Wake Lock)' });
      return true;
    } catch (err) {
      setStatus({ state: 'error', message: 'Failed to acquire Wake Lock' });
      return false;
    }
  }, []);

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
      return true;
    } catch {
      // Autoplay blocked until user gesture.
      setStatus({ state: 'needs-user-gesture', message: 'Tap once to enable keep-awake' });
      return false;
    }
  }, [allowFallbackVideo]);

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

  // Attempt to enable keep-awake *immediately* in a user-gesture call stack.
  // This can allow the fallback media to start without requiring an extra tap
  // (depends on browser autoplay policies).
  const enableFromUserGesture = useCallback(() => {
    // IMPORTANT: avoid awaiting before trying to start playback; otherwise the
    // browser may no longer consider this a user gesture.

    if (wakeLockPossible) {
      return requestWakeLock().then((ok) => {
        if (ok) {
          stopFallbackVideo();
          return true;
        }
        // Best-effort cleanup, but do not await.
        void releaseWakeLock();
        return startFallbackVideo();
      });
    }

    void releaseWakeLock();
    return startFallbackVideo();
  }, [wakeLockPossible, requestWakeLock, stopFallbackVideo, releaseWakeLock, startFallbackVideo]);

  // If fallback needs a gesture, bind one-time listeners that attempt to start it.
  useEffect(() => {
    if (!enabled) return;

    const shouldArmGesture =
      status.state === 'needs-user-gesture' && allowFallbackVideo && !wakeLockPossible;
    if (!shouldArmGesture) return;

    if (gestureListenerBoundRef.current) return;
    gestureListenerBoundRef.current = true;

    const onGesture = async () => {
      await startFallbackVideo();
      // If it succeeded, we can remove listeners.
      if (fallbackVideoRef.current) {
        try {
          document.removeEventListener('click', onGesture, true);
          document.removeEventListener('touchstart', onGesture, true);
          document.removeEventListener('keydown', onGesture, true);
        } catch {
          // ignore
        }
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
  }, [enabled, status.state, allowFallbackVideo, wakeLockPossible, startFallbackVideo]);

  // Re-acquire on visibility change.
  useEffect(() => {
    if (!enabled) return;

    const onVisibility = async () => {
      if (document.visibilityState === 'visible') {
        await ensureEnabled();
      } else {
        // Release wake lock to be polite; keep fallback paused to avoid background playback.
        await releaseWakeLock();
        if (fallbackVideoRef.current) {
          try {
            fallbackVideoRef.current.pause();
          } catch {
            // ignore
          }
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

  return {
    status,
    ensureEnabled,
    enableFromUserGesture,
    stopAll,
    wakeLockPossible,
    secureContext: isSecureContextForWakeLock(),
  };
};

