import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from p0e4.resolve.aakhri_v12_repair_contract import (
    VISIBILITY_WINDOWS,
    assert_no_forbidden_overlap,
    resolve_chain_logo,
    restore_property,
    set_or_insert_scalar,
)


class RepairContractTests(unittest.TestCase):
    class FakeItem:
        def __init__(self, value, accepts=True):
            self.value = value
            self.accepts = accepts

        def GetProperty(self, _key):
            return self.value

        def SetProperty(self, _key, value):
            if self.accepts:
                self.value = value
            return self.accepts

    def test_identical_property_does_not_require_write(self):
        restore_property(self.FakeItem(0.0, accepts=False), "AnchorPointX", 0.0)

    def test_changed_property_requires_accepted_write(self):
        with self.assertRaisesRegex(RuntimeError, "cannot restore ZoomX"):
            restore_property(self.FakeItem(1.0, accepts=False), "ZoomX", 1.2)

    def test_changed_property_is_read_back(self):
        item = self.FakeItem(1.0)
        restore_property(item, "ZoomX", 1.2)
        self.assertEqual(item.value, 1.2)

    def test_authorized_windows_are_disjoint(self):
        assert_no_forbidden_overlap()
        self.assertLess(
            VISIBILITY_WINDOWS["chain_intro"][1],
            VISIBILITY_WINDOWS["opening_hook"][0],
        )
        self.assertLess(
            VISIBILITY_WINDOWS["title_artist"][1],
            VISIBILITY_WINDOWS["outro_card"][0],
        )

    def test_overlap_is_rejected(self):
        windows = dict(VISIBILITY_WINDOWS)
        windows["opening_hook"] = (40, 88)
        with self.assertRaisesRegex(RuntimeError, "chain_intro/opening_hook"):
            assert_no_forbidden_overlap(windows)

    def test_hash_bound_asset_reuses_verified_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            asset = Path(directory) / "logo.png"
            payload = b"verified-chain-logo"
            asset.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            with mock.patch(
                "p0e4.resolve.aakhri_v12_repair_contract.CHAIN_LOGO_SHA256",
                digest,
            ), mock.patch(
                "p0e4.resolve.aakhri_v12_repair_contract.urllib.request.urlretrieve",
                side_effect=AssertionError("network must not be used"),
            ):
                self.assertEqual(resolve_chain_logo(asset), asset)

    def test_hash_bound_asset_rejects_wrong_download(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "logo.png"

            def fake_download(_url, target):
                Path(target).write_bytes(b"wrong")

            with mock.patch(
                "p0e4.resolve.aakhri_v12_repair_contract.urllib.request.urlretrieve",
                side_effect=fake_download,
            ):
                with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                    resolve_chain_logo(destination)
            self.assertFalse(destination.exists())

    def test_caption_scalar_patch_is_idempotent(self):
        block = "\n\t\t\t\tStyledText = Input { Value = 'x', },"
        once = set_or_insert_scalar(block, "Opacity1", "1")
        twice = set_or_insert_scalar(once, "Opacity1", "1")
        self.assertEqual(once, twice)
        self.assertEqual(twice.count("Opacity1 = Input"), 1)

    def test_duplicate_caption_scalar_is_rejected(self):
        block = (
            "\n\t\t\t\tOpacity1 = Input { Value = 1, },"
            "\n\t\t\t\tOpacity1 = Input { Value = 1, },"
            "\n\t\t\t\tStyledText = Input { Value = 'x', },"
        )
        with self.assertRaisesRegex(RuntimeError, "duplicate Opacity1"):
            set_or_insert_scalar(block, "Opacity1", "1")


if __name__ == "__main__":
    unittest.main()
