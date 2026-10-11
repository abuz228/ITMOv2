"""Independent unittest tests for service.subscribe."""

import unittest

from service import subscribers, subscribe


class SubscribeTests(unittest.TestCase):
    def setUp(self):
        subscribers.clear()

    def test_subscribe_normal(self):
        result = subscribe("alice")

        self.assertEqual(result, "alice")
        self.assertIn("alice", subscribers)
        self.assertEqual(subscribers, {"alice"})

    def test_subscribe_empty_name(self):
        with self.assertRaises(ValueError) as ctx:
            subscribe("   ")

        self.assertEqual(str(ctx.exception), "empty name")
        self.assertEqual(subscribers, set())

    def test_subscribe_twice_no_duplicates(self):
        subscribe("alice")
        subscribe("alice")

        self.assertEqual(subscribers, {"alice"})
        self.assertEqual(len(subscribers), 1)


if __name__ == "__main__":
    unittest.main()
