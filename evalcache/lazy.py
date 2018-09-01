#coding: utf-8

import sys
import types
import hashlib
import binascii

class Lazy:
	"""Decorator for endpoint objects lazifying.

	Arguments:
	----------
	cache -- dict-like object, which stores and loads evaluation's results (f.e. DirCache or dict)
	algo -- hashing algorithm for keys making. (hashlib-like)
	encache -- default state of enabling cache storing
	decache -- default state of enabling cache loading
	diag -- diagnostic output
	"""

	def __init__(self, cache, algo = hashlib.sha256, encache = True, decache = True, diag = False):
		self.cache = cache
		self.algo = algo
		self.encache = encache
		self.decache = decache
		self.diag = diag

	def __call__(self, wrapped_object):
		"""Construct lazy wrap for target object."""
		return LazyObject(self, value = wrapped_object)

class LazyObject:
	"""Lazytree element's interface.

	A lazy object provides a rather abstract interface. We can use attribute getting or operators to
	generate another lazy objects.

	The technical problem is that a lazy wrapper does not know the type of wraped object before unlazing.
	Therefore, we assume that any action on a lazy object is a priori true. If the object does not support 
	the manipulation performed on it, we will know about it at the execution stage.
	
	Arguments:
	----------
	lazifier -- parental lazy decorator
	generic -- callable that construct this object
	args -- call arguments
	kwargs -- call keyword arguments
	encache -- True if need to store to cache. 
	value -- force set __lazyvalue__. Uses for endpoint objects.
	"""

	def __init__(self, lazifier, generic = None, args = (), kwargs = {}, encache = None, decache = None, value = None): 
		self.__lazybase__ = lazifier
		self.__encache__ = encache if encache is not None else self.__lazybase__.encache
		self.__decache__ = decache if decache is not None else self.__lazybase__.decache

		self.generic = generic
		self.args = args
		self.kwargs = kwargs
		self.__lazyvalue__ = value
		
		m = self.__lazybase__.algo()		
		if generic: updatehash(m, generic)
		if len(args): updatehash(m, args)
		if len(kwargs): updatehash(m, kwargs)
		if value is not None: updatehash(m, value)

		self.__lazyhash__ = m.digest()
		self.__lazyhexhash__ = m.hexdigest()

	def __call__(self, *args, **kwargs): return LazyObject(self.__lazybase__, self, args, kwargs)
	
	def __getattr__(self, item): return LazyObject(self.__lazybase__, getattr, (self, item), encache = False, decache = False)
	def __getitem__(self, item): return LazyObject(self.__lazybase__, lambda x, i: x[i], (self, item))

	def __add__(self, oth): return LazyObject(self.__lazybase__, lambda x,y: x + y, (self, oth))
	def __sub__(self, oth): return LazyObject(self.__lazybase__, lambda x,y: x - y, (self, oth))
	def __xor__(self, oth): return LazyObject(self.__lazybase__, lambda x,y: x ^ y, (self, oth))
	def __mul__(self, oth): return LazyObject(self.__lazybase__, lambda x,y: x * y, (self, oth))
	def __div__(self, oth): return LazyObject(self.__lazybase__, lambda x,y: x / y, (self, oth))

	def __eq__(self, oth): return LazyObject(self.__lazybase__, lambda x,y: x == y, (self, oth))
	def __ne__(self, oth): return LazyObject(self.__lazybase__, lambda x,y: x != y, (self, oth))
	def __lt__(self, oth): return LazyObject(self.__lazybase__, lambda x,y: x <  y, (self, oth))
	def __le__(self, oth): return LazyObject(self.__lazybase__, lambda x,y: x <= y, (self, oth))
	def __gt__(self, oth): return LazyObject(self.__lazybase__, lambda x,y: x >  y, (self, oth))
	def __ge__(self, oth): return LazyObject(self.__lazybase__, lambda x,y: x >= y, (self, oth))

	def __get__(self, instance, cls):
		"""With __get__ method we can use lazy decorator on class's methods"""
		if (instance is not None) and isinstance(self.__lazyvalue__, types.FunctionType):
			return types.MethodType(self, instance)
		else:
			return self

	def __hash__(self):
		return int(binascii.hexlify(self.__lazyhash__), 16)

	def unlazy(self):
		"""Get a result of evaluation.

		See .unlazy function for details.
		
		Disclamer:
		Technically, the evaluated object can define an "unlazy" method.
		If so, we'll hide such the method. However since using the unlazy 
		function is more convenient as the method, so this option was excluded."""		
		ret = unlazy(self)
		if hasattr(ret, "unlazy"):
			print("WARNING: Shadow unlazy method.")
		return ret

def lazydo(obj):
	"""Perform evaluation.

	We need expand all arguments and callable for support lazy trees.
	Such we should expand result becourse it can be LazyObject (f.e. lazy functions in lazy functions)
	"""
	func = expand(obj.generic)
	args = expand(obj.args)
	kwargs = expand(obj.kwargs)
	result = expand(func(*args, **kwargs)) 
	return result

def unlazy(obj):
	"""Get a result of evaluation.

	This function searches for the result in local memory, and after that in cache.
	If object wasn't stored early, it performs evaluation and stores a result in cache and local memory.
	If object has disabled __encache__ storing prevented.
	If object has disabled __decache__ loading prevented.
	"""
	diagnostic = obj.__lazybase__.diag
	diag = lambda t: print(t, obj.__lazyhexhash__) if diagnostic else lambda t : None

	# If local context was setted we can return object imediatly
	if (obj.__lazyvalue__ is not None):
		# Load from local context ...
		if obj.generic is None:
			# for endpoint object.
			diag('endp') 
		else:
			# for early executed object.
			diag('fget')				
	
	# Now searhes object in cache, if not prevented.
	elif obj.__decache__ and obj.__lazyhexhash__ in obj.__lazybase__.cache:
		# Load from cache.
		diag('load')
		obj.__lazyvalue__ = obj.__lazybase__.cache[obj.__lazyhexhash__]
	
	# Object wasn't stored early. Evaluate it. Store it if not prevented.
	else:
		# Execute ...
		obj.__lazyvalue__ = lazydo(obj)		
		if obj.__encache__:
			# with storing.
			diag('save')
			obj.__lazybase__.cache[obj.__lazyhexhash__] = obj.__lazyvalue__
		else:
			# without storing.
			diag('eval')

	return obj.__lazyvalue__						

def expand(arg):
	"""Apply unlazy operation for argument or for all argument's items if need.
	LazyObject as dictionary key can be used.

	TODO: Need construct expand functions table for compat with user's collections.
	"""
	if isinstance(arg, list) or isinstance(arg, tuple): return [ expand(a) for a in arg ]
	elif isinstance(arg, dict) : return { expand(k) : expand(v) for k, v in arg.items() }
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
	if obj.__qualname__ == "<lambda>":
		print("WARNING: evalcache cann't work with global lambdas correctly")
	if hasattr(obj, "__qualname__"): 
		m.update(obj.__qualname__.encode("utf-8"))
	elif hasattr(obj, "__name__") : 
		m.update(obj.__name__.encode("utf-8"))
	if hasattr(obj, "__module__") and obj.__module__: 
		m.update(obj.__module__.encode("utf-8"))
		m.update(sys.modules[obj.__module__].__file__.encode("utf-8"))

## Table of hash functions for special types.
hashfuncs = {
	LazyObject: updatehash_LazyObject,
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
		if obj.__class__.__repr__ is object.__repr__:
			print("WARNING: object of class {} uses common __repr__ method. Сache may not work correctly"
				.format(obj.__class__))
		m.update(repr(obj).encode("utf-8"))

__tree_tab = "    "
def print_tree(obj, t = 0):
	"""Print lazy tree in user friendly format."""	
	if isinstance(obj, LazyObject):
		#print(__tree_tab*t, end=''); print("LazyObject:")
		if (obj.generic): 
			print(__tree_tab*t, end=''); print("generic:\n", end=''); print_tree(obj.generic, t+1)
			if (len(obj.args)): print(__tree_tab*t, end=''); print("args:\n", end=''); print_tree(obj.args, t+1)
			if (len(obj.kwargs)): print(__tree_tab*t, end=''); print("kwargs:\n", end=''); print_tree(obj.kwargs, t+1)
			print(__tree_tab*t, end=''); print("-------")
		else:
			print(__tree_tab*t, end=''); print(obj.__lazyvalue__)
	elif isinstance(obj, list) or isinstance(obj, tuple):
		for o in obj:
			print_tree(o, t)
	else:
		print(__tree_tab*t, end=''); print(obj)

def encache(obj, sts = True):
	obj.__encache__ = sts

def decache(obj, sts = True):
	obj.__decache__ = sts