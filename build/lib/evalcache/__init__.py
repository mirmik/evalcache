import hashlib
import os
import pickle
import inspect
import types

version = "0.0.1"

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

class FunctionHeader:
	def __init__(self, func, rettype):
		self.func = func
		self.rettype = rettype
		m = hashlib.sha1()
		if hasattr(func, "__qualname__"): m.update(func.__qualname__.encode("utf-8"))
		else: m.update(func.__name__.encode("utf-8"))
		if (func.__module__): m.update(func.__module__.encode("utf-8"))
		self.hsh = m.digest()
		
	def __call__(self, *args, **kwargs):
		print("__call__", *args)
		if (isinstance(self.rettype, types.FunctionType)): self.rettype = self.rettype(*args, **kwargs)
		obj = self.rettype.__construct__(self, *args, **kwargs)
		return obj


	def __get__(self, instance, cls):
		if instance is None:
			return self
		else:
			return types.MethodType(self, instance)

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

def lazy(rettype):
	def decorator(func):
		return FunctionHeader(func, rettype)
	return decorator

def lazy_universal(rettype_func):
	def decorator(func):
		return FunctionHeader(func, rettype_func)
	return decorator

def wraped_new(cls, *args, **kwargs):
	obj = cls.__wraped_class__.__new__(cls.__wraped_class__)
	cls.__wraped_class__.__init__(obj, *args, **kwargs)
	return obj

def do_nothing(*args, **kwargs):
	pass

class Bind:
	def __init__(self, func, *args, **kwargs):
		self.func = func
		self.args = args
		self.kwargs = kwargs
		self.evalhash()
		self.val = None

	@classmethod
	def __construct__(cls, funchead, *args, **kwargs):
		obj = object.__new__(cls) 
		Bind.__init__(obj, funchead, *args, **kwargs)
		return obj

	@classmethod
	def __wrapmethod__(cls, name, rettype):
		setattr(
			cls, 
			name, 
			FunctionHeader(getattr(cls.__wraped_class__, name), rettype))

	@staticmethod
	def expand(arg):
		if isinstance(arg, list): return [Bind.expand(a) for a in arg] 
		return arg.eval() if isinstance(arg, Bind) else arg

	def do(self):
		args = [Bind.expand(arg) for arg in self.args]
		kwargs = {k : Bind.expand(v) for k, v in self.kwargs.items()}
		return self.func.func(*args, **kwargs)

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
		print("load", self)
		fl = open(os.path.join(cache_directory, self.hexhsh), "rb")
		self.val = pickle.load(fl)

	def evalhash(self):
		m = hashlib.sha1()		
		m.update(gethash(str(self.__class__)))
		m.update(self.func.gethash())
		for a in self.args: 
			m.update(gethash(a))
		for k, v in sorted(self.kwargs.items()): 
			m.update(gethash(k)) 
			m.update(gethash(v))
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
	

def create_class_wrap(name, wraped_class, parent = Bind):
	T = type(name, (parent,), { "__wraped_class__": wraped_class, })
	setattr(T, "__new__", FunctionHeader(wraped_new, T))
	setattr(T, "__init__", do_nothing)
	return T