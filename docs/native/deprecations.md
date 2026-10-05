# Deprecations

animageo 1.11.0rc1 (L6). A public name or form that is going away is
deprecated first: it keeps working and warns with `DeprecationWarning`,
saying since when, what to use instead and the version that removes it.

- **Removal is not before 2.0.** `remove_in` defaults to `"2.0"`; the helper
  refuses a lower version. A deprecated name stays through every 1.x.
- **One helper.** `animageo/_deprecation.py`:
  `@deprecated(since, remove_in="2.0", alternative=None)` on a function or a
  class (the call or the instantiation warns; the object gets
  `__deprecated__`, as in PEP 702); `register(...)` and `warn(name)` for a
  form of input (a JSON version, an argument value).
- **One list.** Every deprecation is a row of `_deprecation.DEPRECATIONS`
  and of the table below; `tests/test_deprecation.py` keeps them equal.
- **What is not a deprecation.** A fix of a classic bug (kernel spec §15:
  `CpxTo`, `parsers/ggb_generator.py`) removes a name that never worked; it
  is a line of CHANGELOG «1.8 → 1.11: native», not a row here. The public
  API itself is a snapshot (`tests/snapshots/public_api.json`): a name
  leaves it only through this table and a major version.

To silence the warnings of a deprecated form in your own code, fix the
call; to see them all in tests, run `python -W error::DeprecationWarning`.

## Deprecated

| Name | Since | Removed in | Instead |
|---|---|---|---|
| keyframes JSON v1 | 1.6.0 | 2.0 | `"version": 2` |
