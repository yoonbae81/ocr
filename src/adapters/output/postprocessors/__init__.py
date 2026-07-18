"""Declarative Markdown post-processing rule loader."""

from __future__ import annotations

from .loader import DEFAULT_RULE_DIRECTORY, RegexReplacement, load_regex_rules

__all__ = [
    "DEFAULT_RULE_DIRECTORY",
    "RegexReplacement",
    "load_regex_rules",
]
