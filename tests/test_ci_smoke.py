"""CI smoke check for test discovery and execution."""
import unittest


class CISmokeTests(unittest.TestCase):
    def test_unittest_discovery(self):
        self.assertTrue(True)
