# `ray.by_vector` — ray along a vector (beta)

Registry 1.4 · beta · group `line` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `origin: point`, `vector: vector` |
| outputs | `ray: ray` |
| orientation | `vector_dir` |
| undefined | `zero_length`, `upstream` |
| checks | `parallel` |

Beta. The ray from `origin` along the vector.

## Value

    v = vector.b − vector.a,  L = hypot(v)
    if L ≤ tol.decide:      → "zero_length"
    ray = {origin, dir: v / L}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` | `L` | `tol.decide` |

## Checks

- `parallel`: `|dir × v| / |v|·S`
