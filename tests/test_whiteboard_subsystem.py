"""
test_whiteboard_subsystem.py -- Unit and Integration Tests for Whiteboard Subsystem (Phases D5 & D6)
=============================================================================================
Verifies:
  - Whiteboard database persistence (save/load)
  - Vector coordinate synchronization
  - Drawing rendering and image export (PNG)
  - Document rendering and PDF export
  - Mermaid diagram layout parsing into vector shapes
"""

import io
import unittest

from PIL import Image

from sentio.tutor.tutor_agent import TutorAgent
from sentio.whiteboard.whiteboard_service import WhiteboardService


class TestWhiteboardSubsystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = TutorAgent()
        cls.agent.load()
        cls.whiteboard_service = WhiteboardService(cls.agent)

        cls.student_id = "stu_test_board_001"
        cls.agent.sm.ensure_student_exists(cls.student_id)

        cls.session = cls.agent.sm.create_session(
            student_id=cls.student_id,
            subject="computer_science",
            topic="recursion",
            difficulty="intermediate",
        )
        cls.session_id = cls.session.session_id
        cls.whiteboard_id = "wb_test_id_999"

    def test_01_save_and_load_whiteboard(self):
        canvas_state = {
            "width": 800,
            "height": 600,
            "shapes": [
                {
                    "type": "rectangle",
                    "x": 50.0,
                    "y": 100.0,
                    "width": 200.0,
                    "height": 100.0,
                    "color": "blue",
                    "strokeWidth": 3,
                },
                {
                    "type": "circle",
                    "x": 300.0,
                    "y": 150.0,
                    "width": 80.0,  # diameter
                    "color": "red",
                    "strokeWidth": 2,
                },
                {
                    "type": "arrow",
                    "points": [[150.0, 200.0], [300.0, 200.0]],
                    "color": "black",
                    "strokeWidth": 2,
                },
                {
                    "type": "text",
                    "x": 60.0,
                    "y": 120.0,
                    "text": "Hello Whiteboard",
                    "color": "green",
                    "fontSize": 18,
                },
            ],
        }

        # Save whiteboard
        self.whiteboard_service.save_session(
            whiteboard_id=self.whiteboard_id,
            student_id=self.student_id,
            session_id=self.session_id,
            title="Recursion Diagram",
            canvas_state=canvas_state,
        )

        # Load and verify
        loaded = self.whiteboard_service.load_session(self.whiteboard_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["title"], "Recursion Diagram")
        self.assertEqual(loaded["canvas_state"]["width"], 800)
        self.assertEqual(len(loaded["canvas_state"]["shapes"]), 4)
        self.assertEqual(loaded["canvas_state"]["shapes"][0]["type"], "rectangle")
        self.assertEqual(loaded["canvas_state"]["shapes"][3]["text"], "Hello Whiteboard")

    def test_02_export_png(self):
        png_bytes = self.whiteboard_service.export_canvas(self.whiteboard_id, format_type="png")
        self.assertIsNotNone(png_bytes)
        self.assertGreater(len(png_bytes), 100)

        # Verify it is a valid PNG image
        try:
            img = Image.open(io.BytesIO(png_bytes))
            self.assertEqual(img.format, "PNG")
            self.assertEqual(img.size, (800, 600))
        except Exception as e:
            self.fail(f"PNG export invalid: {e}")

    def test_03_export_pdf(self):
        pdf_bytes = self.whiteboard_service.export_canvas(self.whiteboard_id, format_type="pdf")
        self.assertIsNotNone(pdf_bytes)
        self.assertGreater(len(pdf_bytes), 100)

        # Verify PDF magic number header
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_04_parse_mermaid_to_shapes(self):
        mermaid_code = """
        graph TD
            A[Base Case] --> B[Recursive Step]
            B -->|calls| A
        """
        shapes = self.whiteboard_service.parse_mermaid_to_shapes(mermaid_code)

        self.assertGreaterEqual(len(shapes), 4)  # Should have node rectangles, texts, and arrows

        # Verify existence of node text shapes
        texts = [s["text"] for s in shapes if s.get("type") == "text"]
        self.assertIn("Base Case", texts)
        self.assertIn("Recursive Step", texts)
        self.assertIn("calls", texts)

        # Verify arrows connecting them exist
        arrows = [s for s in shapes if s.get("type") == "arrow"]
        self.assertEqual(len(arrows), 2)


if __name__ == "__main__":
    unittest.main()
