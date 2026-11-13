"""Check startup window acquisition without relaxing live keyboard assertions."""
import subprocess
import sys
import unittest

from test_bios_menu_input_xdotool import acquire_window
from test_buffered_menu_repeat_xdotool import acquire_window as acquire_buffered_window


class WindowTests(unittest.TestCase):
    acquire = staticmethod(acquire_window)

    def probe(self, failure=None, search="2097154", operation="windowfocus"):
        calls = []

        def xdo(*args):
            calls.append(args)
            if failure and args[0] == operation:
                raise failure
            return {"search": search, "windowfocus": "", "getwindowgeometry": "X=0\nY=0\nWIDTH=960\nHEIGHT=600"}[args[0]]

        return calls, xdo

    def test_owned_visible_window(self):
        calls, xdo = self.probe()
        window, geometry = self.acquire(123, xdo)
        self.assertEqual(window, "2097154")
        self.assertEqual(geometry, {"X": "0", "Y": "0", "WIDTH": "960", "HEIGHT": "600"})
        self.assertEqual(calls, [("search", "--onlyvisible", "--pid", "123", "--name", "Larax"),
                                 ("windowfocus", "--sync", "2097154"),
                                 ("getwindowgeometry", "--shell", "2097154")])

    def test_no_window(self):
        calls, xdo = self.probe(search="")
        self.assertIsNone(self.acquire(123, xdo))
        self.assertEqual(len(calls), 1)

    def test_search_no_match(self):
        _, xdo = self.probe(subprocess.CalledProcessError(1, ["xdotool", "search"]), operation="search")
        self.assertIsNone(self.acquire(123, xdo))

    def test_focus_bad_window(self):
        _, xdo = self.probe(subprocess.CalledProcessError(1, ["xdotool", "windowfocus"], stderr="BadWindow"))
        self.assertIsNone(self.acquire(123, xdo))

    def test_geometry_bad_window(self):
        _, xdo = self.probe(subprocess.CalledProcessError(1, ["xdotool", "getwindowgeometry"], stderr="BadWindow"),
                            operation="getwindowgeometry")
        self.assertIsNone(self.acquire(123, xdo))

    def test_rediscovery_uses_new_owned_window(self):
        _, stale = self.probe(subprocess.CalledProcessError(1, ["xdotool", "windowfocus"], stderr="BadWindow"))
        self.assertIsNone(self.acquire(123, stale))
        calls, fresh = self.probe(search="4194306")
        self.assertEqual(self.acquire(123, fresh)[0], "4194306")
        self.assertEqual(calls[0][3], "123")
        self.assertEqual(calls[1][-1], "4194306")

    def test_other_focus_error_fails(self):
        _, xdo = self.probe(subprocess.CalledProcessError(1, ["xdotool", "windowfocus"], stderr="BadMatch"))
        with self.assertRaises(subprocess.CalledProcessError):
            self.acquire(123, xdo)

    def test_other_search_error_fails(self):
        _, xdo = self.probe(subprocess.CalledProcessError(2, ["xdotool", "search"]), operation="search")
        with self.assertRaises(subprocess.CalledProcessError):
            self.acquire(123, xdo)

    def test_timeout_fails(self):
        _, xdo = self.probe(subprocess.TimeoutExpired(["xdotool", "windowfocus"], 5))
        with self.assertRaises(subprocess.TimeoutExpired):
            self.acquire(123, xdo)

    def test_missing_tool_fails(self):
        _, xdo = self.probe(FileNotFoundError("xdotool"), operation="search")
        with self.assertRaises(FileNotFoundError):
            self.acquire(123, xdo)


class BufferedWindowTests(WindowTests):
    acquire = staticmethod(acquire_buffered_window)


if __name__ == "__main__":
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("bios_menu_window_contract=ok cases=20 ownership=pid visible=1 badwindow_only=1 no_game_restart=1")
