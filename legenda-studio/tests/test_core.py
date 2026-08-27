import unittest

from legenda_studio.ass import generate_ass
from legenda_studio.cuts import normalize_cuts, remap_captions, remap_time
from legenda_studio.models import CutRange, WordCaption
from legenda_studio.timecode import format_timecode, parse_timecode


class TimecodeTests(unittest.TestCase):
    def test_round_trip(self):
        value = "01:02:03.450"
        self.assertEqual(format_timecode(parse_timecode(value)), value)

    def test_rejects_invalid(self):
        with self.assertRaises(ValueError):
            parse_timecode("1:2:3")


class CutTests(unittest.TestCase):
    def test_overlapping_and_adjacent_ranges_are_merged(self):
        cuts = normalize_cuts([CutRange(4, 6), CutRange(1, 3), CutRange(3, 4), CutRange(5, 8)])
        self.assertEqual(cuts, [CutRange(1, 8)])

    def test_remaps_after_multiple_cuts(self):
        cuts = [CutRange(1, 2), CutRange(4, 5)]
        self.assertIsNone(remap_time(1.5, cuts))
        self.assertEqual(remap_time(6, cuts), 4)

    def test_caption_inside_or_crossing_cut_is_removed(self):
        captions = [
            WordCaption("antes", 0.2, 0.8),
            WordCaption("remover", 1.1, 1.9),
            WordCaption("cruza", 1.8, 2.2),
            WordCaption("depois", 3.0, 3.4),
        ]
        self.assertEqual(
            remap_captions(captions, [CutRange(1, 2)]),
            [WordCaption("antes", 0.2, 0.8), WordCaption("depois", 2.0, 2.4)],
        )


class AssTests(unittest.TestCase):
    def test_fixed_style_and_word_events(self):
        output = generate_ass([WordCaption("Olá {mundo}", 0, 1.25)])
        self.assertIn("Poppins ExtraBold,80", output)
        self.assertIn("PlayResX: 478", output)
        self.assertIn(r"\pos(239,625)", output)
        self.assertIn("Dialogue: 0,0:00:00.00,0:00:01.25", output)
        self.assertIn(r"\{mundo\}", output)
        self.assertEqual(output.count("Dialogue:"), 2)


if __name__ == "__main__":
    unittest.main()