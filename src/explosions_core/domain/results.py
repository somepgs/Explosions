"""Общие выходные модели: нарушения нормативов и результат проверки."""

from pydantic import BaseModel, Field


class NormativeViolation(BaseModel):
    code: str
    clause: str
    description: str
    actual_value: float | str | None = None
    required_value: float | str | None = None


class ValidationResult(BaseModel):
    violations: list[NormativeViolation] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.violations
