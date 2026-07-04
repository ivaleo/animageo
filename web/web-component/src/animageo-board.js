/**
 * <animageo-board> — the zero-framework integration primitive.
 *
 * A custom element wrapping @animageo/runtime. Works in any framework (React,
 * Vue, Angular, Svelte) or none, because custom elements are part of the DOM.
 *
 *   <animageo-board spec="/board.json" debounce="50"></animageo-board>
 *   const el = document.querySelector('animageo-board');
 *   el.addEventListener('animageo:change', (e) => console.log(e.detail.state));
 *   el.setState({ A: { x: 1, y: 2 } });
 *
 * Or set the spec as a property (preferred for app integration):
 *   el.spec = await fetch('/board.json').then(r => r.json());
 *
 * Signals are dispatched as bubbling, composed CustomEvents named
 * `animageo:<signal>` (ready / change / commit / viewchange / error). Actions
 * are element methods delegating to the runtime handle.
 *
 * In this repo the runtime is imported by relative path so the example runs
 * unbuilt; the published package imports `@animageo/runtime` (and a UMD bundle
 * inlines it for <script> users).
 */
import { createBoard } from '../../runtime/src/index.js';

const SIGNALS = ['ready', 'change', 'commit', 'viewchange', 'select', 'error'];
const DEFAULT_JSXGRAPH =
  'https://cdn.jsdelivr.net/npm/jsxgraph@1.10.1/distrib/jsxgraphcore.js';

export class AnimageoBoard extends HTMLElement {
  static get observedAttributes() {
    return ['spec'];
  }

  constructor() {
    super();
    this._spec = null;
    this._handle = null;
    this._offs = [];
    this._mount = null;
    this.engine = null; // optional injected JXG (else global / CDN)
  }

  /** The board spec (animageo-board/v1) as an object. Setting it rebuilds. */
  get spec() {
    return this._spec;
  }
  set spec(value) {
    this._spec = value;
    if (this.isConnected) this._rebuild();
  }

  /** The live runtime handle (or null before build). */
  get handle() {
    return this._handle;
  }

  connectedCallback() {
    if (this._spec) {
      this._rebuild();
      return;
    }
    const attr = this.getAttribute('spec');
    if (attr) this._loadFromAttr(attr);
  }

  disconnectedCallback() {
    this._teardown();
  }

  attributeChangedCallback(name, _old, value) {
    if (name === 'spec' && value && !this._spec && this.isConnected) {
      this._loadFromAttr(value);
    }
  }

  async _loadFromAttr(attr) {
    const s = String(attr).trim();
    let spec;
    if (s.startsWith('{')) {
      try {
        spec = JSON.parse(s);
      } catch {
        return this._emitError('invalid inline spec JSON');
      }
    } else {
      try {
        spec = await fetch(s).then((r) => r.json());
      } catch {
        return this._emitError('failed to fetch spec: ' + s);
      }
    }
    this._spec = spec;
    if (this.isConnected) this._rebuild();
  }

  async _rebuild() {
    this._teardown();
    if (!this._spec) return;

    let engine =
      this.engine || (typeof globalThis !== 'undefined' ? globalThis.JXG : undefined);
    if (!engine) {
      try {
        engine = await ensureEngine(this.getAttribute('jsxgraph-src'));
      } catch {
        return this._emitError('JSXGraph failed to load');
      }
    }
    if (!this._spec || !this.isConnected) return; // disconnected while loading

    const opts = { engine };
    const debounce = this.getAttribute('debounce');
    if (debounce) opts.debounceMs = Number(debounce);

    try {
      this._handle = createBoard(this._spec, this._container(), opts);
    } catch (err) {
      return this._emitError(String((err && err.message) || err));
    }
    for (const sig of SIGNALS) {
      this._offs.push(
        this._handle.on(sig, (detail) =>
          this.dispatchEvent(
            new CustomEvent('animageo:' + sig, {
              detail,
              bubbles: true,
              composed: true,
            }),
          ),
        ),
      );
    }
  }

  _container() {
    if (typeof document === 'undefined') return this; // headless (tests)
    if (!this._mount) {
      this._mount = document.createElement('div');
      this._mount.style.width = '100%';
      this._mount.style.height = '100%';
      this._mount.id = 'agbox-' + Math.random().toString(36).slice(2);
      this.appendChild(this._mount);
    }
    return this._mount;
  }

  _teardown() {
    for (const off of this._offs) {
      try {
        off();
      } catch {
        /* ignore */
      }
    }
    this._offs = [];
    if (this._handle) {
      try {
        this._handle.destroy();
      } catch {
        /* ignore */
      }
      this._handle = null;
    }
  }

  _emitError(message) {
    this.dispatchEvent(
      new CustomEvent('animageo:error', {
        detail: { message },
        bubbles: true,
        composed: true,
      }),
    );
  }

  // ── actions (delegate to the handle) ───────────────────────────────────────
  getState() {
    return this._handle ? this._handle.getState() : null;
  }
  setState(partial) {
    if (this._handle) this._handle.setState(partial);
  }
  getValue(name) {
    return this._handle ? this._handle.getValue(name) : undefined;
  }
  setValue(name, value) {
    if (this._handle) this._handle.setValue(name, value);
  }
  getElement(name) {
    return this._handle ? this._handle.getElement(name) : null;
  }
  reset() {
    if (this._handle) this._handle.reset();
  }
  setVisible(name, on) {
    if (this._handle) this._handle.setVisible(name, on);
  }
  setStyle(name, attrs) {
    if (this._handle) this._handle.setStyle(name, attrs);
  }
  inputs() {
    return this._handle ? this._handle.inputs() : [];
  }
  toSVG() {
    return this._handle ? this._handle.toSVG() : '';
  }
}

let _enginePromise = null;
/** Load JSXGraph from a CDN (once) if no `JXG` global is present. */
export function ensureEngine(src) {
  if (typeof globalThis !== 'undefined' && globalThis.JXG) {
    return Promise.resolve(globalThis.JXG);
  }
  if (_enginePromise) return _enginePromise;
  _enginePromise = new Promise((resolve, reject) => {
    if (typeof document === 'undefined') {
      reject(new Error('no document to load JSXGraph into'));
      return;
    }
    const url = src || DEFAULT_JSXGRAPH;
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = url.replace('jsxgraphcore.js', 'jsxgraph.css');
    document.head.appendChild(css);
    const script = document.createElement('script');
    script.src = url;
    script.onload = () => resolve(globalThis.JXG);
    script.onerror = () => reject(new Error('JSXGraph script failed to load'));
    document.head.appendChild(script);
  });
  return _enginePromise;
}

export function defineAnimageoBoard(tag = 'animageo-board') {
  if (typeof customElements !== 'undefined' && !customElements.get(tag)) {
    customElements.define(tag, AnimageoBoard);
  }
}

// Auto-register on import in a browser.
defineAnimageoBoard();
