"""Subscriber registry for Practice 4.

Existing behaviour (implemented):
    - subscribe(name)
    - unsubscribe(name)   (Feature A)
    - is_subscribed(name) (Feature B)
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


def unsubscribe(name):
    """Remove a subscriber and report whether it was present.

    The name is normalized with strip(). An empty name (or a name that is
    empty after normalization) raises ValueError("empty name"). If the
    normalized name is subscribed it is removed and True is returned;
    otherwise the state is left unchanged and False is returned.
    """
    normalized = name.strip()
    if not normalized:
        raise ValueError("empty name")
    if normalized in subscribers:
        subscribers.remove(normalized)
        return True
    return False


def is_subscribed(name):
    """Report whether a subscriber is present.

    The name is normalized with strip(). An empty name (or a name that is
    empty after normalization) raises ValueError("empty name"). Returns True
    if the normalized name is subscribed and False otherwise; the state is
    left unchanged either way.
    """
    normalized = name.strip()
    if not normalized:
        raise ValueError("empty name")
    return normalized in subscribers
