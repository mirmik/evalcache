# coding: utf-8

from __future__ import print_function

import sys
import types
import hashlib
import binascii
import operator
import inspect
import math
import time


class Lazy:
	"""Decorator for endpoint objects lazifying.

	Arguments:
	----------
	cache -- dict-like object, which stores and loads evaluation's results (f.e. DirCache or dict)
	algo -- hashing algorithm for keys making. (hashlib-like)
	encache -- default state of enabling cache storing
	decache -- default state of enabling cache loading
	diag -- diagnostic output
	onplace -- возвращать результат вычисления вместо ленивого объекта. 
	onuse -- раскрывать ленивый объект при попытки его использования. 
	"""

	def __init__(
			self, cache, algo=hashlib.sha256, 
			encache=True, decache=True,
			onplace=False, onuse=False, fastdo=False,
			diag=False, print_invokes=False, print_values=False, 
			function_dump=True,
			updatehash_profiling=False):
		self.cache = cache
		self.algo = algo
		self.encache = encache
		self.decache = decache
		self.diag = diag
		self.onplace = onplace
		self.onuse = onuse
		self.fastdo = fastdo
		self.print_invokes = print_invokes
		self.print_values = print_values
		self.function_dump = function_dump
		self.updatehash_profiling = updatehash_profiling

	def __call__(self, wrapped_object, hint=None):
		"""Construct lazy wrap for target object."""
		return LazyObject(self, value=wrapped_object, onplace=False, onuse=False, hint=hint)

class LazyHash(Lazy):
	"""Этот декоратор не использует кэш. Создаёт ленивые объекты, вычисляемые один раз."""

	def __init__(self, **kwargs):
		Lazy.__init__(self, cache=None, fastdo=True, **kwargs)

class Memoize(Lazy):
	"""Memoize - это вариант декоратора, проводящего более традиционную ленификацию. 
	
	Для кэширования файлов используется словарь в оперативной памяти. Созданные объекты
	раскрываются или в момент создания или в момент использования.
	"""

	def __init__(self, onplace=False, **kwargs):
		Lazy.__init__(self, cache={}, onplace=onplace, onuse=True, **kwargs)

class MetaLazyObject(type):
	"""LazyObject has metaclass for creation control. It uses for onplace expand option supporting"""

	def __call__(cls, lazifier, *args, onplace = None, **kwargs):
		obj = cls.__new__(cls)
		cls.__init__(obj, lazifier, *args, **kwargs)
		
		if onplace is None:
			onplace = lazifier.onplace

		if onplace is True:
			return unlazy(obj)
		else:
			return obj

class LazyObject(object, metaclass = MetaLazyObject):
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

	def __init__(
				self, lazifier, generic=None, args=(), kwargs={}, 
				encache=None, decache=None, onuse=None, value=None, hint=None):
		self.__lazybase__ = lazifier
		self.__encache__ = encache if encache is not None else self.__lazybase__.encache
		self.__decache__ = decache if decache is not None else self.__lazybase__.decache
		self.__unlazyonuse__ = onuse if onuse is not None else self.__lazybase__.onuse
		self.__lazyhint__ = hint
		self.__lazyheap__ = value is not None

		self.generic = generic
		self.args = args
		self.kwargs = kwargs
		self.__lazyvalue__ = value

		m = lazifier.algo()
		if generic is not None:
			updatehash(m, generic, lazifier)
		if len(args):
			updatehash(m, args, lazifier)
		if len(kwargs):
			updatehash(m, kwargs, lazifier)
		if value is not None:
			updatehash(m, value, lazifier)
		if hint is not None:
			updatehash(m, hint, lazifier)

		self.__lazyhash__ = m.digest()
		self.__lazyhexhash__ = m.hexdigest()

		if self.__lazyvalue__ is None and self.__lazybase__.fastdo:
			self.__lazyvalue__ = lazydo(self)
			self.__lazyheap__ = True

	def __lazyinvoke__(self, generic, args = [], kwargs = {}, encache=None, decache=None):
		"""Логика порождающего вызова.

		Если установлена опция onuse, происходит мгновенное раскрытие.
		В независимости от необходимости мгновенного раскрытия создаётся ленивый
		объект, чтобы задействовать логику кэша."""

		if self.__lazybase__.print_invokes:
			print("__lazyinvoke__", generic, args, kwargs)

		lazyobj = LazyObject(self.__lazybase__, generic, args, kwargs, encache, decache)		
		return lazyobj.unlazy() if self.__unlazyonuse__ else lazyobj

	#Callable
	def __call__(self, *args, **kwargs): 
		return self.__lazyinvoke__(self, args, kwargs)
	
	#Attribute control
	def __getattr__(self, item): 
		return self.__lazyinvoke__( 
									getattr, (self, item), 
									encache = False, decache = False)
	
	#Arithmetic operators:
	def __add__(self, oth):         return self.__lazyinvoke__(operator.__add__, (self, oth))
	def __sub__(self, oth):         return self.__lazyinvoke__(operator.__sub__,      (self, oth))
	def __mul__(self, oth):         return self.__lazyinvoke__(operator.__mul__,      (self, oth))
	def __floordiv__(self, oth):    return self.__lazyinvoke__(operator.__floordiv__, (self, oth))
	def __div__(self, oth):         return self.__lazyinvoke__(operator.__div__,      (self, oth))
	def __truediv__(self, oth):     return self.__lazyinvoke__(operator.__truediv__,  (self, oth))
	def __mod__(self, oth):         return self.__lazyinvoke__(operator.__mod__,      (self, oth))
	def __divmod__(self, oth):      return self.__lazyinvoke__(divmod,                (self, oth))
	def __pow__(self, oth):         return self.__lazyinvoke__(operator.__pow__,      (self, oth))
	def __lshift__(self, oth):      return self.__lazyinvoke__(operator.__lshift__,   (self, oth))
	def __rshift__(self, oth):      return self.__lazyinvoke__(operator.__rshift__,   (self, oth))
	def __and__(self, oth):         return self.__lazyinvoke__(operator.__and__,      (self, oth))
	def __or__(self, oth):          return self.__lazyinvoke__(operator.__or__,       (self, oth))
	def __xor__(self, oth):         return self.__lazyinvoke__(operator.__xor__,      (self, oth))

	#Reverse arithmetic operators:
	def __radd__(self, oth):        return self.__lazyinvoke__(operator.__add__,      (oth, self))
	def __rsub__(self, oth):        return self.__lazyinvoke__(operator.__sub__,      (oth, self))
	def __rmul__(self, oth):        return self.__lazyinvoke__(operator.__mul__,      (oth, self))
	def __rfloordiv__(self, oth):   return self.__lazyinvoke__(operator.__floordiv__, (oth, self))
	def __rdiv__(self, oth):        return self.__lazyinvoke__(operator.__div__,      (oth, self))
	def __rtruediv__(self, oth):    return self.__lazyinvoke__(operator.__truediv__,  (oth, self))
	def __rmod__(self, oth):        return self.__lazyinvoke__(operator.__mod__,      (oth, self))
	def __rdivmod__(self, oth):     return self.__lazyinvoke__(divmod,                (oth, self))
	def __rpow__(self, oth):        return self.__lazyinvoke__(operator.__pow__,      (oth, self))
	def __rlshift__(self, oth):     return self.__lazyinvoke__(operator.__lshift__,   (oth, self))
	def __rrshift__(self, oth):     return self.__lazyinvoke__(operator.__rshift__,   (oth, self))
	def __rand__(self, oth):        return self.__lazyinvoke__(operator.__and__,      (oth, self))
	def __ror__(self, oth):         return self.__lazyinvoke__(operator.__or__,       (oth, self))
	def __rxor__(self, oth):        return self.__lazyinvoke__(operator.__xor__,      (oth, self))

	#Compare operators:
	#Is not supported as lazy operations
	def __eq__(self, oth):
		if self.__unlazyonuse__:
			return self.__lazyinvoke__(operator.__eq__, (self,oth))
		return self.__lazyhash__ == oth.__lazyhash__ 
	
	def __ne__(self, oth):
		if self.__unlazyonuse__:
			return self.__lazyinvoke__(operator.__ne__, (self,oth))
		return self.__lazyhash__ != oth.__lazyhash__ 
	#def __eq__(self, oth): 
	#def __ne__(self, oth): 
	#def __lt__(self, oth):
	#def __le__(self, oth): 
	#def __gt__(self, oth):
	#def __ge__(self, oth): 

	#Unary operators:
	def __pos__(self):      return self.__lazyinvoke__(operator.__pos__,      (self,))
	def __neg__(self):      return self.__lazyinvoke__(operator.__neg__,      (self,))
	def __abs__(self):      return self.__lazyinvoke__(operator.__abs__,      (self,))
	def __invert__(self):   return self.__lazyinvoke__(operator.__invert__,   (self,))
	def __round__(self, n): return self.__lazyinvoke__(operator.__round__,    (self, n))
	def __floor__(self):    return self.__lazyinvoke__(math.floor,    (self,))
	def __ceil__(self):     return self.__lazyinvoke__(math.ceil,     (self,))
	def __trunc__(self):    return self.__lazyinvoke__(math.trunc,    (self,))

	#Augmented assignment
	#This methods group are not supported

	#Container methods:
	#def __len__(self): print("LEN"); exit(0); return LazyObject(self.__lazybase__, lambda x: len(x), (self))
	def __getitem__(self, item): 
		return self.__lazyinvoke__(
									operator.__getitem__, (self, item), 
									encache = False, decache = False)
	#def __setitem__(self, key, value) --- Not supported
	#def __delitem__(self, key)--- Not supported
	#def __iter__(self): return LazyObject(self.__lazybase__, lambda x: iter(x), (self))
	def __reversed__(self): return self.__lazyinvoke__(reversed, (self,))
	#def __contains__(self, item): return LazyObject(self.__lazybase__, lambda x, i: contains(x, i), (self, item))
	#def __missing__(self, key): --- ???
	
	#Type conversion:
	#TODO: need undestand, what it should...
	#def __nonzero__(self): return bool(unlazy(self))
	#def __bool__(self): return bool(unlazy(self))
	#def __int__(self): return int(unlazy(self))
	#def __long__(self): return long(unlazy(self))
	#def __float__(self): return float(unlazy(self))
	#def __complex__(self): return complex(unlazy(self))
	#def __oct__(self): return oct(unlazy(self))
	#def __hex__(self): return hex(unlazy(self))
	#def __index__(self): return LazyObject(self.__lazybase__, lambda x: int(x), (self)) ???
	#def __trunc__(self): return LazyObject(self.__lazybase__, lambda x: math.trunc(x), (self))
	def __coerce__(self, oth): return None

	#Type presentation
	def __hash__(self): return int(binascii.hexlify(self.__lazyhash__), 16)
	
	def __str__(self): 
		if self.__unlazyonuse__:
			return self.__lazyinvoke__(str, (self,))
		else:
			return repr(self)
	#def __repr__(self): repr(unlazy(self)) # Standart repr for best debugging

	#Descriptor:
	#def __set__ --- Not supported
	def __get__(self, instance, cls):
		"""With __get__ method we can use lazy decorator on class's methods"""
		if (instance is not None) and isinstance(self.__lazyvalue__, types.FunctionType):
			return types.MethodType(self, instance)
		else:
			return self

	def __delete__(self): pass

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
	# If local context was setted we can return object imediatly
	if obj.__lazyheap__:
		# Load from local context ...
		if obj.generic is None:
			# for endpoint object.
			msg = 'endp'
		else:
			# for early executed object.
			msg = 'fget'

	# Now searhes object in cache, if not prevented.
	elif obj.__decache__ and obj.__lazyhexhash__ in obj.__lazybase__.cache:
		# Load from cache.
		msg = 'load'
		obj.__lazyvalue__ = obj.__lazybase__.cache[obj.__lazyhexhash__]
		obj.__lazyheap__ = True

	# Object wasn't stored early. Evaluate it. Store it if not prevented.
	else:
		# Execute ...
		obj.__lazyvalue__ = lazydo(obj)
		obj.__lazyheap__ = True
		if obj.__encache__:
			# with storing.
			msg = 'save'
			obj.__lazybase__.cache[obj.__lazyhexhash__] = obj.__lazyvalue__
		else:
			# without storing.
			msg = 'eval'
	
	if obj.__lazybase__.diag:
		if obj.__lazybase__.print_values:
			print(msg, obj.__lazyhexhash__, obj.__lazyvalue__)
		else:
			print(msg, obj.__lazyhexhash__)
	
	while isinstance(obj.__lazyvalue__, LazyObject):
		obj.__lazyvalue__ = expand(obj.__lazyvalue__)

	# And, anyway, here our object in obj.__lazyvalue__
	return obj.__lazyvalue__


def expand(arg):
	"""Apply unlazy operation for argument or for all argument's items if need.
	LazyObject as dictionary key can be used.

	TODO: Need construct expand functions table for compat with user's collections.
	"""
	if isinstance(arg, list) or isinstance(arg, tuple):
		return [expand(a) for a in arg]
	elif isinstance(arg, dict):
		return {expand(k): expand(v) for k, v in arg.items()}
	else:
		return unlazy(arg) if isinstance(arg, LazyObject) else arg


def updatehash_list(m, obj, base):
	for e in obj:
		updatehash(m, e, base)


def updatehash_dict(m, obj, base):
	for k, v in sorted(obj.items()):
		updatehash(m, k, base)
		updatehash(m, v, base)


def updatehash_str(m, obj, base):
	m.update(obj.encode("utf-8"))


def updatehash_LazyObject(m, obj, base):
	m.update(obj.__lazyhash__)


def updatehash_function(m, obj, base):
	if hasattr(obj, "__qualname__"):
		#if obj.__qualname__ == "<lambda>":
		#	print("WARNING: evalcache cann't work with global lambdas correctly without hints")
		updatehash_str(m, obj.__qualname__, base)
	elif hasattr(obj, "__name__"):
		updatehash_str(m, obj.__name__, base)

	if base.function_dump:
		updatehash_str(m, inspect.getsource(obj), base)

	if hasattr(obj, "__module__") and obj.__module__:
		updatehash_str(m, obj.__module__, base)
		updatehash_str(m, sys.modules[obj.__module__].__file__, base)


# Table of hash functions for special types.
hashfuncs = {
	LazyObject: updatehash_LazyObject,
	str: updatehash_str,
	tuple: updatehash_list,
	list: updatehash_list,
	dict: updatehash_dict,
	types.FunctionType: updatehash_function,
}


def updatehash(m, obj, base):
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
	if base.updatehash_profiling:
		start = time.time()

	if obj.__class__ in hashfuncs:
		hashfuncs[obj.__class__](m, obj, base)
	else:
		if obj.__class__.__repr__ is object.__repr__:
			print("WARNING: object of class {} uses common __repr__ method. Сache may not work correctly"
				  .format(obj.__class__))
		updatehash_str(m, repr(obj), base)

	if base.updatehash_profiling:
		end = time.time()
		print("updatehash elapse for {}: {}".format(repr(obj), end - start))


__tree_tab = "    "


def print_tree(obj, t=0):
	"""Print lazy tree in user friendly format."""
	if isinstance(obj, LazyObject):
		#print(__tree_tab*t, end=''); print("LazyObject:")
		if (obj.generic):
			print(__tree_tab*t, end='')
			print("generic:\n", end='')
			print_tree(obj.generic, t+1)
			if (len(obj.args)):
				print(__tree_tab*t, end='')
				print("args:\n", end='')
				print_tree(obj.args, t+1)
			if (len(obj.kwargs)):
				print(__tree_tab*t, end='')
				print("kwargs:\n", end='')
				print_tree(obj.kwargs, t+1)
			print(__tree_tab*t, end='')
			print("-------")
		else:
			print(__tree_tab*t, end='')
			print(obj.__lazyvalue__)
	elif isinstance(obj, list) or isinstance(obj, tuple):
		for o in obj:
			print_tree(o, t)
	else:
		print(__tree_tab*t, end='')
		print(obj)


def encache(obj, sts=True):
	obj.__encache__ = sts


def decache(obj, sts=True):
	obj.__decache__ = sts
