from typing import Literal
from pydantic import BaseModel, Field, field_validator


class Query(BaseModel):
    query: str = Field(min_length=1, max_length=1500)
    document_ids: list[str] = Field(default_factory=list, max_length=100)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Please enter a question or search term.")
        return value.strip()


class Question(Query):
    language: Literal["Auto", "English", "中文", "Español", "Français", "日本語"] = (
        "Auto"
    )


class Rename(BaseModel):
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Title cannot be blank.")
        return value.strip()


