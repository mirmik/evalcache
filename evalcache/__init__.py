#coding: utf-8
##@file evalcache/__init__.py
##Библиотека дискового кэширования ленивых вычислений.

import hashlib
import types

from evalcache.dirdict import dirdict as DirCache 

## Версия пакета
version = "0.2.0" 
diagnostic_enabled = False

def enable_diagnostic():
	global diagnostic_enabled
	diagnostic_enabled = True

def _index(obj, item):
	return obj[item]

def _updatehash(m, obj):
	"""Получение хэша объекта или аргумента.

	В зависимости от типа объекта:
	Для ленивых объектов использует заранее расчитанный хэш.
	Для остальных объектов, сначала ищет хэш функцию в таблице hashfunc
	При неудаче пробует сконструировать хеш на основе общих соображений 
	о наследнике объектного типа.  
	"""
	if isinstance(obj, types.FunctionType):
		if hasattr(obj, "__qualname__"): 
			m.update(obj.__qualname__.encode("utf-8"))
		elif hasattr(obj, "__name__") : 
			m.update(obj.__name__.encode("utf-8"))
		
		if hasattr(obj, "__module__") and obj.__module__: 
			m.update(obj.__module__.encode("utf-8"))
		return 
	m.update(repr(obj).encode("utf-8"))

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
			if diagnostic_enabled: print('save', self.__lazyhexhash__)
			self.__lazyvalue__ = self.__lazydo__()		
			self.__lazybase__.cache[self.__lazyhexhash__] = self.__lazyvalue__
			return self.__lazyvalue__

	def __getattr__(self, item):
		return LazyResult(self.__lazybase__, getattr, self, item)

	#def __index__(self, item):
	def __getitem__(self, item):
		return LazyResult(self.__lazybase__, lambda x, i: x[i], self, item)

	def __add__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x + y, self, oth)
	def __sub__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x - y, self, oth)
	def __xor__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x ^ y, self, oth)
	def __mul__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x * y, self, oth)
	def __div__(self, oth): return LazyResult(self.__lazybase__, lambda x,y: x / y, self, oth)

	def __repr__(self):
		return self.__lazyhexhash__

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
		m = self.__lazybase__.algo()		

		_updatehash(m, self.generic)
		_updatehash(m, args)
		_updatehash(m, sorted(kwargs.items()))

		self.__lazyhash__ = m.digest()
		self.__lazyhexhash__ = m.hexdigest()
		self.__lazyvalue__ = None

class LazyGeneric(LazyObject):
	def __init__(self, lazifier, func):
		LazyObject.__init__(self, lazifier)
		self.__lazyvalue__ = func
		m = self.__lazybase__.algo()
		_updatehash(m, func)
		self.__lazyhash__ = m.digest()
		self.__lazyhexhash__ = m.hexdigest()
		
def unlazy(lazyobj):
	"""Получить результат вычисления ленивого объекта"""
	return lazyobj.__lazyeval__()