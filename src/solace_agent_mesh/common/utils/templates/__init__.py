"""
Templating utilities for inline template rendering.
"""

from .liquid_renderer import render_liquid_template
from .template_resolver import resolve_template_blocks_in_string

__all__ = ["render_liquid_template", "resolve_template_blocks_in_string"]
