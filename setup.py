#!/usr/bin/python3

from setuptools import setup
import glob
import os

import evalcache

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
	name = 'evalcache',
	version = evalcache.__version__,
	packages = ['evalcache'],
	author = 'mirmik',
	author_email = 'mirmikns@yandex.ru',
	description = 'Lazy computing tree cache library',
    long_description=long_description,
    long_description_content_type="text/markdown",
	license='MIT',
	url = 'https://github.com/mirmik/evalcache',
	keywords = ['caching', 'lazy'],
)