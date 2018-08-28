#coding: utf-8
##@file evalcache/__init__.py
##Библиотека дискового кэширования ленивых вычислений.

import hashlib
import types

from evalcache.dircache import DirCache 

## Версия пакета
version = "0.2.0" 
diagnostic_enabled = False

def enable_diagnostic():
	global diagnostic_enabled
	diagnostic_enabled = True

class Lazy:
	def __init__(self, cache, algo = hashlib.sha256):
		self.cache = cache
		self.algo = algo

	def ctor(self, cls):
		def constructor(*args, **kwargs):
			return cls(*args, **kwargs)
		return self(constructor)

	def __call__(self, func):
		return LazyGeneric(self, func)

class LazyObject:
	def __init__(self, lazy):
		self.__lazybase__ = lazy

	def __call__(self, *args, **kwargs):
		"""Работа по производству ленивого объекта.

		С точки зрения пользователя, он вызывает функцию или метод, производящую вычисление,
		но на самом деле конструируется ленивый объект, запоминающий переданные аргументы"""
		return LazyResult(self.__lazybase__, self, *args, **kwargs)


	@staticmethod
	def __lazyexpand__(arg):
		"""Раскрытие аргумента. 
	
		Если arg - ленивый объект, вернуть его вычисление. Иначе вернуть сам объект."""
		if isinstance(arg, list): return [LazyObject.__lazyexpand__(a) for a in arg] 
		return arg.__lazyeval__() if isinstance(arg, LazyObject) else arg

	def __lazydo__(self):
		"""Выполнить операцию.
	
		В начале производится восстановление запомненных аргументов. Если аргументы ленивые, запрашивается их вычисление.
		"""

		args = [LazyObject.__lazyexpand__(arg) for arg in self.args]
		kwargs = {k : LazyObject.__lazyexpand__(v) for k, v in self.kwargs.items()}

		func = LazyObject.__lazyexpand__(self.generic)
		return func(*args, **kwargs)

	def __lazyeval__(self):
		"""Выполнить ленивое вычисление.
	
		Пытается получить результат наиболее экономным способом. Ищет в памяти, затем в дисковом кэше (если он активирован).
		Если нет ни там, ни там, вычисляет результат и сохраняет его в дисковый кэш (если он активирован).
		"""
		if (self.__lazyvalue__ != None):
			if diagnostic_enabled: print('fget', self.__lazyhexhash__)
			return self.__lazyvalue__

		if self.__lazyhexhash__ in self.__lazybase__.cache:
			if diagnostic_enabled: print('load', self.__lazyhexhash__)
			self.__lazyvalue__ = self.__lazybase__.cache[self.__lazyhexhash__]
			return self.__lazyvalue__
		else:
			self.__lazyvalue__ = self.__lazydo__()		
			if diagnostic_enabled: print('save', self.__lazyhexhash__)
			self.__lazybase__.cache[self.__lazyhexhash__] = self.__lazyvalue__
			return self.__lazyvalue__

	def __getattr__(self, item):
		return LazyResult(self.__lazybase__, getattr, self, item)

	def __getitem__(self, item):
		return LazyResult(self.__lazybase__, lambda x, i: x[i], self, item)

	def __add__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x + y, self, oth)
	def __sub__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x - y, self, oth)
	def __xor__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x ^ y, self, oth)
	def __mul__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x * y, self, oth)
	def __div__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x / y, self, oth)

	def __eq__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x == y, self, oth)
	def __ne__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x != y, self, oth)
	def __lt__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x <  y, self, oth)
	def __le__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x <= y, self, oth)
	def __gt__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x >  y, self, oth)
	def __ge__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x >= y, self, oth)

	def unlazy(self):
		ret = self.__lazyeval__()
		if hasattr(ret, "unlazy"):
			print("warn: Shadow unlazy method.")
		return ret

	def eval(self):
		print("warn: Eval method is deprecated. You should use unlazy.")
		ret = self.__lazyeval__()
		if hasattr(ret, "eval"):
			print("warn: Shadow eval method.")
		return ret


class LazyResult(LazyObject):
	def __init__(self, lazifier, generic, *args, **kwargs):
		"""Конструктор сохраняет аргументы, с которыми объект вызван и вычисляет его хэш для последующего использования"""
		LazyObject.__init__(self, lazifier)	
		self.generic = generic
		self.args = args
		self.kwargs = kwargs
		self.__lazyvalue__ = None
		
		m = self.__lazybase__.algo()		
		_updatehash(m, self.generic)
		if len(args): _updatehash(m, args)
		if len(kwargs): _updatehash(m, kwargs)

		self.__lazyhash__ = m.digest()
		self.__lazyhexhash__ = m.hexdigest()

	def __repr__(self): return "<LazyResult(generic:{}, args:{}, kwargs:{})>".format(self.generic, self.args, self.kwargs)

class LazyGeneric(LazyObject):
	def __init__(self, lazifier, func):
		LazyObject.__init__(self, lazifier)
		self.__lazyvalue__ = func
		
		m = self.__lazybase__.algo()
		_updatehash(m, func)
		
		self.__lazyhash__ = m.digest()
		self.__lazyhexhash__ = m.hexdigest()

	def __get__(self, instance, cls):
		"""With __get__method we can use lazy decorator on classe's methods"""
		if instance is None:
			return self
		else:
			return types.MethodType(self, instance)

	def __repr__(self): return "<LazyGeneric(value:{})>".format(self.__lazyvalue__)
		
def unlazy(lazyobj):
	"""Получить результат вычисления ленивого объекта"""
	return lazyobj.__lazyeval__()

def _updatehash_list(m, obj):
	for e in obj:
		_updatehash(m, e)

def _updatehash_dict(m, obj):
	for k, v in sorted(obj.items()):
		_updatehash(m, k)
		_updatehash(m, v)

def _updatehash_LazyObject(m, obj):
	m.update(obj.__lazyhash__)

def _updatehash_function(m, obj):
	if hasattr(obj, "__qualname__"): 
		m.update(obj.__qualname__.encode("utf-8"))
	elif hasattr(obj, "__name__") : 
		m.update(obj.__name__.encode("utf-8"))
	if hasattr(obj, "__module__") and obj.__module__: 
		m.update(obj.__module__.encode("utf-8"))


hashfuncs = {
	LazyGeneric: _updatehash_LazyObject,
	LazyResult: _updatehash_LazyObject,
	tuple: _updatehash_list,
	list: _updatehash_list,
	dict: _updatehash_dict,
	types.FunctionType: _updatehash_function,
}

def _updatehash(m, obj):
	"""Получение хэша объекта или аргумента.

	В зависимости от типа объекта:
	Для ленивых объектов использует заранее расчитанный хэш.
	Для остальных объектов, сначала ищет хэш функцию в таблице hashfunc
	При неудаче пробует сконструировать хеш на основе общих соображений 
	"""
	if obj.__class__ in hashfuncs:
		hashfuncs[obj.__class__](m, obj)
	else:
		if obj.__class__.__repr__ == object.__repr__:
			print("warn: object of class {} have not __repr__ method".format(obj.__class__))
		m.update(repr(obj).encode("utf-8"))

__tree_tab = "    "
def print_tree(obj, t = 0):
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