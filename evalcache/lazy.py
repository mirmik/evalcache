# coding: utf-8

from __future__ import print_function

import sys
import types
import hashlib
import binascii
import operator
import inspect
import functools
import math
import time

import evalcache.dircache_v2


class Lazy:
    """Decorator for endpoint objects lazifying.

	Arguments:
	----------
	cache -- dict-like object, which stores and loads evaluation's results (f.e. DirCache or dict)
	algo -- hashing algorithm for keys making. (hashlib-like)
	encache -- default state of enabling cache storing
	decache -- default state of enabling cache loading
	onplace -- возвращать результат вычисления вместо ленивого объекта
	onuse -- раскрывать ленивый объект при попытки его использования
	fastdo -- вычислять объект при создании ленивого объекта
	diag -- cache diagnostic output
	diag_values -- add values print to cache diagnostic
	print_invokes -- LazyObject invokes diagnostic output
	function_dump -- use code dump for function hashing
	updatehash_profiling -- updatehash diagnostic output
	"""

    def __init__(
        self,
        cache,
        algo=hashlib.sha256,
        encache=True,
        decache=True,
        onplace=False,
        onuse=False,
        fastdo=False,
        diag=False,
        diag_values=False,
        print_invokes=False,
        function_dump=True,
        function_file=False,
        updatehash_profiling=False,
        onstr=False,
        onrepr=False,
        onbool=True,
    ):
        self.cache = cache
        self.algo = algo
        self.encache = encache
        self.decache = decache
        self.diag = diag
        self.onplace = onplace
        self.onuse = onuse
        self.onstr = onstr
        self.onrepr = onrepr
        self.onbool = onbool
        self.fastdo = fastdo
        self.print_invokes = print_invokes
        self.diag_values = diag_values
        self.function_dump = function_dump
        self.function_file = function_file
        self.updatehash_profiling = updatehash_profiling
        self.objects = {}

        if cache is None:
            if encache is not False:
                print("WARNING: Cache is None, but encache option setted")
            if decache is not False:
                print("WARNING: Cache is None, but decache option setted")
        elif isinstance(cache, str):
            self.cache = evalcache.dircache_v2.DirCache_v2(cache)

        if diag_values and not diag:
            print("WARNING: diag_values is True, but diag is False")

    def register(self, obj):
        self.objects[obj.__lazyhexhash__] = obj

    def cache_startswith(self, hash):
        lst = [k for k in self.cache.keys()]
        ret = []
        for l in lst:
            if l.startswith(hash):
                ret.append(l)
        return ret

    def objects_startswith(self, hash):
        lst = [k for k in self.objects.keys()]
        ret = []
        for l in lst:
            if l.startswith(hash):
                ret.append(self.objects[l])
        return ret

    def __getitem__(self, hash):
        ret = self.objects_startswith(hash)
        if len(ret) == 1:
            return ret[0]
        else:
            print(
                "WARNING: objects_startswith return is array with len {}".format(
                    len(ret)
                )
            )
            return None

    def lazyfile(self, path="path"):
        return self.file_creator(path)

    def file_creator(self, pathfield="path", hint=None):
        """Параметр указывает, в каком поле передаётся путь к создаваемому файлу"""
        from evalcache.lazyfile import LazyFileMaker

        return lambda func: LazyFileMaker(self, func, pathfield, hint)

    def __call__(self, wrapped_object, hint=None):
        """Construct lazy wrap for target object."""
        return LazyObject(
            self, value=wrapped_object, onplace=False, onuse=False, hint=hint
        )

    def lazy(self, hint=None, cls=None):
        if cls is None:
            cls = LazyObject
        return lambda wraped: cls(
            self, value=wraped, onplace=False, onuse=False, hint=hint
        )


class LazyHash(Lazy):
    """Этот декоратор не использует кэш. Создаёт ленивые объекты, вычисляемые один раз."""

    def __init__(self, fastdo=True, **kwargs):
        Lazy.__init__(
            self, cache=None, encache=False, decache=False, fastdo=fastdo, **kwargs
        )


class Memoize(Lazy):
    """Memoize - это вариант декоратора, проводящего более традиционную ленификацию. 
	
	Для кэширования файлов используется словарь в оперативной памяти. Созданные объекты
	раскрываются или в момент создания или в момент использования.
	"""

    def __init__(self, onplace=False, **kwargs):
        Lazy.__init__(self, cache={}, onplace=onplace, onuse=True, **kwargs)


class MetaLazyObject(type):
    """LazyObject has metaclass for creation control. It uses for onplace expand option supporting"""

    def __call__(cls, lazifier, *args, onplace=None, **kwargs):
        obj = cls.__new__(cls)
        cls.__init__(obj, lazifier, *args, **kwargs)

        if onplace is None:
            onplace = lazifier.onplace

        if onplace is True:
            return unlazy(obj)
        else:
            return obj


class LazyObject(object, metaclass=MetaLazyObject):
    """Lazytree element's interface.

	A lazy object provides a rather abstract interface. We can use attribute getting or operators to
	generate another lazy objects.

	The technical problem is that a lazy wrapper does not know the type of wraped object before unlazing.
	Therefore, we assume that any action on a lazy object is a priori true. If the object does not support 
	the manipulation performed on it, we will know about it at the execution stage.

	Details
	-------
	MetaLazyObject used as metaclass for support onplace expand logic.

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
        self,
        lazifier,
        generic=None,
        args=(),
        kwargs={},
        encache=None,
        decache=None,
        onuse=None,
        value=None,
        hint=None,
    ):
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
            updatehash(m, generic, self)
        if len(args):
            updatehash(m, args, self)
        if len(kwargs):
            updatehash(m, kwargs, self)
        if value is not None:
            updatehash(m, value, self)
        if hint is not None:
            updatehash(m, hint, self)

        self.__lazyhash__ = m.digest()
        self.__lazyhexhash__ = m.hexdigest()

        self.__lazybase__.register(self)

        if self.__lazybase__.fastdo and self.__lazyvalue__ is None:
            unlazy(self)

    # Callable
    def __call__(self, *args, **kwargs):
        return lazyinvoke(self, self, args, kwargs)

    # Attribute control
    def __getattr__(self, item):
        return lazyinvoke(
            self,
            lazy_getattr,
            (self, item, NoExpand(self)),
            encache=False,
            decache=False,
        )
        # return lazyinvoke(self, lazy_getattr, (self, item, NoExpand(self)), encache = False, decache = False)

    # Arithmetic operators:
    def __add__(self, oth):
        return lazyinvoke(self, operator.__add__, (self, oth))

    def __sub__(self, oth):
        return lazyinvoke(self, operator.__sub__, (self, oth))

    def __mul__(self, oth):
        return lazyinvoke(self, operator.__mul__, (self, oth))

    def __floordiv__(self, oth):
        return lazyinvoke(self, operator.__floordiv__, (self, oth))

    def __div__(self, oth):
        return lazyinvoke(self, operator.__div__, (self, oth))

    def __truediv__(self, oth):
        return lazyinvoke(self, operator.__truediv__, (self, oth))

    def __mod__(self, oth):
        return lazyinvoke(self, operator.__mod__, (self, oth))

    def __divmod__(self, oth):
        return lazyinvoke(self, divmod, (self, oth))

    def __pow__(self, oth):
        return lazyinvoke(self, operator.__pow__, (self, oth))

    def __lshift__(self, oth):
        return lazyinvoke(self, operator.__lshift__, (self, oth))

    def __rshift__(self, oth):
        return lazyinvoke(self, operator.__rshift__, (self, oth))

    def __and__(self, oth):
        return lazyinvoke(self, operator.__and__, (self, oth))

    def __or__(self, oth):
        return lazyinvoke(self, operator.__or__, (self, oth))

    def __xor__(self, oth):
        return lazyinvoke(self, operator.__xor__, (self, oth))

    # Reverse arithmetic operators:
    def __radd__(self, oth):
        return lazyinvoke(self, operator.__add__, (oth, self))

    def __rsub__(self, oth):
        return lazyinvoke(self, operator.__sub__, (oth, self))

    def __rmul__(self, oth):
        return lazyinvoke(self, operator.__mul__, (oth, self))

    def __rfloordiv__(self, oth):
        return lazyinvoke(self, operator.__floordiv__, (oth, self))

    def __rdiv__(self, oth):
        return lazyinvoke(self, operator.__div__, (oth, self))

    def __rtruediv__(self, oth):
        return lazyinvoke(self, operator.__truediv__, (oth, self))

    def __rmod__(self, oth):
        return lazyinvoke(self, operator.__mod__, (oth, self))

    def __rdivmod__(self, oth):
        return lazyinvoke(self, divmod, (oth, self))

    def __rpow__(self, oth):
        return lazyinvoke(self, operator.__pow__, (oth, self))

    def __rlshift__(self, oth):
        return lazyinvoke(self, operator.__lshift__, (oth, self))

    def __rrshift__(self, oth):
        return lazyinvoke(self, operator.__rshift__, (oth, self))

    def __rand__(self, oth):
        return lazyinvoke(self, operator.__and__, (oth, self))

    def __ror__(self, oth):
        return lazyinvoke(self, operator.__or__, (oth, self))

    def __rxor__(self, oth):
        return lazyinvoke(self, operator.__xor__, (oth, self))

    # Compare operators:
    # Is not supported as lazy operations
    def __eq__(self, oth):
        # if self.__unlazyonuse__:
        return lazyinvoke(self, operator.__eq__, (self, oth))
        # return self.__lazyhash__ == oth.__lazyhash__

    def __ne__(self, oth):
        # if self.__unlazyonuse__:
        return lazyinvoke(self, operator.__ne__, (self, oth))
        # return self.__lazyhash__ != oth.__lazyhash__

    def __lt__(self, oth):
        return lazyinvoke(self, operator.__lt__, (self, oth))

    def __le__(self, oth):
        return lazyinvoke(self, operator.__le__, (self, oth))

    def __gt__(self, oth):
        return lazyinvoke(self, operator.__gt__, (self, oth))

    def __ge__(self, oth):
        return lazyinvoke(self, operator.__ge__, (self, oth))

    # Unary operators:
    def __pos__(self):
        return lazyinvoke(self, operator.__pos__, (self,))

    def __neg__(self):
        return lazyinvoke(self, operator.__neg__, (self,))

    def __abs__(self):
        return lazyinvoke(self, operator.__abs__, (self,))

    def __invert__(self):
        return lazyinvoke(self, operator.__invert__, (self,))

    def __round__(self, n):
        return lazyinvoke(self, operator.__round__, (self, n))

    def __floor__(self):
        return lazyinvoke(self, math.floor, (self,))

    def __ceil__(self):
        return lazyinvoke(self, math.ceil, (self,))

    def __trunc__(self):
        return lazyinvoke(self, math.trunc, (self,))

    # Augmented assignment
    # This methods group are not supported

    # Container methods:
    def __len__(self):
        return unlazy(lazyinvoke(self, len, (self,)))

    def __getitem__(self, item):
        return lazyinvoke(
            self, operator.__getitem__, (self, item), encache=False, decache=False
        )

    # def __setitem__(self, key, value) --- Not supported
    # def __delitem__(self, key)--- Not supported
    def __iter__(self):
        return iter([self[i] for i in range(0, len(self))])

    def __reversed__(self):
        return lazyinvoke(self, reversed, (self,))

    # def __contains__(self, item): return LazyObject(self.__lazybase__, lambda x, i: contains(x, i), (self, item))
    # def __missing__(self, key): --- ???

    # Type conversion:
    # TODO: need undestand, what it should...
    # def __nonzero__(self): return bool(unlazy(self))
    # def __int__(self): return int(unlazy(self))
    # def __long__(self): return long(unlazy(self))
    # def __float__(self): return float(unlazy(self))
    # def __complex__(self): return complex(unlazy(self))
    # def __oct__(self): return oct(unlazy(self))
    # def __hex__(self): return hex(unlazy(self))
    # def __index__(self): return LazyObject(self.__lazybase__, lambda x: int(x), (self)) ???
    # def __trunc__(self): return LazyObject(self.__lazybase__, lambda x: math.trunc(x), (self))
    def __bool__(self):
        if self.__lazybase__.onbool:
            return bool(unlazy(self))
        else:
            return True

    def __coerce__(self, oth):
        return None

    # Type presentation
    def __hash__(self):
        return int(binascii.hexlify(self.__lazyhash__), 16)

    def __str__(self):
        if self.__unlazyonuse__ or self.__lazybase__.onstr:
            return str(unlazy(self))
        else:
            return object.__repr__(self)

    def __repr__(self):
        if self.__lazybase__.onrepr:
            return repr(unlazy(self))
        else:
            return object.__repr__(self)

    # Descriptor:
    # def __set__ --- Not supported
    def __get__(self, instance, cls):
        """With __get__ method we can use lazy decorator on class's methods"""
        if (instance is not None) and isinstance(
            self.__lazyvalue__, types.FunctionType
        ):
            return functools.partial(self, instance)
        else:
            return self

    def __delete__(self):
        pass

    def unlazy(self, debug=False):
        """Get a result of evaluation.

		See .unlazy function for details.

		Disclamer:
		Technically, the evaluated object can define an "unlazy" method.
		If so, we'll hide such the method. However since using the unlazy 
		function is more convenient as the method, so this option was excluded."""
        ret = unlazy(self, debug)
        if hasattr(ret, "unlazy"):
            print("WARNING: Shadow unlazy method.")
        return ret

    def lazyinvoke(self, *args, **kwargs):
        return lazyinvoke(self, *args, **kwargs)


class NoExpand:
    def __init__(self, lazyobj):
        self.obj = lazyobj

    def __repr__(self):
        return repr(self.obj)


def lazyinvoke(
    obj, generic, args=[], kwargs={}, encache=None, decache=None, cls=LazyObject
):
    """Логика порождающего вызова.

	Если установлена опция onuse, происходит мгновенное раскрытие.
	В независимости от необходимости мгновенного раскрытия создаётся ленивый
	объект, чтобы задействовать логику кэша."""

    if obj.__lazybase__.print_invokes:
        print("__lazyinvoke__", generic, args, kwargs)

    lazyobj = cls(obj.__lazybase__, generic, args, kwargs, encache, decache)
    return lazyobj.unlazy() if obj.__unlazyonuse__ else lazyobj


def lazydo(obj, debug=False):
    """Perform evaluation.

	We need expand all arguments and callable for support lazy trees.
	Such we should expand result becourse it can be LazyObject (f.e. lazy functions in lazy functions)
	"""
    if debug:
        print("__lazydo__")
        print("\tobj.generic:", obj.generic)
        print("\tobj.args:", obj.args)
        print("\tobj.kwargs:", obj.kwargs)

    func = expand(obj.generic)
    if debug:
        print("\texpand generic:", func)
    args = expand(obj.args)
    if debug:
        print("\texpand args:", args)
    kwargs = expand(obj.kwargs)
    if debug:
        print("\texpand kwargs:", kwargs)

    # if isinstance(func, lazyoperator):
    # 	if debug: print("\tinstance is lazyoperator branch")
    # 	mnem = func.mnem
    # 	opattr = getattr(args[0], mnem)
    # 	if isinstance(opattr, LazyObject):
    # 		return opattr(*obj.args, **obj.kwargs).unlazy(debug)
    # 	else:
    # 		func = func.op

    result = expand(func(*args, **kwargs))
    if debug:
        print("\texpand result:", result)
    return result


def unlazy(obj, debug=False):
    """Get a result of evaluation.

	This function searches for the result in local memory, and after that in cache.
	If object wasn't stored early, it performs evaluation and stores a result in cache and local memory.
	If object has disabled __encache__ storing prevented.
	If object has disabled __decache__ loading prevented.
	"""
    # If local context was setted we can return object imediatly
    if debug:
        print("unlazy")
        print("decache:", obj.__decache__)
        print("encache:", obj.__encache__)

    if obj.__lazyheap__:
        # Load from local context ...
        if obj.generic is None:
            # for endpoint object.
            msg = "endp"
        else:
            # for early executed object.
            msg = "fget"

    # Now searhes object in cache, if not prevented.
    elif obj.__decache__ and obj.__lazyhexhash__ in obj.__lazybase__.cache:
        # Load from cache.
        msg = "load"
        try:
            setvalue(obj, obj.__lazybase__.cache[obj.__lazyhexhash__])
        except:
            print(
                "Warning: Incostistent pickling. Remove it from cache and reevaluate."
            )
            msg = "fail"
            del obj.__lazybase__.cache[obj.__lazyhexhash__]
            setvalue(obj, lazydo(obj, debug))
            obj.__lazybase__.cache[obj.__lazyhexhash__] = obj.__lazyvalue__

    # Object wasn't stored early. Evaluate it. Store it if not prevented.
    else:
        # Execute ...
        setvalue(obj, lazydo(obj, debug))
        if obj.__encache__:
            # with storing.
            msg = "save"
            obj.__lazybase__.cache[obj.__lazyhexhash__] = obj.__lazyvalue__
        else:
            # without storing.
            msg = "eval"

    if obj.__lazybase__.diag:
        if obj.__lazybase__.diag_values:
            print(msg, obj.__lazyhexhash__[:20] + "...", obj.__lazyvalue__)
        else:
            print(msg, obj.__lazyhexhash__[:20] + "...")

    # while isinstance(obj.__lazyvalue__, LazyObject):
    # 	setvalue(obj, expand(obj.__lazyvalue__))

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


def updatehash_list(m, obj, lobj):
    for e in obj:
        updatehash(m, e, lobj)


def updatehash_dict(m, obj, lobj):
    for k, v in sorted(obj.items()):
        updatehash(m, k, lobj)
        updatehash(m, v, lobj)


def updatehash_str(m, obj, lobj):
    m.update(obj.encode("utf-8"))


def updatehash_LazyObject(m, obj, lobj):
    m.update(obj.__lazyhash__)


def updatehash_NoExpand(m, obj, lobj):
    pass


def updatehash_function(m, obj, lobj):
    if hasattr(obj, "__qualname__"):
        if (
            obj.__qualname__ == "<lambda>"
            and lobj.__lazyhint__ is None
            and lobj.__lazybase__.function_dump is False
        ):
            print(
                "WARNING: evalcache cann't work with global lambdas correctly without hints or function_dump"
            )
        updatehash_str(m, obj.__qualname__, lobj)
    elif hasattr(obj, "__name__"):
        updatehash_str(m, obj.__name__, lobj)

    if lobj.__lazybase__.function_dump:
        # Pass inspection if sources is not available.
        try:
            updatehash_str(m, inspect.getsource(obj), lobj)
        except:
            pass

    if hasattr(obj, "__module__") and obj.__module__:
        updatehash_str(m, obj.__module__, lobj)
        if lobj.__lazybase__.function_file:
            updatehash_str(m, sys.modules[obj.__module__].__file__, lobj)


def updatehash_instancemethod(m, obj, lobj):
    if hasattr(obj, "__qualname__"):
        updatehash_str(m, obj.__qualname__, lobj)
    elif hasattr(obj, "__name__"):
        updatehash_str(m, obj.__name__, lobj)

    if hasattr(obj, "__module__") and obj.__module__:
        updatehash_str(m, obj.__module__, lobj)
        if lobj.__lazybase__.function_file:
            updatehash_str(m, sys.modules[obj.__module__].__file__, lobj)


# Table of hash functions for special types.
hashfuncs = {
    LazyObject: updatehash_LazyObject,
    NoExpand: updatehash_NoExpand,
    str: updatehash_str,
    tuple: updatehash_list,
    list: updatehash_list,
    dict: updatehash_dict,
    types.FunctionType: updatehash_function,
    "instancemethod": updatehash_instancemethod,
    # types.BuiltinFunctionType: updatehash_function,
    # types.BuiltinMethodType: updatehash_function,
}


def updatehash(m, obj, lobj):
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
    if lobj is not None and lobj.__lazybase__.updatehash_profiling:
        start = time.time()

    if obj.__class__ in hashfuncs:
        hashfuncs[obj.__class__](m, obj, lobj)
    elif obj.__class__.__name__ in hashfuncs:
        hashfuncs[obj.__class__.__name__](m, obj, lobj)
    else:
        if obj.__class__.__repr__ is object.__repr__:
            print(
                "WARNING: object of class {} uses common __repr__ method. Сache may not work correctly".format(
                    obj.__class__
                )
            )
        updatehash_str(m, repr(obj), lobj)

    if lobj is not None and lobj.__lazybase__.updatehash_profiling:
        end = time.time()
        print("updatehash elapse for {}: {}".format(repr(obj), end - start))


def setvalue(obj, value):
    obj.__lazyvalue__ = value
    obj.__lazyheap__ = True


__tree_tab = "    "


def print_tree(obj, t=0):
    """Print lazy tree in user friendly format."""
    if isinstance(obj, LazyObject):
        # print(__tree_tab*t, end=''); print("LazyObject:")
        if obj.generic:
            print(__tree_tab * t, end="")
            print("type: {}...\n".format(obj.__class__), end="")
            print(__tree_tab * t, end="")
            print("hash: {}...\n".format(obj.__lazyhexhash__[0:20]), end="")
            print(__tree_tab * t, end="")
            print("generic:\n", end="")
            print_tree(obj.generic, t + 1)
            if len(obj.args):
                print(__tree_tab * t, end="")
                print("args:\n", end="")
                print_tree(obj.args, t + 1)
            if len(obj.kwargs):
                print(__tree_tab * t, end="")
                print("kwargs:\n", end="")
                print_tree(obj.kwargs, t + 1)
            print(__tree_tab * t, end="")
            print("-------")
        else:
            print(__tree_tab * t, end="")
            print(obj.__lazyvalue__)
    elif isinstance(obj, list) or isinstance(obj, tuple):
        for o in obj:
            print_tree(o, t)
    else:
        print(__tree_tab * t, end="")
        print(obj)


def encache(obj, sts=True):
    obj.__encache__ = sts


def decache(obj, sts=True):
    obj.__decache__ = sts


def onuse(obj, sts=True):
    obj.__unlazyonuse__ = sts


def nocache(obj):
    obj.__encache__ = False
    obj.__decache__ = False


def lazy_getattr(obj, attr, wrapped_obj):
    """LazyObject`s getattr implementation
	
	If gettatr return LazyObject method, we rebind it from expanded class object to his lazy object 
	for strait hashchain supporting 
	"""

    ret = getattr(obj, attr)

    if (
        isinstance(ret, functools.partial)
        and isinstance(ret.func, LazyObject)
        and len(ret.args) == 1
    ):
        return functools.partial(ret.func, wrapped_obj.obj)

    return ret


# class lazyoperator:
# 	def __init__(self, op, mnem):
# 		self.op = op
# 		self.mnem = mnem

# 	def __repr__(self):
# 		return repr(self.op)
