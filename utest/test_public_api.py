import evalcache
import evalcache.v2 as former_v2
import subprocess
import sys
from evalcache.dircache import DirCache as ShimDirCache
from evalcache.lazy import Lazy as ShimLazy
from evalcache.legacy import DirCache as LegacyDirCache
from evalcache.legacy import Lazy as LegacyLazy


def test_expression_api_is_the_documented_top_level_surface():
    assert evalcache.operation is former_v2.operation
    assert evalcache.Expression is former_v2.Expression
    assert evalcache.DirectoryCacheStore is former_v2.DirectoryCacheStore
    assert "operation" in evalcache.__all__
    assert "DirectoryCacheStore" in evalcache.__all__
    assert "Lazy" not in evalcache.__all__


def test_original_import_paths_remain_as_legacy_shims():
    assert evalcache.Lazy is LegacyLazy is ShimLazy
    assert evalcache.DirCache is LegacyDirCache is ShimDirCache


def test_normal_import_does_not_eagerly_load_legacy_implementation():
    code = """
import sys
import evalcache
assert 'evalcache.legacy' not in sys.modules
assert 'evalcache.legacy.lazy' not in sys.modules
"""
    subprocess.check_call([sys.executable, "-c", code])
