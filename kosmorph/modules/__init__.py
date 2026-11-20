"""Imports all built-in modules so their @register_action decorators execute."""

from . import organizer, converters, pdf_tools, file_ops, image_tools, spreadsheets

__all__ = [
    "organizer",
    "converters",
    "pdf_tools",
    "file_ops",
    "image_tools",
    "spreadsheets",
]
