"""Registry labels of the historical parity corpus, independent of releases."""
from .document import min_registry_version

BASELINE_VERSION = '1.12'


def fixture_version(document):
    """Retain old fixture bytes; label newly required operations explicitly."""
    return max(BASELINE_VERSION, min_registry_version(document),
               key=lambda version: tuple(map(int, version.split('.'))))
