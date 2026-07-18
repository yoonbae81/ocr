"""Load declarative regular-expression replacement rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict

DEFAULT_RULE_DIRECTORY: Final = Path(__file__).with_name("rules")


class RegexRuleFile(BaseModel):
    """Schema for one JSON post-processing rule file."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    before: str
    after: str


@dataclass(frozen=True, slots=True)
class RegexReplacement:
    """Compiled replacement ready to apply to recognized Markdown."""

    before: re.Pattern[str]
    after: str

    def apply(self, body: str, /) -> str:
        """Apply this rule to one Markdown body."""
        return self.before.sub(self.after, body)


def load_regex_rules(directory: Path, /) -> tuple[RegexReplacement, ...]:
    """Load JSON rules in filename order from the given directory."""
    return tuple(_load_regex_rule(path) for path in sorted(directory.glob("*.json")))


def _load_regex_rule(path: Path) -> RegexReplacement:
    rule = RegexRuleFile.model_validate_json(path.read_text(encoding="utf-8"))
    return RegexReplacement(before=re.compile(rule.before), after=rule.after)
