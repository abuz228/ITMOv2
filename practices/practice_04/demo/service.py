"""Subscriber registry for Practice 4.

Existing behaviour (implemented):
    - subscribe(name)

Feature A (unsubscribe) and Feature B (is_subscribed) are described in
docs/requirements.md and are NOT implemented yet.
"""

subscribers = set()


def subscribe(name):
    """Add a subscriber and return the normalized name.

    The name is normalized with strip(). An empty name (or a name that is
    empty after normalization) raises ValueError("empty name"). Subscribing
    the same name twice does not create duplicates.
    """
    normalized = name.strip()
    if not normalized:
        raise ValueError("empty name")
    subscribers.add(normalized)
    return normalized
