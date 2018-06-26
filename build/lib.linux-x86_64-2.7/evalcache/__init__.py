import hashlib
import os
import pickle

version = "0.0.1"

cache_directory = ".evalcache"
cache_enabled = False

files = None

def enable():
	global files
	global cache_enabled
	cache_enabled = True
	if not os.path.exists(cache_directory):
		os.system("mkdir {}".format(cache_directory))
		files = set()
		return

	lst = os.listdir(cache_directory)
	files = set(lst)
	print(sorted(files))

class FunctionHeader:
	def __init__(self, func, hsh):
		self.func = func
		self.hsh = hsh

	def __call__(self, *args, **kwargs):
		return Bind(None, self, *args, **kwargs)

	def gethash(self):
		return self.hsh

def lazy(func):
	m = hashlib.sha1()
	m.update(func.__qualname__.encode("utf-8"))
	m.update(func.__module__.encode("utf-8"))
	hsh = m.digest()
	return FunctionHeader(func, hsh)

class Bind:
	def __init__(self, obj, func, *args, **kwargs):
		self.obj = obj
		self.func = func
		self.args = args
		self.kwargs = kwargs
		self.evalhash()
		self.val = None

	def do(self):
		args = [arg.eval() if isinstance(arg, Bind) else arg for arg in self.args]
		kwargs = {}
		if self.obj == None:
			return self.func.func(*args, **kwargs)
		else:
			return self.func.func(self.obj, *args, **kwargs)

	def eval(self):
		if (self.val != None):
			return self.val

		if cache_enabled and self.hexhsh in files:
			self.load()
			return self.val

		self.val = self.do()
		if cache_enabled: self.save()
		return self.val		

	def save(self):
		print("save")
		fl = open(os.path.join(cache_directory, self.hexhsh), "wb")
		pickle.dump(self.val, fl)

	def load(self):
		print("load")
		fl = open(os.path.join(cache_directory, self.hexhsh), "rb")
		self.val = pickle.load(fl)

	def evalhash(self):
		m = hashlib.sha1()
		if self.obj != None: m.update(gethash(self.obj))
		m.update(gethash(self.func))
		for a in self.args: 
			m.update(gethash(a))
		self.hsh = m.digest()
		self.hexhsh = m.hexdigest()

	def gethash(self):
		return self.hsh

def gethash(obj):
	try:
		return obj.gethash()
	except(Exception):
		pass
	if isinstance(obj, str):
		return obj.encode("utf-8")
	if isinstance(obj, int) or isinstance(obj, float):
		return str(obj).encode("utf-8")
	else:
		m = hashlib.sha1()
		m.update(str(obj.__class__).encode("utf-8"))
		m.update(str(obj.__dict__).encode("utf-8"))
		return m.digest()
	