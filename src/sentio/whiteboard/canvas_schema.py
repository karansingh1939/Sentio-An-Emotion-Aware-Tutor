"""Bound vector input and normalize browser colors for consistent exports."""

import re
from typing import Literal

from PIL import ImageColor
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def render_color(value):
    match = re.fullmatch(
        r"rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*([0-9.]+)\s*\)", value
    )
    if match:
        red, green, blue = (int(match[i]) for i in (1, 2, 3))
        alpha = float(match[4])
        if max(red, green, blue) > 255 or not 0 <= alpha <= 1:
            raise ValueError("Invalid highlight color")
        return red, green, blue, round(alpha * 255)
    return ImageColor.getcolor(value, "RGBA")


class Shape(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    type: Literal["line", "arrow", "rectangle", "circle", "text"]
    color: str = Field("black", max_length=60)
    strokeWidth: int = Field(2, ge=1, le=64)
    x: float = Field(0, ge=-10000, le=10000)
    y: float = Field(0, ge=-10000, le=10000)
    width: float = Field(0, ge=0, le=10000)
    height: float = Field(0, ge=0, le=10000)
    fontSize: int = Field(16, ge=8, le=128)
    text: str = Field("", max_length=2000)
    points: list[tuple[float, float]] = Field(default_factory=list, max_length=2000)

    @field_validator("color")
    @classmethod
    def valid_color(cls, value):
        render_color(value)
        return value

    @model_validator(mode="after")
    def valid_points(self):
        if self.type in ("line", "arrow") and len(self.points) < 2:
            raise ValueError("A line or arrow needs at least two points")
        if any(abs(coordinate) > 10000 for point in self.points for coordinate in point):
            raise ValueError("Drawing coordinates exceed their bounds")
        return self


class CanvasState(BaseModel):
    width: int = Field(1000, ge=1, le=4096)
    height: int = Field(800, ge=1, le=4096)
    shapes: list[Shape] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def bounded_canvas(self):
        if (
            self.width * self.height > 8_000_000
            or sum(len(shape.points) for shape in self.shapes) > 30000
        ):
            raise ValueError("Drawing exceeds the canvas or point budget")
        return self


def validate_canvas(state):
    return CanvasState.model_validate(state).model_dump()
