#!/usr/bin/env python3
"""Check that the preferred animation selector covers the shipped DONNY scenes."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANAGER = ROOT / "applications/services/desktop/animations/animation_manager.c"
MANIFEST = ROOT / "assets/dolphin/external/manifest.txt"


class DonnyAnimationSelectionTest(unittest.TestCase):
    def test_all_shipped_donny_animations_are_preferred(self):
        source = MANAGER.read_text(encoding="utf-8")
        function = re.search(
            r"static bool animation_manager_is_donny_animation\([^}]+\}", source
        )
        self.assertIsNotNone(function)
        prefixes = re.findall(r'strncmp\(info->name, "([^"]+)",\s*(\d+)\)', function.group())
        self.assertTrue(prefixes)
        for prefix, length in prefixes:
            self.assertEqual(len(prefix), int(length))
        names = re.findall(r"^Name: (DB_(?:DS|Kluk|Auto)_[^\r\n]+)$", MANIFEST.read_text(encoding="utf-8"), re.M)
        self.assertEqual(len(names), 12)
        self.assertEqual(len(set(names)), 12)
        for name in names:
            with self.subTest(animation=name):
                self.assertTrue(any(name.startswith(prefix) for prefix, _ in prefixes))
        self.assertFalse(any("L1_Sleep_128x64".startswith(prefix) for prefix, _ in prefixes))


if __name__ == "__main__":
    unittest.main()
