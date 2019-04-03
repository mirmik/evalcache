import inspect


def select(obj, func):
    # print(func)
    # print(inspect.getsource(func))
    return obj.__lazybase__(lambda: [x for x in obj if func(x)], hint=func)()
