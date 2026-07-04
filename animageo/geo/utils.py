"""Shared utility functions for type checking and value parsing."""


def is_number(s):
    """Check if a value can be interpreted as a float."""
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def is_angle_degrees(s):
    """Check if a string represents an angle in degrees (e.g. '90°')."""
    try:
        if not isinstance(s, str) or not s.endswith('°'):
            return False
        float(s[:-1])
        return True
    except (ValueError, TypeError):
        return False


def is_boolean(s):
    """Check if a value represents a boolean string ('true'/'false')."""
    return str(s).lower() in ('true', 'false')


def boolean(s):
    """Parse a string as boolean."""
    return str(s).lower() == 'true'
