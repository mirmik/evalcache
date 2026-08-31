#!/usr/bin/python3

from pathlib import Path

from setuptools import find_packages, setup


ROOT = Path(__file__).parent

setup(
    name="evalcache",
    version="2.0.0a1",
    packages=find_packages(),
    package_data={"evalcache": ["py.typed"]},
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    description="Decorator-first caching for reusable computation graphs",
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    license="MIT",
    license_files=["LICENSE"],
    url="https://github.com/mirmik/evalcache",
    keywords=["caching", "deferred", "lazy", "memoization"],
    python_requires=">=3.8",
)
