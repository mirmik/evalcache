#coding: utf-8
##@file evalcache/__init__.py


import hashlib
import os
import pickle
import inspect
import types

version = "0.1.1"

cache_directory = ".evalcache" 
cache_enabled = False

files = None

def hashlist(x):
	m = hashlib.sha1()
	for a in x: 
		m.update(gethash(a))
	return m.digest()
	

hashfuncs = { 
	str : 	lambda x: x.encode("utf-8"),
	int : 	lambda x: str(x).encode("utf-8"),
	float : lambda x: str(x).encode("utf-8"),
	tuple : hashlist,
	list: hashlist,
}

enabled = False

def enable():
	global enabled
	if enabled == False:
		global files
		global cache_enabled
		cache_enabled = True
		if not os.path.exists(cache_directory):
			os.system("mkdir {}".format(cache_directory))
			files = set()
			return

		lst = os.listdir(cache_directory)
		files = set(lst)
	enabled = True

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
		m = hashlib.sha1()
		if hasattr(func, "__qualname__"): m.update(func.__qualname__.encode("utf-8"))
		elif hasattr(func, "__name__") : m.update(func.__name__.encode("utf-8"))
		else: m.update(func.encode("utf-8")) 
		if hasattr(func, "__module__") and func.__module__: m.update(func.__module__.encode("utf-8"))
		self.__lazyhash__ = m.digest()
		
	def __call__(self, *args, **kwargs):
		"""Работа по производству ленивого объекта."""
		if (isinstance(self.rettype, types.FunctionType)): self.rettype = self.rettype(*args, **kwargs)
		obj = self.rettype.__construct__(self, *args, **kwargs)
		return obj

	def __get__(self, instance, cls):
		"""Ленивая функция поддерживает синтаксис вызова метода"""
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
		if isinstance(arg, list): return [LazyObject.__lazyexpand__(a) for a in arg] 
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
			#print("load", self.__lazyhexhash__)
			fl = open(os.path.join(cache_directory, self.__lazyhexhash__), "rb")
			self.__lazyvalue__ = pickle.load(fl)
			return self.__lazyvalue__

		self.__lazyvalue__ = self.__lazydo__()
		if cache_enabled: 
			#print("save", self.__lazyhexhash__)
			fl = open(os.path.join(cache_directory, self.__lazyhexhash__), "wb")
			pickle.dump(self.__lazyvalue__, fl)
		return self.__lazyvalue__		

	def do(self): return self.__lazydo__()
	
	def eval(self): return self.__lazyeval__()

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
	rettype - Тип ленивого указателя. rettype может быть callable, который будет
	вызван для определения типа объекта перед созданием ленивого объекта.
	"""
	return lambda func: LazyFunction(func, rettype)