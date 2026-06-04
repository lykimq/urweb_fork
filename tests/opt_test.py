import unittest
import urllib.request

class Suite(unittest.TestCase):
    def test_1(self):
        # Fetch the root page
        with urllib.request.urlopen('http://localhost:8080/main') as response:
            html = response.read().decode('utf-8')
            # Verify the output produced by polymorphic identity function
            self.assertIn('42', html)
            self.assertIn('hello', html)
