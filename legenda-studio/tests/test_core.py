import unittest
import tempfile
from pathlib import Path

from legenda_studio.ass import generate_ass
from legenda_studio.cuts import normalize_cuts, remap_captions, remap_time
from legenda_studio.models import CutRange, WordCaption
from legenda_studio.project import ProjectState, SessionStore, load_project, save_project
from legenda_studio.silence import parse_silence_output
from legenda_studio.themes import THEME_DARK, THEME_LIGHT, resolved_theme
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


class ProjectTests(unittest.TestCase):
    def test_project_round_trip_and_recent_session(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "video.mp4"
            source.touch()
            state = ProjectState(
                source=source,
                captions=[WordCaption("teste", 0.2, 0.8)],
                cuts=[CutRange(1, 2)],
                position_ms=4321,
            )
            project = root / "projeto.glimo"
            save_project(project, state)
            loaded = load_project(project)
            self.assertEqual(loaded.source, source)
            self.assertEqual(loaded.captions, state.captions)
            self.assertEqual(loaded.cuts, state.cuts)
            self.assertEqual(loaded.position_ms, 4321)

            store = SessionStore(root / "app-data")
            snapshot = store.save(state)
            self.assertTrue(snapshot.is_file())
            self.assertEqual(store.recent()[0]["source"], str(source))


class SilenceTests(unittest.TestCase):
    def test_parses_closed_and_trailing_silence_with_padding(self):
        output = """
        [silencedetect] silence_start: 1
        [silencedetect] silence_end: 3 | silence_duration: 2
        [silencedetect] silence_start: 8
        """
        self.assertEqual(
            parse_silence_output(output, 10),
            [CutRange(1.1, 2.9), CutRange(8.1, 9.9)],
        )


class ThemeTests(unittest.TestCase):
    def test_explicit_theme_does_not_depend_on_windows_setting(self):
        self.assertEqual(resolved_theme(THEME_LIGHT), THEME_LIGHT)
        self.assertEqual(resolved_theme(THEME_DARK), THEME_DARK)


if __name__ == "__main__":
    unittest.main()

