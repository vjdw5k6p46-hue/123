from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError


@dataclass
class ValidationReport:
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def validate_output(parsed: Any, schema: Any = None, validator: Callable[[Any], Any] | None = None) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []

    if schema is not None:
        try:
            if isinstance(schema, type) and issubclass(schema, BaseModel):
                schema.model_validate(parsed)
            elif isinstance(schema, type) and issubclass(schema, list):
                if not isinstance(parsed, list):
                    errors.append("Expected a JSON list.")
            elif isinstance(schema, dict):
                required = schema.get("required", [])
                if not isinstance(parsed, dict):
                    errors.append("Expected a JSON object for schema validation.")
                else:
                    for key in required:
                        if key not in parsed:
                            errors.append(f"Missing required key: {key}")
            else:
                errors.append(f"Unsupported schema validator type: {type(schema).__name__}")
        except ValidationError as exc:
            errors.extend(err["msg"] for err in exc.errors())

    if validator is not None:
        try:
            result = validator(parsed)
            if isinstance(result, ValidationReport):
                errors.extend(result.errors)
                warnings.extend(result.warnings)
            elif result is False:
                errors.append("Custom validator returned False.")
        except Exception as exc:
            errors.append(f"Custom validator failed: {exc}")

    warnings.extend(_citation_warnings(parsed))
    return ValidationReport(status="failed" if errors else "passed", errors=errors, warnings=warnings)


def _citation_warnings(value: Any) -> list[str]:
    warnings: list[str] = []
    if isinstance(value, dict):
        if "citation" in value and isinstance(value["citation"], dict):
            citation = value["citation"]
            if not any(citation.get(key) for key in ["title", "doi", "pmid", "source_paper_id"]):
                warnings.append("Citation object has no title, DOI, PMID, or source_paper_id; mark as missing rather than inventing metadata.")
        for nested in value.values():
            warnings.extend(_citation_warnings(nested))
    elif isinstance(value, list):
        for item in value:
            warnings.extend(_citation_warnings(item))
    return warnings
