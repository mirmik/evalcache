#!/usr/bin/python3

from setuptools import setup
import evalcache

setup(
	name = 'evalcache',
	version = evalcache.__version__,
	packages = ['evalcache'],
	author = 'mirmik',
	author_email = 'mirmikns@yandex.ru',
	description = 'Lazy computing tree cache library',
	long_description=open("README.md", "r").read(),
	long_description_content_type='text/markdown',
	license='MIT',
	url = 'https://github.com/mirmik/evalcache',
	keywords = ['caching', 'lazy'],
)