"""Independent unittest tests for service.subscribe."""

import unittest

import service
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


class UnsubscribeTests(unittest.TestCase):
    def setUp(self):
        subscribers.clear()

    def test_unsubscribe_existing_returns_true_and_removes(self):
        subscribe("alice")

        result = service.unsubscribe("alice")

        self.assertIs(result, True)
        self.assertNotIn("alice", subscribers)
        self.assertEqual(subscribers, set())

    def test_unsubscribe_missing_returns_false_and_keeps_state(self):
        subscribe("alice")

        result = service.unsubscribe("bob")

        self.assertIs(result, False)
        self.assertEqual(subscribers, {"alice"})

    def test_unsubscribe_normalizes_name(self):
        subscribe("alice")

        result = service.unsubscribe("  alice  ")

        self.assertIs(result, True)
        self.assertEqual(subscribers, set())

    def test_unsubscribe_empty_name(self):
        subscribe("alice")

        with self.assertRaises(ValueError) as ctx:
            service.unsubscribe("")

        self.assertEqual(str(ctx.exception), "empty name")
        self.assertEqual(subscribers, {"alice"})

    def test_unsubscribe_whitespace_name(self):
        subscribe("alice")

        with self.assertRaises(ValueError) as ctx:
            service.unsubscribe("   ")

        self.assertEqual(str(ctx.exception), "empty name")
        self.assertEqual(subscribers, {"alice"})

    def test_unsubscribe_twice_second_returns_false(self):
        subscribe("alice")

        first = service.unsubscribe("alice")
        second = service.unsubscribe("alice")

        self.assertIs(first, True)
        self.assertIs(second, False)
        self.assertEqual(subscribers, set())

    def test_subscribe_still_works_after_unsubscribe(self):
        subscribe("alice")
        service.unsubscribe("alice")

        result = subscribe("alice")

        self.assertEqual(result, "alice")
        self.assertEqual(subscribers, {"alice"})


if __name__ == "__main__":
    unittest.main()
