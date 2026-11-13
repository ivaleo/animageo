import { mockEngine } from './mock-engine.js';

export function domEngine() {
  const engine = mockEngine();
  const init = engine.JSXGraph.initBoard;
  const nodes = [];
  engine.JSXGraph.initBoard = (...args) => {
    const board = init(...args);
    const layer = { appendChild(node) {
      const i = nodes.indexOf(node);
      if (i >= 0) nodes.splice(i, 1);
      nodes.push(node);
      node.parentNode = layer;
    } };
    board.renderer = { layer: Array.from({ length: 10 }, () => layer) };
    const create = board.create;
    board.create = (...args) => {
      const obj = create(...args);
      const node = (id) => ({ id, attrs: {}, setAttribute(k,v) { this.attrs[k]=v; }, getAttribute(k) { return this.attrs[k]; } });
      obj.rendNode = node('n'+nodes.length);
      obj.label = { rendNode: node(obj.rendNode.id + '_label') };
      for (const [i,border] of (obj.borders || []).entries()) {
        border.rendNode = node(obj.rendNode.id+'_border'+i);
        layer.appendChild(border.rendNode);
      }
      layer.appendChild(obj.rendNode);
      layer.appendChild(obj.label.rendNode);
      return obj;
    };
    board.nodes = nodes;
    return board;
  };
  return engine;
}

