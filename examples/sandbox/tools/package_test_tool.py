"""
Package loading test tool.

This tool imports from 'pyfiglet', a pip package that is NOT pre-installed
in the container image. The manifest declares `package: pyfiglet` so the
worker should auto-install it via `ensure_packages_installed()` on startup.

If the import succeeds and the tool returns ASCII art, the package loading
pipeline is working end-to-end.
"""

from typing import Any, Dict


def render_ascii_art(ctx: Any, text: str, font: str = "standard") -> Dict[str, Any]:
    """
    Render text as ASCII art using pyfiglet.

    This tool exists to verify that the manifest `package` field triggers
    automatic installation. pyfiglet is not in the base container image.

    Args:
        ctx: Tool context
        text: Text to render
        font: pyfiglet font name (default: standard)

    Returns:
        Dict with the rendered ASCII art and package version
    """
    import pyfiglet

    ctx.send_status(f"Rendering '{text}' with font '{font}'...")

    try:
        art = pyfiglet.figlet_format(text, font=font)
    except pyfiglet.FontNotFound:
        return {
            "status": "error",
            "error": f"Font '{font}' not found",
            "available_fonts": pyfiglet.FigletFont.getFonts()[:20],
        }

    return {
        "status": "success",
        "ascii_art": art,
        "pyfiglet_version": getattr(pyfiglet, "__version__", "unknown"),
        "font_used": font,
    }
