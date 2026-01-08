import '@testing-library/jest-dom';
import '@testing-library/jest-dom/vitest';

// JSDOM does not implement media playback; mock the methods we call in keep-awake fallback.
Object.defineProperty(HTMLMediaElement.prototype, 'play', {
  configurable: true,
  // Simulate autoplay being blocked; our app should handle this gracefully.
  value: () => Promise.reject(new Error('NotAllowedError')),
});

Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
  configurable: true,
  value: () => undefined,
});
