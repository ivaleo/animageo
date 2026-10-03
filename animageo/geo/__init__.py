# Import ``construction`` first: it loads the geo modules in the order their
# mutual imports need, so ``import animageo.geo.lib_elements`` works on its
# own. ``import animageo`` used to do this as a side effect even without
# manim; it now skips the manim-backed API when manim is missing.
from . import construction  # noqa: F401,E402
