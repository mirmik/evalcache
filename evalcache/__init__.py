#coding: utf-8
##@file evalcache/__init__.py
##
##Lazy evaluation cache library
##@author mirmik(mirmikns@yandex.ru)

import hashlib
import types

from evalcache.dircache import DirCache 

version = "0.2.0" 
diagnostic_enabled = False

def enable_diagnostic():
	"""Enable console output about cache operations"""
	global diagnostic_enabled
	diagnostic_enabled = True

class Lazy:
	"""Base library class. Decorator for callable lazifying.

	Arguments:
	----------
	cache -- dict-like object, which store and load evaluation's results (f.e. DirCache or dict)
	algo -- hashing algorithm for keys making. (hashlib-like) 
	"""

	def __init__(self, cache, algo = hashlib.sha256):
		self.cache = cache
		self.algo = algo

	def __call__(self, func):
		"""Construct lazy wrap for callable."""
		return LazyGeneric(self, func)

class LazyObject:
	"""Lazytree element's interface.

	A lazy object provides a rather abstract interface. We can use attribute getting or operators for
	generate another lazy objects.

	The technical problem is that a lazy wrapper does not know the type of wraped object before unlazing.
	Therefore, we assume that any action on a lazy object is a priori true. If the object does not support 
	the manipulation performed on it, we will know about it at the execution stage.
	
	Arguments:
	----------
	lazifier -- parental lazy decorator
	"""

	def __init__(self, lazifier): 
		self.__lazybase__ = lazifier

	def __call__(self, *args, **kwargs): return LazyResult(self.__lazybase__, self, args, kwargs)
	
	def __getattr__(self, item): return LazyResult(self.__lazybase__, getattr, (self, item))
	def __getitem__(self, item): return LazyResult(self.__lazybase__, lambda x, i: x[i], (self, item))

	def __add__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x + y, (self, oth))
	def __sub__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x - y, (self, oth))
	def __xor__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x ^ y, (self, oth))
	def __mul__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x * y, (self, oth))
	def __div__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x / y, (self, oth))

	def __eq__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x == y, (self, oth))
	def __ne__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x != y, (self, oth))
	def __lt__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x <  y, (self, oth))
	def __le__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x <= y, (self, oth))
	def __gt__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x >  y, (self, oth))
	def __ge__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x >= y, (self, oth))

	def unlazy(self):
		"""Get result of evaluation.

		See .unlazy function for details.
		
		Disclamer:
		Technically, the calculated object can turn out to be a "unlazy" method. 
		In this case it turns out that we have hidden such a method. But using the unlazy function is more 
		convenient in the method format, so I decided to sacrifice this variant."""
		
		ret = unlazy(self)
		if hasattr(ret, "unlazy"):
			print("WARNING: Shadow unlazy method.")
		return ret

class LazyResult(LazyObject):
	""""""

	def __init__(self, lazifier, generic, args = (), kwargs = {}):
		LazyObject.__init__(self, lazifier)	
		self.generic = generic
		self.args = args
		self.kwargs = kwargs
		self.__lazyvalue__ = None
		
		m = self.__lazybase__.algo()		
		updatehash(m, self.generic)
		if len(args): updatehash(m, args)
		if len(kwargs): updatehash(m, kwargs)

		self.__lazyhash__ = m.digest()
		self.__lazyhexhash__ = m.hexdigest()

	def __repr__(self): return "<LazyResult(generic:{},args:{},kwargs:{})>".format(self.generic, self.args, self.kwargs)

class LazyGeneric(LazyObject):
	"""Lazy function wraper.

	End point of lazy tree. Special LazyObject type for wrap callables as function, methods, ctors, functors...
	It constructed in Lazy.__call__.

	Arguments:
	----------
	lazifier -- parental lazy decorator
	func -- wrapped callable
	"""

	def __init__(self, lazifier, func):
		LazyObject.__init__(self, lazifier)
		self.__lazyvalue__ = func
		
		m = self.__lazybase__.algo()
		updatehash(m, func)
		
		self.__lazyhash__ = m.digest()
		self.__lazyhexhash__ = m.hexdigest()

	def __get__(self, instance, cls):
		"""With __get__method we can use lazy decorator on class's methods"""
		if instance is None:
			return self
		else:
			return types.MethodType(self, instance)

	def __repr__(self): return "<LazyGeneric(value:{})>".format(self.__lazyvalue__)

def lazydo(obj):
		"""Perform evaluation.

		We need expand all arguments and callable for support lazy trees."""
		func = expand(obj.generic)
		args = expand(obj.args)
		kwargs = expand(obj.kwargs)
		return func(*args, **kwargs)

def unlazy(obj):
	"""Get result of evaluation.

	This function trying find object in local memory (fget), then in cache (load).
	If object wasn't stored early, perform evaluation and store result in cache and local memory. 		
	"""
	if (obj.__lazyvalue__ != None):
		if diagnostic_enabled: print('fget', obj.__lazyhexhash__)
		return obj.__lazyvalue__

	if obj.__lazyhexhash__ in obj.__lazybase__.cache:
		if diagnostic_enabled: print('load', obj.__lazyhexhash__)
		obj.__lazyvalue__ = obj.__lazybase__.cache[obj.__lazyhexhash__]
		return obj.__lazyvalue__
	else:
		obj.__lazyvalue__ = lazydo(obj)		
		if diagnostic_enabled: print('save', obj.__lazyhexhash__)
		obj.__lazybase__.cache[obj.__lazyhexhash__] = obj.__lazyvalue__
		return obj.__lazyvalue__

def expand(arg):
	"""Apply unlazy operation for argument or for all argument's items if need."""
	if isinstance(arg, list) or isinstance(arg, tuple): return [ expand(a) for a in arg ] 
	elif isinstance(arg, dict) : return { k : expand(v) for k, v in arg.items() }
	else: return unlazy(arg) if isinstance(arg, LazyObject) else arg

def updatehash_list(m, obj):
	for e in obj:
		updatehash(m, e)

def updatehash_dict(m, obj):
	for k, v in sorted(obj.items()):
		updatehash(m, k)
		updatehash(m, v)

def updatehash_LazyObject(m, obj):
	m.update(obj.__lazyhash__)

def updatehash_function(m, obj):
	if hasattr(obj, "__qualname__"): 
		m.update(obj.__qualname__.encode("utf-8"))
	elif hasattr(obj, "__name__") : 
		m.update(obj.__name__.encode("utf-8"))
	if hasattr(obj, "__module__") and obj.__module__: 
		m.update(obj.__module__.encode("utf-8"))

## Table of hash functions for special types.
hashfuncs = {
	LazyGeneric: updatehash_LazyObject,
	LazyResult: updatehash_LazyObject,
	tuple: updatehash_list,
	list: updatehash_list,
	dict: updatehash_dict,
	types.FunctionType: updatehash_function,
}

def updatehash(m, obj):
	"""Update hash in hashlib-like algo with hashable object

	As usual we use hash of object representation, but for special types we can set
	special updatehash functions (see 'hashfuncs' table).

	Warn: If you use changing between program starts object representation (f.e. object.__repr__)
	for hashing, this library will not be work corectly. 

	Arguments
	---------
	m -- hashlib-like algorithm instance.
	obj -- hashable object
	"""
	if obj.__class__ in hashfuncs:
		hashfuncs[obj.__class__](m, obj)
	else:
		if obj.__class__.__repr__ == object.__repr__:
			print("WARNING: object of class {} uses common __repr__ method. Сache may not work correctly"
				.format(obj.__class__))
		m.update(repr(obj).encode("utf-8"))

__tree_tab = "    "
def print_tree(obj, t = 0):
	"""Print lazy tree in user friendly format."""	
	if isinstance(obj, LazyResult):
		print(__tree_tab*t, end=''); print("LazyResult:")
		print(__tree_tab*t, end=''); print("|generic:\n", end=''); print_tree(obj.generic, t+1)
		if (len(obj.args)): print(__tree_tab*t, end=''); print("|args:\n", end=''); print_tree(obj.args, t+1)
		if (len(obj.kwargs)): print(__tree_tab*t, end=''); print("|kwargs:\n", end=''); print_tree(obj.kwargs, t+1)
		print(__tree_tab*t, end=''); print("-------")
	elif isinstance(obj, list) or isinstance(obj, tuple):
		for o in obj:
			print_tree(o, t)
	else:
		print(__tree_tab*t, end=''); print(obj)