"""Style proxy — attribute-style access to the ``elem.style`` dict.

``StyleProxy`` is a ``dict`` subclass, so normal mapping operations work::

    elem.style['stroke']                  # subscript read
    elem.style['stroke'] = '#f00'         # subscript write
    elem.style.get('stroke', 'black')     # get with default
    'stroke' in elem.style                # membership
    for k, v in elem.style.items(): ...   # iteration
    dict(elem.style)                      # conversion
    json.dumps(elem.style)                # serialisation
    {**elem.style, 'extra': 1}            # unpacking

On top of that, the DSL-friendly attribute syntax works too::

    elem.style.stroke = '#ff0000'         # equivalent to ['stroke'] = ...
    elem.style.stroke                     # → '#ff0000' (None if unset)
    del elem.style.stroke                 # remove key

Semantics notes
---------------

* Missing keys return ``None`` from attribute access (instead of
  raising ``AttributeError``). Mirrors "style not set" intent, same
  way CSS cascades treat absent properties.
* ``hasattr(sp, 'stroke')`` always returns True as a consequence.
  Use ``'stroke' in sp`` for presence tests.
* Attribute names starting with ``_`` are treated as real Python
  attributes (for internal bookkeeping), not style keys.
"""

from __future__ import annotations


class StyleProxy(dict):
    """Dict subclass with attribute-style access to its keys."""

    def __init__(self, *args, **kwargs):
        object.__setattr__(self, "_explicit_keys", set())
        super().__init__()
        if args or kwargs:
            self.update(*args, **kwargs)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if not str(key).startswith("_"):
            self._explicit_keys.add(key)

    def update(self, *args, **kwargs):
        other = dict(*args, **kwargs)
        for key, value in other.items():
            self[key] = value

    def mark_clean(self):
        """Mark current contents as intrinsic defaults, not user writes."""
        self._explicit_keys.clear()
        return self

    def mark_explicit(self, key):
        self._explicit_keys.add(key)

    def is_explicit(self, key):
        return key in self._explicit_keys

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self.get(name)

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            self[name] = value

    def __delattr__(self, name):
        if name.startswith("_"):
            object.__delattr__(self, name)
        else:
            try:
                del self[name]
            except KeyError:
                raise AttributeError(name) from None

    def __repr__(self):
        return f"StyleProxy({dict.__repr__(self)})"
