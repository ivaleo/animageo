/**
 * React adapter (template, ~30 lines) — not part of the library core.
 *
 *   const { containerRef, state, setState } = useAnimageoBoard(spec, {
 *     onCommit: ({ name, value }) => analytics.track('move', { name, value }),
 *   });
 *   return <div ref={containerRef} style={{ width: 640, height: 480 }} />;
 *
 * Requires `@animageo/runtime` and a JSXGraph global (or pass `engine`).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { createBoard } from '@animageo/runtime';

export function useAnimageoBoard(spec, options = {}) {
  const { engine, debounceMs, onReady, onChange, onCommit } = options;
  const containerRef = useRef(null);
  const handleRef = useRef(null);
  const [state, setState] = useState(null);

  // Keep callbacks fresh without rebuilding the board.
  const cbRef = useRef({});
  cbRef.current = { onReady, onChange, onCommit };

  useEffect(() => {
    if (!containerRef.current || !spec) return undefined;
    const handle = createBoard(spec, containerRef.current, { engine, debounceMs });
    handleRef.current = handle;
    const offs = [
      handle.on('ready', (p) => { setState(p.state); cbRef.current.onReady?.(p); }),
      handle.on('change', (p) => { setState(p.state); cbRef.current.onChange?.(p); }),
      handle.on('commit', (p) => cbRef.current.onCommit?.(p)),
    ];
    return () => {
      offs.forEach((off) => off());
      handle.destroy();
      handleRef.current = null;
    };
  }, [spec, engine, debounceMs]);

  const setBoardState = useCallback((partial) => handleRef.current?.setState(partial), []);

  return { containerRef, state, setState: setBoardState, handle: handleRef };
}
