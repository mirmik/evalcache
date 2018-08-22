#coding: utf-8
##@file evalcache/__init__.py
##Библиотека дискового кэширования ленивых вычислений.
##
## Example:
##
## import evalcache
## evalcache.enable()
##
## class EvalRes:
##		def something_do():
##			...
## 		...
##
## Lazy = evalcache.create_class_wrap("Lazy", wrapclass = EvalRes) 
## Lazy.__wrapmethod__(name = "something_do", rettype = EvalRes, wrapfunc = EvalRes.something_do)
##
## @lazy(Lazy)
## def very_long_evaluation(args ...):
##		...
##		...
##		...
##
## result = very_long_evaluation(args ...).something_do()
##

import hashlib
import os
import pickle
import inspect
import types

## Версия пакета
version = "0.1.2" 

## Имя директории кэша
cache_directory = ".evalcache"

## Статус активации
cache_enabled = False

## Имена файлов в директории кэша
files  = None 

def enable():
	"""Активировать дисковый кэш .evalcache"""
	global cache_enabled
	if cache_enabled == False:
		global files 
		if not os.path.exists(cache_directory):
			os.mkdir(cache_directory)
			files  = set()
			return

		lst = os.listdir(cache_directory)
		files  = set(lst)
		cache_enabled = True
	
def hashlist(x):
	"""Хэшфункция list-like объектов"""
	m = hashlib.sha1()
	for a in x: 
		m.update(gethash(a))
	return m.digest()

## Хэшфункции базовых типов
hashfuncs = { 
	str : 	lambda x: x.encode("utf-8"),
	int : 	lambda x: str(x).encode("utf-8"),
	float : lambda x: str(x).encode("utf-8"),
	tuple : hashlist,
	list: hashlist,
}

def gethash(obj):
	"""Получение хэша объекта или аргумента.

	В зависимости от типа объекта:
	Для ленивых объектов использует заранее расчитанный хэш.
	Для остальных объектов, сначала ищет хэш функцию в таблице hashfunc
	При неудаче пробует сконструировать хеш на основе общих соображений 
	о наследнике объектного типа.  
	"""
	if hasattr(obj, "__lazyhash__"): return obj.__lazyhash__
	elif obj.__class__ in hashfuncs: return hashfuncs[obj.__class__](obj)
	else:
		m = hashlib.sha1()
		m.update(str(obj.__class__).encode("utf-8"))
		m.update(str(repr(obj)).encode("utf-8"))
		return m.digest()

class LazyFunction:
	"""Ленивая обёртка для функций. 

	Представляет собой фабрику для создания ленивых объектов. 
	"""
	def __init__(self, func, rettype):
		"""
		Parametrs:
		----------
		func - оборачиваемая функция или метод.
		rettype - тип генерируемого фабрикой объекта, или функция, определяющая тип
		при вызове, исходя из переданных параметров.
		"""
		self.func = func
		self.rettype = rettype
		if cache_enabled:
			m = hashlib.sha1()
			if hasattr(func, "__qualname__"): m.update(func.__qualname__.encode("utf-8"))
			elif hasattr(func, "__name__") : m.update(func.__name__.encode("utf-8"))
			else: m.update(func.encode("utf-8")) 
			if hasattr(func, "__module__") and func.__module__: m.update(func.__module__.encode("utf-8"))
			self.__lazyhash__ = m.digest()
		
	def __call__(self, *args, **kwargs):
		"""Работа по производству ленивого объекта.

		С точки зрения пользователя, он вызывает функцию или метод, производящую вычисление,
		но на самом деле конструируется ленивый объект, запоминающий переданные аргументы"""
		if (isinstance(self.rettype, types.FunctionType)): self.rettype = self.rettype(*args, **kwargs)
		obj = self.rettype.__construct__(self, *args, **kwargs)
		return obj

	def __get__(self, instance, cls):
		"""Переопределение __get__ позволяет использовать класс для оборачивания методов."""
		if instance is None:
			return self
		else:
			return types.MethodType(self, instance)

def wraped_new(cls, *args, **kwargs):
	"""Функция-обертка конструктора объекта"""
	obj = cls.__wraped_class__.__new__(cls.__wraped_class__)
	cls.__wraped_class__.__init__(obj, *args, **kwargs)
	return obj

def do_nothing(*args, **kwargs):
	pass

class LazyObject:
	def __init__(self, func, *args, **kwargs):
		"""Конструктор сохраняет аргументы, с которыми объект вызван и вычисляет его хэш для последующего использования"""
		self.func = func
		self.args = args
		self.kwargs = kwargs
		if cache_enabled:
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
		"""Специальный метод-конструктор, используемый в рамках библиотеки.

		Конструирует объект по обычным правилам. Нужен потому, что конструктор потомка LazyObject может быть переопределен. (см. create_class_wrap)"""
		obj = object.__new__(cls) 
		LazyObject.__init__(obj, funchead, *args, **kwargs)
		return obj

	@classmethod
	def __wrapmethod__(cls, name, rettype, wrapfunc = None):
		"""Создание обёртки над методом ленивого класса."""
		if (wrapfunc == None): wrapfunc = name
		setattr(cls, name, LazyFunction(wrapfunc, rettype))

	@staticmethod
	def __lazyexpand__(arg):
		"""Раскрытие аргумента. 
	
		Если arg - ленивый объект, вернуть его вычисление. Иначе вернуть сам объект."""
		if isinstance(arg, list): return [LazyObject.__lazyexpand__(a) for a in arg] 
		return arg.eval() if isinstance(arg, LazyObject) else arg

	def __lazydo__(self):
		"""Выполнить операцию.
	
		В начале производится восстановление запомненных аргументов. Если аргументы ленивые, запрашивается их вычисление.
		"""
		args = [LazyObject.__lazyexpand__(arg) for arg in self.args]
		kwargs = {k : LazyObject.__lazyexpand__(v) for k, v in self.kwargs.items()}
		if (isinstance(self.func.func, str)):
			func = getattr(args[0], self.func.func)
			return func(*args[1:], **kwargs)
		else: 
			func = self.func.func
			return func(*args, **kwargs)

	def __lazyeval__(self):
		"""Выполнить ленивое вычисление.
	
		Пытается получить результат наиболее экономным способом. Ищет в памяти, затем в дисковом кэше (если он активирован).
		Если нет ни там, ни там, вычисляет результат и сохраняет его в дисковый кэш (если он активирован).
		"""		
		if (self.__lazyvalue__ != None):
			return self.__lazyvalue__

		if cache_enabled and self.__lazyhexhash__ in files :
			fl = open(os.path.join(cache_directory, self.__lazyhexhash__), "rb")
			self.__lazyvalue__ = pickle.load(fl)
			return self.__lazyvalue__

		self.__lazyvalue__ = self.__lazydo__()
		if cache_enabled: 
			fl = open(os.path.join(cache_directory, self.__lazyhexhash__), "wb")
			pickle.dump(self.__lazyvalue__, fl)
		
		return self.__lazyvalue__		

	def do(self): 
		"""Синоним для операции __lazydo__. Если оригинальный объект имеет метод с таким названием, можно его обернуть и работать с __lazydo__."""
		return self.__lazydo__()

	def eval(self): 
		"""Синоним для операции __lazyeval__. Если оригинальный объект имеет метод с таким названием, можно его обернуть и работать с __lazyeval__."""
		return self.__lazyeval__()
	
def create_class_wrap(name, parent = LazyObject, wrapclass = None):
	"""Функция генерирует класс ленивого объекта.

	Parameters: 
	-----------
	parent - установить в качестве предка другой ленивый тип. Используется
	при создании оберток над иерархиями типов.

	wrapclass - Класс, тип которого оборачивает конструируемый тип.
	Не обязателен для определения. При определении данного параметра
	появляется возможность использовать конструктор оборачивоемого класса
	как ленивый метод.
	"""
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
	"""Декоратор, превращающий функцию в ленивую.
	
	Вызов декарированной функции приведет к созданию ленивого указанного объекта.
	
	Parameters:
	----------
	rettype - Тип ленивого указателя. rettype может быть функцией, которая будет
	вызвана для определения типа перед созданием ленивого объекта.
	"""
	return lambda func: LazyFunction(func, rettype)