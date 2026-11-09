#!/usr/bin/env python3
"""Check the selectors used by each universal IR scene against its shipped database."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IR = ROOT / "applications/main/infrared"
SCENES = {
    "ac": "ac.ir",
    "audio": "audio.ir",
    "fan": "fans.ir",
    "leds": "leds.ir",
    "projector": "projectors.ir",
    "tv": "tv.ir",
}


class UniversalIRDatabaseTest(unittest.TestCase):
    def test_scene_records_cover_each_database_signal_name(self):
        for scene, filename in SCENES.items():
            with self.subTest(scene=scene):
                source = (IR / f"scenes/infrared_scene_universal_{scene}.c").read_text(
                    encoding="utf-8"
                )
                database = (IR / f"resources/infrared/assets/{filename}").read_text(
                    encoding="utf-8"
                )
                self.assertIn(f'infrared/assets/{filename}', source)
                selectors = re.findall(
                    r'infrared_brute_force_add_record\(brute_force,\s*i\+\+,\s*"([^"]+)"\)',
                    source,
                )
                names = {line[6:].strip() for line in database.splitlines() if line.startswith("name: ")}
                self.assertTrue(names, f"{filename} contains no signal names")
                self.assertEqual(len(selectors), len(set(selectors)), "duplicate scene selectors")
                self.assertSetEqual(set(selectors), names)


if __name__ == "__main__":
    unittest.main()
