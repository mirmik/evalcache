#!/usr/bin/python3.5

from sympy import *
import numpy as np
import math
import evalcache

evalcache.enable_diagnostic()
lazy = evalcache.Lazy(evalcache.DirCache(".evalcache"))

pj1, psi, y0, gamma, gr= symbols("pj1 psi y0 gamma gr")

F = 2500
xright = 625
re = 625
y0 = 1650

gr = 2*math.pi / 360
#gamma = pi / 2

xj1q = xright + re * (1 - cos(psi))
yj1q = (xright + re) * tan(psi) - re * sin(psi) #+ y0
pj1 =  sqrt(xj1q**2 + yj1q**2)

pj2 = pj1 + y0 * sin(psi)
zj2 = (pj2**2)/4/F

asqrt = sqrt(pj2**2 + 4*F**2)

xp2 = 2*F / asqrt
yp2 = pj2 / asqrt
xp3 = yp2
yp3 = -xp2

xmpsi = 1295
gmpsi = 106 * gr
aepsi = 600 
bepsi = 125

b = 0.5*(1-cos(pi * gamma / gmpsi))

p1 = (
	(gamma * xmpsi / gmpsi * xp2) * (1-b) 
	+ (aepsi * xp2 * sin(gamma) + bepsi * yp2 * (1-cos(gamma)))*b + pj1
)

p1 = lazy(simplify)(p1)

Na = 200
angles = [t * 2 * math.pi / 360 / Na * 106 for t in range(0,Na+1)]

N = int(200)
a = (np.arange(0,N+1) - N/2) * 90/360*2*math.pi/N

@lazy
def genarray(angles, a, p1):
	points = []
	for i in range(0, len(angles)):
		ex = p1.subs(gamma, angles[i])
		func = lambdify(psi, ex, 'numpy') # returns a numpy-ready function
		rads = func(a)
		xs = rads*np.cos(a)
		ys = rads*np.sin(a)
		arr = np.column_stack((xs,ys,[i*2]*len(xs)))
		points.append(arr)
	return points

arr = genarray(angles, a, p1)
arr.unlazy()

#print(points)

#lazy_solve = lazy(sympy.solve)
#ret = sympy.solve((eq1,eq2), (x,y))

#print(ret)

#print(evalcache.unlazy(ret))