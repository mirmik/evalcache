#!/usr/bin/python3
#coding:utf-8

import sys
sys.path.insert(0, "..")

import types
import unittest
import test_environment

class A:
    def __init__(self):
        self.i = 3

    def pr(self, *args, **kwargs):
        print()
        print(args, kwargs)
        print()


class TestLazy(unittest.TestCase):

    def tearDown(self):
        test_environment.clean()

    def test_arithmetic_full(self):  
        a = test_environment.lazy(1)
        b = test_environment.lazy(2)
        c = test_environment.lazy(3)
        d = test_environment.lazy(4)

        count = (a + b + c).unlazy()
        total_objects = test_environment.count_cached_objects()

        self.assertEqual(count, 6)
        self.assertEqual(total_objects, 2) #2 summ

    def test_arithmetic_part(self):
        a = test_environment.lazy(1)
        b = test_environment.lazy(2)
        c = test_environment.lazy(3)
        d = test_environment.lazy(4)

        count = (a + b + c + d).unlazy()
        total_objects = test_environment.count_cached_objects()

        self.assertEqual(count, 10)
        self.assertEqual(total_objects, 3) #3 summ


    def test_twoargs(self):  
        @test_environment.lazy
        def summ(a, b):
            return a + b

        summ(0, 0).unlazy()
        summ(0, 1).unlazy()
        summ(1, 1).unlazy()
        summ(1, 1).unlazy()
        summ(1, b=1).unlazy()
        summ(a=1, b=1).unlazy()
        summ(b=1, a=1).unlazy()

        total_objects = test_environment.count_cached_objects()
        self.assertEqual(total_objects, 5)

    def test_fibonachi(self):
        @test_environment.lazy
        def fib(n):
            if n < 2:
                return n
            return fib(n - 1) + fib(n - 2)

        ret = fib(9).unlazy()
        
        self.assertEqual(ret, 34)
        self.assertEqual(test_environment.count_cached_objects(), 18) #range(0-9) and 8 summ

    def test_method(self):
        A.lazy_pr = types.MethodType( test_environment.lazy(A.pr), A )
        A.lazy_pr(1, 2, 3, k=4).unlazy()

class TestMemoize(unittest.TestCase):

    def tearDown(self):
        test_environment.clean_memoize()

    def test_arithmetic(self):

        @test_environment.memoize
        def maker(n):
            return n

        a = test_environment.memoize(1)
        b = test_environment.memoize(2)
        c = maker(3)
        d = maker(4)

        self.assertEqual(len(test_environment.memoize.cache), 0) #no unlazy yet

        count = a + b + c + d

        self.assertEqual(len(test_environment.memoize.cache), 5) #c, d and 3 summ
        self.assertEqual(count, 10)


    def test_fibonachi(self):
        @test_environment.memoize
        def fib(n):
            if n < 2:
                return n
            return fib(n - 1) + fib(n - 2)

        ret = fib(9)

        self.assertEqual(ret, 34)
        self.assertEqual(len(test_environment.memoize.cache), 19) #range(0-9) and 9 summ and eq(assertEqual)


class TestOnplaceMemoize(unittest.TestCase):

    def tearDown(self):
        test_environment.clean_onplace_memoize()

    def test_arithmetic(self):

        @test_environment.onplace_memoize
        def maker(n):
            return n

        a = test_environment.onplace_memoize(1)
        b = test_environment.onplace_memoize(2)
        c = maker(3)
        d = maker(4)

        self.assertEqual(len(test_environment.onplace_memoize.cache), 2) #c, d

        count = a + b + c + d

        self.assertEqual(len(test_environment.onplace_memoize.cache), 3) #c, d and a+b
        self.assertEqual(count, 10)


    def test_fibonachi(self):

        @test_environment.onplace_memoize
        def fib(n):
            if n < 2:
                return n
            return fib(n - 1) + fib(n - 2)

        self.assertEqual(fib(9), 34)
        self.assertEqual(len(test_environment.onplace_memoize.cache), 10) #range(0-9)
        

if __name__ == '__main__':
    unittest.main()