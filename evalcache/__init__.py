import hashlib
import os
import pickle
import inspect

version = "0.0.1"

cache_directory = ".evalcache"
cache_enabled = False

files = None

class Self: pass

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
	def __init__(self, func, rettype):
		print("FunctionHeader.__init__", func, rettype)
		self.func = func
		self.rettype = rettype
		m = hashlib.sha1()
		m.update(func.__qualname__.encode("utf-8"))
		if (func.__module__): m.update(func.__module__.encode("utf-8"))
		self.hsh = m.digest()
		
	def __call__(self, *args, **kwargs):
		print("FunctionHeader.__call__", self, *args, **kwargs)
		obj = self.rettype.__construct__(self.rettype, self, *args, **kwargs)
		return obj

	def gethash(self):
		return self.hsh

#class MethodHeader:
#	def __init__(self, obj, func):
#		self.func = func
#		m = hashlib.sha1()
#		m.update(func.__qualname__.encode("utf-8"))
#		m.update(func.__module__.encode("utf-8"))
#		self.hsh = m.digest()
		
#	def __call__(self, *args, **kwargs):
#		return Bind(self, *args, **kwargs)

#	def gethash(self):
#		return self.hsh

def lazy(func):
	return FunctionHeader(func)

def wraped_new(cls, *args, **kwargs):
	print("wraped_new")

	obj = cls.__wraped_class__.__new__(cls.__wraped_class__)
	cls.__wraped_class__.__init__(obj, *args, **kwargs)
	return obj

def do_nothing(*args, **kwargs):
	pass

def create_class_wrap(name, wraped_class):
	print("create_class_wrap")
	T = type(name, (Bind,), { "__wraped_class__": wraped_class, })
	setattr(T, "__new__", FunctionHeader(wraped_new, T))
	setattr(T, "__init__", do_nothing)
	return T

class Bind:
	def __init__(self, func, *args, **kwargs):
		print("Bind.__init__", self, func, *args)
		self.func = func
		self.args = args
		self.kwargs = kwargs
		self.evalhash()
		self.val = None

	def __construct__(cls, funchead, *args, **kwargs):
		print("Bind.__construct__", cls, funchead, *args, **kwargs)

		obj = object.__new__(cls)
		Bind.__init__(obj, funchead, *args, **kwargs)
		return obj


	def __wrapmethod__(cls, name, rettype):
		setattr(
			cls, 
			name, 
			FunctionHeader(getattr(rettype.__wraped_class__, name), rettype))

	def __wrapmethods__(dict):
		pass

	def do(self):
		args = [arg.eval() if isinstance(arg, Bind) else arg for arg in self.args]
		kwargs = {}
		#if self.obj == None:
		print("555",self.func)
		return self.func.func(*self.args, **self.kwargs)
		#else:
		#	return self.func.func(self.obj, *args, **kwargs)

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
		m.update(gethash(self.func))
		for a in self.args: 
			m.update(gethash(a))
		self.hsh = m.digest()
		self.hexhsh = m.hexdigest()

	def gethash(self):
		return self.hsh
		#print(attr)

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
	