import io
from unittest.mock import Mock

import pytest
from PIL import Image
from pypdf import PdfReader

from sentio.whiteboard.canvas_schema import validate_canvas
from sentio.whiteboard.whiteboard_service import WhiteboardService


def test_highlighter_alpha_and_pdf_export_preserve_drawing():
    service = WhiteboardService(Mock())
    service.load_session = lambda _: {
        "canvas_state": {
            "width": 120,
            "height": 80,
            "shapes": [
                {
                    "type": "line",
                    "points": [[10, 20], [100, 20]],
                    "strokeWidth": 4,
                    "color": "rgba(0, 200, 255, 0.4)",
                }
            ],
        }
    }
    image = Image.open(io.BytesIO(service.export_canvas("fixture", "png")))
    assert image.size == (120, 80)
    red, green, blue = image.getpixel((20, 20))
    assert 150 <= red <= 155 and 231 <= green <= 235 and blue == 255
    assert len(PdfReader(io.BytesIO(service.export_canvas("fixture", "pdf"))).pages) == 1


@pytest.mark.parametrize(
    "state",
    [
        {"width": 100000, "height": 100000},
        {"shapes": [{"type": "line", "points": [[0, 0]]}]},
        {"shapes": [{"type": "text", "x": float("nan")}]},
        {"shapes": [{"type": "circle", "color": "rgba(0, 999, 0, 0.4)"}]},
    ],
)
def test_unsafe_canvas_is_rejected_before_allocation(state):
    with pytest.raises(ValueError):
        validate_canvas(state)
