import '@testing-library/jest-dom/vitest';

// jsdom doesn't implement ResizeObserver; Radix UI relies on it for popper sizing.
class ResizeObserverMock {
  observe(_target: Element) {}
  unobserve(_target: Element) {}
  disconnect() {}
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).ResizeObserver = ResizeObserverMock;

