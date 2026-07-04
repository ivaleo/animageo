/**
 * Vue 3 adapter (template) — not part of the library core.
 *
 *   <template><div ref="container" style="width:640px;height:480px" /></template>
 *   <script setup>
 *   const { container, state, setState } = useAnimageoBoard(spec, {
 *     onCommit: ({ name, value }) => save(name, value),
 *   });
 *   </script>
 *
 * Requires `@animageo/runtime` and a JSXGraph global (or pass `engine`).
 */
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue';
import { createBoard } from '@animageo/runtime';

export function useAnimageoBoard(spec, options = {}) {
  const container = ref(null);
  const state = shallowRef(null);
  const handle = shallowRef(null);

  onMounted(() => {
    if (!container.value || !spec) return;
    const h = createBoard(spec, container.value, {
      engine: options.engine,
      debounceMs: options.debounceMs,
    });
    handle.value = h;
    h.on('ready', (p) => { state.value = p.state; options.onReady?.(p); });
    h.on('change', (p) => { state.value = p.state; options.onChange?.(p); });
    h.on('commit', (p) => options.onCommit?.(p));
  });

  onBeforeUnmount(() => {
    handle.value?.destroy();
    handle.value = null;
  });

  return {
    container,
    state,
    handle,
    setState: (partial) => handle.value?.setState(partial),
  };
}
