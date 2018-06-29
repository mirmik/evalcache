import hashlib
import os
import pickle
import inspect
import types

version = "0.0.2"

cache_directory = ".evalcache"
cache_enabled = False

files = None

hashfuncs = {}

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

class LazyFunction:
	def __init__(self, func, rettype):
		self.func = func
		self.rettype = rettype
		m = hashlib.sha1()
		if hasattr(func, "__qualname__"): m.update(func.__qualname__.encode("utf-8"))
		elif hasattr(func, "__name__") : m.update(func.__name__.encode("utf-8"))
		else: m.update(func.encode("utf-8")) 
		if hasattr(func, "__module__") and func.__module__: m.update(func.__module__.encode("utf-8"))
		self.__lazyhash__ = m.digest()
		
	def __call__(self, *args, **kwargs):
		if (isinstance(self.rettype, types.FunctionType)): self.rettype = self.rettype(*args, **kwargs)
		obj = self.rettype.__construct__(self, *args, **kwargs)
		return obj

	def __get__(self, instance, cls):
		if instance is None:
			return self
		else:
			return types.MethodType(self, instance)

def wraped_new(cls, *args, **kwargs):
	obj = cls.__wraped_class__.__new__(cls.__wraped_class__)
	cls.__wraped_class__.__init__(obj, *args, **kwargs)
	return obj

def do_nothing(*args, **kwargs):
	pass

class LazyObject:
	def __init__(self, func, *args, **kwargs):
		self.func = func
		self.args = args
		self.kwargs = kwargs
		m = hashlib.sha1()		
		m.update(gethash(str(self.__class__)))
		m.update(self.func.__lazyhash__)
		for a in self.args: 
			m.update(gethash(a))
		for k, v in sorted(self.kwargs.items()): 
			m.update(gethash(k)) 
			m.update(gethash(v))
		self.__lazyhash__ = m.digest()
		self.__lazyhexhash__ = m.hexdigest()
		self.__lazyvalue__ = None

	@classmethod
	def __construct__(cls, funchead, *args, **kwargs):
		obj = object.__new__(cls) 
		LazyObject.__init__(obj, funchead, *args, **kwargs)
		return obj

	@classmethod
	def __wrapmethod__(cls, name, rettype, wrapfunc = None):
		if (wrapfunc == None): wrapfunc = name
		setattr(cls, name, LazyFunction(wrapfunc, rettype))

	@staticmethod
	def __lazyexpand__(arg):
		if isinstance(arg, list): return [LazyObject.expand(a) for a in arg] 
		return arg.eval() if isinstance(arg, LazyObject) else arg

	def __lazydo__(self):
		args = [LazyObject.__lazyexpand__(arg) for arg in self.args]
		kwargs = {k : LazyObject.__lazyexpand__(v) for k, v in self.kwargs.items()}
		if (isinstance(self.func.func, str)):
			func = getattr(args[0], self.func.func)
			return func(*args[1:], **kwargs)
		else: 
			func = self.func.func
			return func(*args, **kwargs)

	def __lazyeval__(self):
		if (self.__lazyvalue__ != None):
			return self.__lazyvalue__

		if cache_enabled and self.__lazyhexhash__ in files:
			print("load", self.__lazyhexhash__)
			fl = open(os.path.join(cache_directory, self.__lazyhexhash__), "rb")
			self.__lazyvalue__ = pickle.load(fl)
			return self.__lazyvalue__

		self.__lazyvalue__ = self.__lazydo__()
		if cache_enabled: 
			print("save", self.__lazyhexhash__)
			fl = open(os.path.join(cache_directory, self.__lazyhexhash__), "wb")
			pickle.dump(self.__lazyvalue__, fl)
		return self.__lazyvalue__		

	def do(self): return self.__lazydo__()
	
	def eval(self): return self.__lazyeval__()

def gethash(obj):
	try:
		return obj.__lazyhash__
	except(Exception):
		pass
	if isinstance(obj, str):
		return obj.encode("utf-8")
	if isinstance(obj, int) or isinstance(obj, float):
		return str(obj).encode("utf-8")
	if isinstance(obj, tuple) or isinstance(obj, list):
		m = hashlib.sha1()
		for a in obj: 
			m.update(gethash(a))
		return m.digest()
	if obj.__class__ in hashfuncs:
		return hashfuncs[obj.__class__](obj)
	else:
		m = hashlib.sha1()
		m.update(str(obj.__class__).encode("utf-8"))
		m.update(str(sorted(obj.__dict__)).encode("utf-8"))
		return m.digest()
	

def create_class_wrap(name, parent = LazyObject, wrapclass = None):
	T = type(
		name, 
		(parent,), 
		{ "__wraped_class__": wrapclass, } if wrapclass else {}
	)
	if wrapclass:
		setattr(T, "__new__", LazyFunction(wraped_new, T))
		setattr(T, "__init__", do_nothing)
	return T

def lazy(rettype = LazyObject):
	def decorator(func):
		return LazyFunction(func, rettype)
	return decorator

def lazy_universal(rettype_func):
	def decorator(func):
		return LazyFunction(func, rettype_func)
	return decorator
