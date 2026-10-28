from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.palette import compile_palette


class PaletteTests(unittest.TestCase):
    def test_known_surface_colors_are_live_variables(self):
        self.assertEqual(compile_palette("body { background:#10191a; color:#e6f2e9; }"),
                         "body { background:var(--forge-canvas); color:var(--forge-ink); }")

    def test_security_colors_are_not_remapped(self):
        text = ".warning { color:#ffd18d; } .error { color:#ffaaa9; }"
        self.assertEqual(compile_palette(text), text)

    def test_fallbacks_are_not_circular(self):
        text = "  --forge-canvas: #10191a;\nbody {background:#10191a}"
        self.assertIn("--forge-canvas: #10191a", compile_palette(text))
        self.assertNotIn("--forge-canvas: var(--forge-canvas)", compile_palette(text))

    def test_compilation_is_idempotent(self):
        text = "body { background:#10191a; border:1px solid #3b5146; }"
        self.assertEqual(compile_palette(compile_palette(text)), compile_palette(text))


if __name__ == "__main__":
    unittest.main()
