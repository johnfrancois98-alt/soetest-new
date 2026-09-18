"""Small shared helpers for chart labels."""

import textwrap


def wrap_label(s, width=12):
    """Insert <br> line breaks so a long category label wraps under a bar
    instead of needing rotation."""
    return "<br>".join(textwrap.wrap(str(s), width=width)) or str(s)
