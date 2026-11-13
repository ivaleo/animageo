/** Apply Python's export-frame display list once, after all creators exist.
 * Geometry can remain live; no update or drag listener changes this order.
 */
export function applyPaintOrder(board, S, paintOrder) {
  if (!paintOrder) return;
  const layer = board.renderer?.layer?.[9];
  if (!layer || typeof layer.appendChild !== 'function') return;
  for (const ref of paintOrder.partOrder || []) {
    for (const target of ref.targets || []) {
      const obj = S[target.name];
      const objects = target.node === 'borders' ? obj?.borders || []
        : [target.node === 'label' ? obj?.label : obj];
      for (const item of objects) {
        if (item?.rendNode) {
          if (target.fillRule && item.rendNode.setAttribute) item.rendNode.setAttribute('fill-rule', target.fillRule);
          layer.appendChild(item.rendNode);
        }
      }
    }
  }
}
