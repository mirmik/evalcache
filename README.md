#EvalCache

##Brief
	Caching lazy evaluation library.

##Details
	For each computed object, the library builds a hashkey based on the hashes of the object's generating 
	function and its arguments. If an lazy object is used as an argument or a generating function, 
	its previously generated hashkey is used as its hash. This allows you to build a dependent 
	computational tree. If the input data of an object changes, its hashkey and hashkeys of all objects 
	computed on its basis change. And the subtree will be reevaluated.

##Install
```pip3 install evalcache```

##Contact
mirmik(mirmikns@yandex.ru)
