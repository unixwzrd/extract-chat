"""Source adapters normalize input; processors and formatters consume shared models."""

from dataclasses import dataclass
from typing import Any, Protocol

from extract_chat.schemas.render_models import SchemaDiagnostics


@dataclass(frozen=True)
class ParsedSource:
    adapter: str
    conversation: dict[str, Any]
    diagnostics: SchemaDiagnostics


class SourceAdapter(Protocol):
    name: str

    def matches(self, raw: Any) -> bool: ...

    def parse(self, raw: Any) -> ParsedSource: ...
