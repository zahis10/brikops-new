/**
 * BATCH fix-annotation-ios-text (2026-07-13) — V1 unit probe.
 *
 * Verifies the pending-text flush semantics in PhotoAnnotation:
 *   P1  label-only session + שמור  → onSave(File, true)   [was (null,false) — RC1]
 *   P2  editing an existing label + שמור → REPLACE (stroke count preserved)
 *   P3  typed-but-uncommitted label + X → confirm modal (no silent close)
 *   P4  empty pending input + X → immediate close (unchanged behavior)
 *
 * Tooling: CRA jest+jsdom (craco test) — no new dependencies.
 * jsdom has no canvas/Image/createObjectURL; all are mocked below.
 * canvas.toBlob is polyfilled to synchronously yield a fake JPEG blob.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import PhotoAnnotation from '../PhotoAnnotation';

// React 19: opt this jsdom suite into act() support (RTL normally does this).
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// ---------------------------------------------------------------- mocks

// Log of 2d-context calls so tests can count fillText per redraw cycle.
let ctxCalls = [];

function makeCtxStub() {
  return new Proxy(
    {},
    {
      get(target, prop) {
        if (prop === 'measureText') {
          return () => ({
            width: 40,
            actualBoundingBoxAscent: 10,
            actualBoundingBoxDescent: 4,
          });
        }
        if (prop === 'canvas') return undefined;
        if (!(prop in target)) {
          target[prop] = (...args) => {
            ctxCalls.push({ method: prop, args });
          };
        }
        return target[prop];
      },
      set(target, prop, value) {
        target[prop] = value; // font, fillStyle, lineWidth, etc.
        return true;
      },
    }
  );
}

beforeAll(() => {
  window.URL.createObjectURL = jest.fn(() => 'blob:mock-url');
  window.URL.revokeObjectURL = jest.fn();

  // Image mock: fires onload on next macrotask with fixed natural size.
  class MockImage {
    constructor() {
      this.naturalWidth = 800;
      this.naturalHeight = 600;
      this.width = 800;
      this.height = 600;
      this.onload = null;
      this.onerror = null;
    }
    set src(_v) {
      setTimeout(() => {
        if (this.onload) this.onload();
      }, 0);
    }
  }
  window.Image = MockImage;

  HTMLCanvasElement.prototype.getContext = function () {
    if (!this.__ctx) this.__ctx = makeCtxStub();
    return this.__ctx;
  };
  HTMLCanvasElement.prototype.toBlob = function (cb) {
    cb(new Blob(['fake-jpeg'], { type: 'image/jpeg' }));
  };
});

// ---------------------------------------------------------------- helpers

const flushLoad = () => act(async () => new Promise((r) => setTimeout(r, 20)));

function makeFile() {
  return new File(['fake'], 'photo.jpg', { type: 'image/jpeg' });
}

function q(sel) {
  return document.body.querySelector(sel);
}

function buttonByText(text) {
  return [...document.body.querySelectorAll('button')].find(
    (b) => b.textContent.trim() === text
  );
}

function click(el) {
  act(() => {
    el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
  });
}

function canvasTap(x, y) {
  const canvas = q('canvas');
  act(() => {
    canvas.dispatchEvent(
      new MouseEvent('mousedown', { bubbles: true, clientX: x, clientY: y })
    );
    canvas.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: x, clientY: y })
    );
  });
}

function typeIntoPendingInput(value) {
  const input = q('input[placeholder="תווית קצרה (עד 30 תווים)"]');
  expect(input).toBeTruthy();
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    'value'
  ).set;
  act(() => {
    setter.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  return input;
}

async function mount(props) {
  const host = document.createElement('div');
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(<PhotoAnnotation {...props} />);
  });
  await flushLoad(); // image onload → canvas sized → loaded=true
  return {
    root,
    host,
    unmount: async () => {
      await act(async () => root.unmount());
      host.remove();
    },
  };
}

function enterTextMode() {
  const tBtn = [...document.body.querySelectorAll('button')].find(
    (b) => b.textContent.trim() === 'T'
  );
  expect(tBtn).toBeTruthy();
  click(tBtn);
}

afterEach(() => {
  ctxCalls = [];
  document.body.innerHTML = '';
});

// ---------------------------------------------------------------- tests

test('P1: label-only pending text is flushed on save → onSave(File, true), NOT (null, false)', async () => {
  const onSave = jest.fn();
  const onDiscard = jest.fn();
  const m = await mount({ imageFile: makeFile(), onSave, onDiscard });

  enterTextMode();
  canvasTap(100, 100); // opens pending text overlay
  typeIntoPendingInput('סדק בקיר');

  click(buttonByText('שמור'));
  await flushLoad();

  expect(onSave).toHaveBeenCalledTimes(1);
  const [file, hasAnnotations] = onSave.mock.calls[0];
  expect(hasAnnotations).toBe(true);
  expect(file).toBeInstanceOf(File);
  expect(file.type).toBe('image/jpeg');
  // The regression path was onSave(null, false):
  expect(file).not.toBeNull();

  await m.unmount();
});

test('P2: saving while editing an existing label REPLACES it (no duplicate stroke)', async () => {
  const onSave = jest.fn();
  const m = await mount({ imageFile: makeFile(), onSave, onDiscard: jest.fn() });

  enterTextMode();
  canvasTap(100, 100);
  typeIntoPendingInput('תווית');
  click(buttonByText('אישור')); // commit label #1 (existing flow)

  // Tap the same spot → hit-test opens EDIT overlay (editingIndex=0).
  canvasTap(100, 100);
  const input = q('input[placeholder="תווית קצרה (עד 30 תווים)"]');
  expect(input).toBeTruthy();
  expect(input.value).toBe('תווית'); // prefilled = edit mode confirmed
  typeIntoPendingInput('תווית מעודכנת');

  ctxCalls = []; // isolate the flush redraw triggered by save
  click(buttonByText('שמור'));
  await flushLoad();

  // The flush redraw draws the final stroke array. REPLACE → exactly one
  // text label rendered per redraw cycle; APPEND bug would render two.
  const clearIdxs = ctxCalls
    .map((c, i) => (c.method === 'clearRect' ? i : -1))
    .filter((i) => i >= 0);
  expect(clearIdxs.length).toBeGreaterThan(0);
  const lastCycle = ctxCalls.slice(clearIdxs[clearIdxs.length - 1]);
  const fillTexts = lastCycle.filter((c) => c.method === 'fillText');
  expect(fillTexts.length).toBe(1);
  expect(fillTexts[0].args[0]).toBe('תווית מעודכנת');

  expect(onSave).toHaveBeenCalledTimes(1);
  expect(onSave.mock.calls[0][1]).toBe(true);

  await m.unmount();
});

test('P5: commit (אישור) immediately followed by שמור → no double-commit, single label', async () => {
  const onSave = jest.fn();
  const m = await mount({ imageFile: makeFile(), onSave, onDiscard: jest.fn() });

  enterTextMode();
  canvasTap(100, 100);
  typeIntoPendingInput('תווית אחת');
  click(buttonByText('אישור')); // commit → pendingText cleared (ref synced via effect inside act)

  ctxCalls = []; // isolate the save-path redraws
  click(buttonByText('שמור'));
  await flushLoad();

  expect(onSave).toHaveBeenCalledTimes(1);
  expect(onSave.mock.calls[0][1]).toBe(true);

  // No pending flush should have run — the label must appear exactly once
  // in the final redraw cycle (a stale-ref double-commit would render two).
  const clearIdxs = ctxCalls
    .map((c, i) => (c.method === 'clearRect' ? i : -1))
    .filter((i) => i >= 0);
  if (clearIdxs.length > 0) {
    const lastCycle = ctxCalls.slice(clearIdxs[clearIdxs.length - 1]);
    const fillTexts = lastCycle.filter((c) => c.method === 'fillText');
    expect(fillTexts.length).toBe(1);
    expect(fillTexts[0].args[0]).toBe('תווית אחת');
  }

  await m.unmount();
});

test('P3: typed-but-uncommitted label + X → confirm modal, no silent close', async () => {
  const onSave = jest.fn();
  const onDiscard = jest.fn();
  const m = await mount({ imageFile: makeFile(), onSave, onDiscard });

  enterTextMode();
  canvasTap(100, 100);
  typeIntoPendingInput('טקסט שלא אושר');

  click(q('button[aria-label="סגור ללא שמירה"]'));

  expect(onDiscard).not.toHaveBeenCalled();
  expect(onSave).not.toHaveBeenCalled();
  expect(document.body.textContent).toContain('לבטל את כל השינויים ולסגור?');

  await m.unmount();
});

test('P6 (batch-2 E8/E9): visualViewport resize compresses editor root; restore clears it', async () => {
  // Minimal visualViewport mock — must exist BEFORE mount (the effect
  // captures window.visualViewport once per loaded-cycle).
  const listeners = {};
  const vv = {
    width: 1024,
    height: window.innerHeight, // full → keyboard closed
    offsetTop: 0,
    addEventListener: (type, fn) => {
      (listeners[type] = listeners[type] || []).push(fn);
    },
    removeEventListener: (type, fn) => {
      listeners[type] = (listeners[type] || []).filter((f) => f !== fn);
    },
  };
  const fire = (type) =>
    act(() => {
      (listeners[type] || []).forEach((fn) => fn());
    });
  window.visualViewport = vv;
  window.scrollTo = jest.fn();

  try {
    const m = await mount({
      imageFile: makeFile(),
      onSave: jest.fn(),
      onDiscard: jest.fn(),
    });
    const root = q('div.fixed.inset-0[dir="rtl"]');
    expect(root).toBeTruthy();
    expect(listeners.resize?.length).toBeGreaterThan(0);
    expect(listeners.scroll?.length).toBeGreaterThan(0);

    // Keyboard opens: vv shrinks + OS pans.
    vv.height = 400;
    vv.offsetTop = 25;
    fire('resize');
    expect(root.style.height).toBe('400px');
    expect(root.style.transform).toBe('translateY(25px)');

    // OS pan without resize → scroll event updates the transform.
    vv.offsetTop = 40;
    fire('scroll');
    expect(root.style.transform).toBe('translateY(40px)');

    // E9: residual document scroll snaps back to 0.
    Object.defineProperty(window, 'scrollY', { value: 33, configurable: true });
    fire('scroll');
    expect(window.scrollTo).toHaveBeenCalledWith(0, 0);
    Object.defineProperty(window, 'scrollY', { value: 0, configurable: true });

    // Keyboard closes: full height restores ''.
    vv.height = window.innerHeight;
    vv.offsetTop = 0;
    fire('resize');
    expect(root.style.height).toBe('');
    expect(root.style.transform).toBe('');

    // Unmount removes the listeners.
    await m.unmount();
    expect(listeners.resize.length).toBe(0);
    expect(listeners.scroll.length).toBe(0);
  } finally {
    delete window.visualViewport;
  }
});

test('P4: empty pending input + X → closes immediately (no modal)', async () => {
  const onSave = jest.fn();
  const onDiscard = jest.fn();
  const m = await mount({ imageFile: makeFile(), onSave, onDiscard });

  enterTextMode();
  canvasTap(100, 100); // overlay opens with empty value

  click(q('button[aria-label="סגור ללא שמירה"]'));

  expect(onDiscard).toHaveBeenCalledTimes(1);
  expect(onSave).not.toHaveBeenCalled();
  expect(document.body.textContent).not.toContain('לבטל את כל השינויים ולסגור?');

  await m.unmount();
});
