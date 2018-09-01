#!/usr/bin/python3

from setuptools import setup
import glob
import os

import evalcache

setup(
	name = 'evalcache',
	packages = ['evalcache'],
	version = evalcache.__version__,
	license='MIT',
	description = 'Disk cache for evaluation results',
	author = 'mirmik',
	author_email = 'mirmikns@yandex.ru',
	url = 'https://github.com/mirmik/evalcache',
	keywords = ['testing', 'caching'],
	classifiers = [],
	scripts = [],
)