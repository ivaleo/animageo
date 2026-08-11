# Security Policy

## Supported versions

Fixes are released on the latest published version. Please upgrade to the
newest release on [PyPI](https://pypi.org/project/animageo/) before reporting.

## Reporting a vulnerability

Report privately through GitHub's
[security advisory form](https://github.com/ivaleo/animageo/security/advisories/new),
or by email to <leo.ivadev@gmail.com>. Please do not open a public issue for a
vulnerability.

Include what the issue is, how to reproduce it (a minimal `.ggb`, DSL snippet,
or style JSON is ideal), and the animageo and Python versions. Expect an
acknowledgement within a week.

## Scope note: untrusted input

Two entry points execute or evaluate their input by design:

- **`scene.putCode()` / `scene.loadCode()`** run the DSL through Python's
  `exec` after an AST rewrite. The rewrite is not a security sandbox.
- **`Function` / `Conic` / `ImplicitCurve` string constructors** parse
  expressions with sympy.

Do not pass code, expressions, or style JSON from untrusted sources into a
process that holds anything you care about. If you build a service around
animageo, run the rendering in an isolated worker (separate process, dropped
privileges, no network, resource limits). Reports that amount to "`putCode`
executes the code you give it" are expected behavior, not vulnerabilities;
reports of parsing a `.ggb` file causing code execution are in scope.
