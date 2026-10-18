"""Evidence gate rejects missing observations and unexpected retained pixels."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
from native_lab.classify import main, validate_report
from native_lab.launcher import ROOT, classify_observation, inspect_images, sha256


class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.scenarios = json.loads((ROOT / 'native_scenarios.json').read_text())
        self.case = self.scenarios['cases'][1]
        self.path = self.root / 'comparison.json'
        self.report = self.fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, root, negative=False):
        root.mkdir(exist_ok=True)
        (root / 'scenarios.json').write_text(json.dumps(self.scenarios))
        report = dict(schema_version=1, status='mismatch' if negative else 'pass',
                      negative_control=negative, reasons=[], run_token=str(root),
                      scenario_sha256=sha256(ROOT / 'native_scenarios.json'),
                      pins=json.loads((ROOT / 'pins.json').read_text()), sources={}, builds={}, native_events={},
                      alive_after_observation={}, resize=dict(status='pass', requested=[320,224],
                      event_confirmed={}, captures={}, actual_capture_sizes={}))
        for role in ('upstream', 'moonbit'):
            image = Image.new('RGB', (256,192))
            ImageDraw.Draw(image).rectangle((32,32,95,79), fill='blue' if negative and role == 'moonbit' else 'red')
            image.save(root / f'{role}.png')
            image.resize((320,224)).save(root / f'{role}-resized.png')
            records = [dict(protocol=1, implementation=role, run_token=report['run_token'],
                            event=event, width=w, height=h, scale=1)
                       for event,w,h in [('frame_ready',256,192), ('resized',320,224)]]
            (root / f'{role}.stdout').write_text(''.join('GPUI_NATIVE_LAB '+json.dumps(r)+'\n' for r in records))
            report['native_events'][role] = records
            report['sources'][role] = dict(revision=report['pins'][role]['revision'], dirty=False)
            report['builds'][role] = dict(returncode=0)
            report['alive_after_observation'][role] = True
            report['resize']['event_confirmed'][role] = True
            report['resize']['actual_capture_sizes'][role] = [320,224]
            report['resize']['captures'][role] = dict(path=f'{role}-resized.png', sha256=sha256(root / f'{role}-resized.png'))
        report['pixels'] = inspect_images({r: root / f'{r}.png' for r in ('upstream','moonbit')}, self.case, 1)
        (root / 'comparison.json').write_text(json.dumps(report))
        return report

    def save(self):
        self.path.write_text(json.dumps(self.report))

    def test_report_from_other_pins_is_rejected(self):
        self.report['pins']['moonbit']['revision'] = 'b'*40
        self.report['sources']['moonbit']['revision'] = 'b'*40
        self.save()
        self.assertEqual(main([str(self.path)]), 1)

    def test_complete_retained_pair_passes(self):
        self.assertEqual(main([str(self.path)]), 0)

    def test_missing_or_broken_json_never_passes(self):
        self.assertEqual(main([str(self.root / 'missing.json')]), 1)
        for text in ('{', 'null', '[]', '{}', '{"status":"pass"}'):
            with self.subTest(text=text):
                self.path.write_text(text)
                self.assertEqual(main([str(self.path)]), 1)

    def test_nonpassing_or_unknown_status_and_nonempty_reasons_fail(self):
        for status in ('unverified','mismatch','unknown',None):
            self.report['status'] = status
            self.save()
            self.assertEqual(main([str(self.path)]), 1)
        self.report.update(status='pass', reasons=['missing resize'])
        self.save()
        self.assertEqual(main([str(self.path)]), 1)

    def test_cursor_overlay_outside_sample_points_is_rejected(self):
        path = self.root / 'moonbit.png'
        with Image.open(path) as image:
            ImageDraw.Draw(image).rectangle((128,89,140,110), fill=(128,128,128))
            image.save(path)
        measured = inspect_images({r: self.root / f'{r}.png' for r in ('upstream','moonbit')}, self.case, 1)
        self.assertTrue(measured['same_sample_colors'])
        self.assertEqual(measured['status'], 'mismatch')
        self.assertEqual(measured['captures']['moonbit']['unexpected_pixels'], 13*22)
        self.assertEqual(main([str(self.path)]), 1)
        self.report['pixels'] = measured
        self.save()
        self.assertEqual(main([str(self.path)]), 1)

    def test_even_clipped_cursor_at_last_pixel_is_rejected(self):
        path = self.root / 'moonbit.png'
        with Image.open(path) as image:
            image.putpixel((255,191), (128,128,128))
            image.save(path)
        measured = inspect_images({r: self.root / f'{r}.png' for r in ('upstream','moonbit')}, self.case, 1)
        self.assertEqual(measured['different_pixels'], 1)
        self.assertEqual(measured['status'], 'mismatch')

    def test_identical_unexpected_pixels_in_both_images_are_rejected(self):
        for role in ('upstream','moonbit'):
            path = self.root / f'{role}.png'
            with Image.open(path) as image:
                image.putpixel((200,150), (255,255,255))
                image.save(path)
        measured = inspect_images({r: self.root / f'{r}.png' for r in ('upstream','moonbit')}, self.case, 1)
        self.assertEqual(measured['different_pixels'], 0)
        self.assertEqual(measured['status'], 'mismatch')

    def test_missing_resize_capture_or_log_is_rejected(self):
        for name in ('moonbit-resized.png', 'moonbit.stdout'):
            path = self.root / name
            data = path.read_bytes()
            path.unlink()
            self.assertEqual(main([str(self.path)]), 1)
            path.write_bytes(data)

    def test_missing_resize_event_cannot_be_overridden_by_pixel_mismatch(self):
        manifest = dict(reasons=['missing resize'], pixels=dict(status='mismatch'), resize=dict(status='unverified'))
        self.assertEqual(classify_observation(manifest), 'unverified')
        manifest['reasons'] = []
        self.assertEqual(classify_observation(manifest), 'unverified')
        manifest['resize']['status'] = 'pass'
        self.assertEqual(classify_observation(manifest), 'mismatch')
        for reason in ('missing frame', 'child exited', 'pointer park failed'):
            manifest['reasons'] = [reason]
            self.assertEqual(classify_observation(manifest), 'unverified')

    def test_resize_claim_without_event_is_rejected(self):
        self.report['native_events']['moonbit'] = self.report['native_events']['moonbit'][:1]
        (self.root / 'moonbit.stdout').write_text('GPUI_NATIVE_LAB '+json.dumps(self.report['native_events']['moonbit'][0])+'\n')
        self.save()
        self.assertEqual(main([str(self.path)]), 1)

    def test_negative_control_requires_exact_blue_runtime_capture(self):
        self.assertEqual(main([str(self.path), '--require-negative-control']), 1)
        control = self.root / 'negative-control'
        self.fixture(control, True)
        self.assertEqual(main([str(self.path), '--require-negative-control']), 0)
        self.fixture(control, False)
        self.assertEqual(main([str(self.path), '--require-negative-control']), 1)

    def test_negative_control_cannot_pass_from_unrelated_mismatch(self):
        control = self.root / 'negative-control'
        negative = self.fixture(control, True)
        path = control / 'moonbit.png'
        with Image.open(path) as image:
            image.putpixel((200,150), (255,255,255))
            image.save(path)
        negative['pixels'] = inspect_images({r: control / f'{r}.png' for r in ('upstream','moonbit')}, self.case, 1)
        (control / 'comparison.json').write_text(json.dumps(negative))
        self.assertEqual(main([str(self.path), '--require-negative-control']), 1)


if __name__ == '__main__':
    unittest.main()
