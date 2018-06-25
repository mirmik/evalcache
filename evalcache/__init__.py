print("HelloWorld")

import hashlib

class FunctionHeader:
	def __init__(self, func, hsh):
		self.func = func
		self.hash = 0

	def __call__(self, *args, **kwargs):
		return self.func(*args, **kwargs)

def lazy(func):
	m = hashlib.md5()
	m.update(func.__qualname__.encode("utf-8"))
	m.update(func.__module__.encode("utf-8"))
	hsh = m.digest()
	print(hsh)
	return FunctionHeader(func, hsh)


class Bind:
	def __init__(self, obj, func, *args, **kwargs):
		self.obj = obj
		self.func = func
		self.args = args
		self.kwargs = kwargs

	def do(self):
		if self.obj == None:
			self.func(*self.args, **self.kwargs)
		else:
			self.func(self.obj, *self.args, **self.kwargs)