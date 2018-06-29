#!/usr/bin/python3.5

import sympy
import evalcache

evalcache.enable()

x,y,z = sympy.symbols("x y z")

eq1 = sympy.Eq(x*x + y*y + z*z, 42)
eq2 = sympy.Eq(x + y + z, 1)

@evalcache.lazy()
def do_solve(eqs, vars):
	return sympy.solve(eqs, vars)
ret = evalcache.lazy()(lambda x, y: sympy.solve(x, y))((eq1,eq2), (x,y)).eval()

print(evalcache.gethash(ret))

print(ret)