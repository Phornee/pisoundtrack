""" Unit tests """
import unittest

from pisoundtrack import Soundtrack


class Testing(unittest.TestCase):
    """Unittesting class"""

    soundtrack = Soundtrack()

    def test_000_open_device(self):
        """ Testing open device function
        """
        stream, input_frames_per_block = self.soundtrack.open_device('unexisting')

        self.assertEqual(stream, None)

if __name__ == "__main__":
    unittest.main()
