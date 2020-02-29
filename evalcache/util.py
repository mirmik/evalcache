import inspect

def select(obj, func):
    return obj.__lazybase__(lambda: [x for x in obj if func(x)], hint=func)()

def _filter(func, obj):
    return obj.__lazybase__(lambda: filter(func, obj), hint=func)()

def _map(func, obj):
    return obj.__lazybase__(lambda: map(func, obj), hint=func)()

def _reduce(func, obj):
    return obj.__lazybase__(lambda: reduce(func, obj), hint=func)()

filter = _filter
map = _map
reduce = _reduce