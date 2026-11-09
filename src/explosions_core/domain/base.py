"""Базовые классы доменной модели."""

from pydantic import BaseModel, ConfigDict


class InputModel(BaseModel):
    """Входная модель: неизвестные поля (например, опечатки в JSON проекта) отвергаются."""

    model_config = ConfigDict(extra="forbid")
