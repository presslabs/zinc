from functools import wraps


def memoized_property(method):
    """
    Caches a method's return value on the instance.
    """
    @property
    @wraps(method)
    def caching_wrapper(self):
        cache_key = "__cached_" + method.__name__
        if not hasattr(self, cache_key):
            return_value = method(self)
            setattr(self, cache_key, return_value)
        return getattr(self, cache_key)
    return caching_wrapper
