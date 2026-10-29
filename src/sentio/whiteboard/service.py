"""
service.py -- Whiteboard Drawing Canvas Service (Phase D5 & D6)
===========================================================================
Handles saving/loading canvas vector structures, exporting canvas states to
PNG/PDF using Pillow, and parsing Mermaid.js diagrams into vector shapes.
"""

import io
import json
import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from sentio.whiteboard.canvas_schema import render_color, validate_canvas

logger = logging.getLogger(__name__)


class WhiteboardService:
    def __init__(self, agent):
        self.agent = agent

    def save_session(
        self,
        whiteboard_id: str,
        student_id: str,
        session_id: str,
        title: str,
        canvas_state: Dict[str, Any],
        require_owner=False,
    ):
        """Save/Sync the whiteboard canvas state JSON."""
        state_str = json.dumps(validate_canvas(canvas_state))

        def save(connection=None):
            self.agent.sm.save_whiteboard(
                whiteboard_id=whiteboard_id,
                student_id=student_id,
                session_id=session_id,
                title=title,
                canvas_state_json=state_str,
                connection=connection,
            )

        if require_owner:
            from sentio.repositories.whiteboards import WhiteboardRepository

            repository = WhiteboardRepository(self.agent.sm.persister._engine)
            with repository.publication(student_id, session_id, whiteboard_id) as connection:
                save(connection)
        else:
            save()
        logger.info(f"Saved whiteboard {whiteboard_id} (title: '{title}')")

    def load_session(self, whiteboard_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve whiteboard canvas state."""
        wb = self.agent.sm.get_whiteboard(whiteboard_id)
        if not wb:
            return None
        return {
            "whiteboard_id": wb["whiteboard_id"],
            "student_id": wb["student_id"],
            "session_id": wb["session_id"],
            "title": wb["title"],
            "canvas_state": json.loads(wb["canvas_state_json"]),
            "created_at": wb["created_at"],
            "updated_at": wb["updated_at"],
        }

    def export_canvas(self, whiteboard_id: str, format_type: str = "png") -> bytes:
        """
        Render canvas vector shapes to PNG or PDF bytes using Pillow.
        """
        wb_data = self.load_session(whiteboard_id)
        if not wb_data:
            raise ValueError(f"Whiteboard not found: {whiteboard_id}")

        if format_type.lower() not in ("png", "pdf"):
            raise ValueError("Choose PNG or PDF export")
        canvas_state = validate_canvas(wb_data["canvas_state"])
        shapes = canvas_state.get("shapes", [])

        # Create a blank image with a grid paper background
        width = canvas_state.get("width", 1000)
        height = canvas_state.get("height", 800)
        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img, "RGBA")

        # Draw grid lines (subtle grid paper feel)
        grid_size = 40
        for x in range(0, width, grid_size):
            draw.line([(x, 0), (x, height)], fill="#F0F0F0", width=1)
        for y in range(0, height, grid_size):
            draw.line([(0, y), (width, y)], fill="#F0F0F0", width=1)

        # Draw shapes
        for s in shapes:
            stype = s.get("type", "").lower()
            color = render_color(s.get("color", "black"))
            stroke_width = int(s.get("strokeWidth", 2))

            x = float(s.get("x", 0))
            y = float(s.get("y", 0))
            w = float(s.get("width", 0)) if s.get("width") is not None else 0.0
            h = float(s.get("height", 0)) if s.get("height") is not None else 0.0

            if stype == "rectangle":
                draw.rectangle([x, y, x + w, y + h], outline=color, width=stroke_width)
            elif stype == "circle":
                # For circles, w acts as diameter
                r = w / 2
                cx, cy = x + r, y + r
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=stroke_width)
            elif stype in ["line", "arrow"]:
                # Parse points
                points_list = s.get("points", [])
                if len(points_list) >= 2:
                    coords = []
                    for p in points_list:
                        coords.append((float(p[0]), float(p[1])))
                    draw.line(coords, fill=color, width=stroke_width)

                    # Draw arrow head if arrow
                    if stype == "arrow" and len(coords) >= 2:
                        p1, p2 = coords[-2], coords[-1]
                        self._draw_arrow_head(draw, p1, p2, color, stroke_width)
            elif stype == "text":
                text_val = s.get("text", "")
                font = ImageFont.load_default(size=int(s.get("fontSize", 16)))
                # Draw simple text annotation
                draw.text((x, y), text_val, fill=color, font=font)

        # Output to byte stream
        bio = io.BytesIO()
        if format_type.lower() == "pdf":
            # Pillow natively supports writing RGB images as single-page PDFs
            img.save(bio, format="PDF")
        else:
            img.save(bio, format="PNG")

        return bio.getvalue()

    def _draw_arrow_head(
        self, draw, p1: Tuple[float, float], p2: Tuple[float, float], color: str, width: int
    ):
        """Helper to draw arrow heads on canvas line endpoints."""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        angle = math.atan2(dy, dx)

        arrow_length = 12
        arrow_angle = math.pi / 6  # 30 degrees

        # Calculate arrow points
        x3 = p2[0] - arrow_length * math.cos(angle - arrow_angle)
        y3 = p2[1] - arrow_length * math.sin(angle - arrow_angle)
        x4 = p2[0] - arrow_length * math.cos(angle + arrow_angle)
        y4 = p2[1] - arrow_length * math.sin(angle + arrow_angle)

        draw.line([p2, (x3, y3)], fill=color, width=width)
        draw.line([p2, (x4, y4)], fill=color, width=width)

    def parse_mermaid_to_shapes(self, mermaid_code: str) -> List[Dict[str, Any]]:
        """
        Parses basic Mermaid flowchart syntax into a list of vector shapes (D6 tutor diagrams).
        Ex:
          graph TD
            A[Start] --> B[Process]
        """
        shapes = []
        nodes = {}  # id -> label
        edges = []  # (id1, id2, label)

        # Basic parsing loop
        lines = mermaid_code.split("\n")
        for line in lines:
            line = line.strip()
            if not line or any(k in line for k in ["graph", "flowchart", "subgraph", "end"]):
                continue

            # Parse nodes with brackets: A[Label] or A(Label) or A((Label))
            node_matches = re.finditer(
                r"([a-zA-Z0-9_-]+)\s*(?:\[|\(|\(\()([^\]\)]+)(?:\]|\)|\)\))", line
            )
            for m in node_matches:
                nid = m.group(1).strip()
                nlabel = m.group(2).strip()
                nodes[nid] = nlabel

            # Remove node labels (bracketed text) so we can easily parse the edges (e.g. A --> B)
            cleaned_line = re.sub(r"\s*(?:\[|\(|\(\()[^\]\)]+(?:\]|\)|\)\))", "", line)
            # Parse edges: A --> B or A -->|label| B
            edge_match = re.finditer(
                r"([a-zA-Z0-9_-]+)\s*(?:-->|-->\|([^|]+)\|)\s*([a-zA-Z0-9_-]+)", cleaned_line
            )
            for m in edge_match:
                id1 = m.group(1).strip()
                elbl = m.group(2).strip() if m.group(2) else ""
                id2 = m.group(3).strip()
                edges.append((id1, id2, elbl))

                # Implicitly declare nodes if not done yet
                if id1 not in nodes:
                    nodes[id1] = id1
                if id2 not in nodes:
                    nodes[id2] = id2

        # Layout nodes vertically/horizontally
        node_ids = list(nodes.keys())
        node_positions = {}  # id -> (x, y)

        # Grid layout
        start_x, start_y = 150.0, 150.0
        spacing_x, spacing_y = 200.0, 150.0

        # Simple TD (top-down) layout by default
        for idx, nid in enumerate(node_ids):
            # Layout vertically
            x = start_x + (idx % 2) * spacing_x
            y = start_y + (idx // 2) * spacing_y
            node_positions[nid] = (x, y)

            # Create a box shape for the node
            shapes.append(
                {
                    "type": "rectangle",
                    "x": x,
                    "y": y,
                    "width": 120.0,
                    "height": 50.0,
                    "color": "blue",
                    "strokeWidth": 2,
                }
            )
            # Add text inside the node
            shapes.append(
                {
                    "type": "text",
                    "x": x + 10.0,
                    "y": y + 15.0,
                    "text": nodes[nid],
                    "color": "black",
                    "fontSize": 14,
                }
            )

        # Create arrows for edges
        for id1, id2, elbl in edges:
            if id1 in node_positions and id2 in node_positions:
                x1, y1 = node_positions[id1]
                x2, y2 = node_positions[id2]

                # Edges from center bottoms to tops
                p1 = (x1 + 60.0, y1 + 50.0)
                p2 = (x2 + 60.0, y2)

                shapes.append(
                    {"type": "arrow", "points": [p1, p2], "color": "darkgray", "strokeWidth": 2}
                )

                # Edge labels if present
                if elbl:
                    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
                    shapes.append(
                        {
                            "type": "text",
                            "x": mx + 10.0,
                            "y": my - 10.0,
                            "text": elbl,
                            "color": "red",
                            "fontSize": 12,
                        }
                    )

        return shapes
