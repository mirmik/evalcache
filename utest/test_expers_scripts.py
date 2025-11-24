import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERS_DIR = REPO_ROOT / "expers"


def _load_module(module_name):
    base = EXPERS_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, base)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


sympy_test = _load_module("sympy_test")
testimplicit = _load_module("testimplicit")


def _expers_scripts():
    return sorted(
        p for p in EXPERS_DIR.glob("*.py") if p.name != "__init__.py"
    )


@pytest.mark.parametrize("script", _expers_scripts())
def test_expers_scripts_run(script, tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"{script.name} failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )


def test_sympy_example_runs(tmp_path):
    cache_dir = tmp_path / "evalcache"
    arr = sympy_test.run(na=5, n=10, cache_dir=str(cache_dir), diag=False)
    assert isinstance(arr, list)
    assert len(arr) == 6  # na + 1
    first = arr[0]
    assert first.shape[1] == 3
    assert first.shape[0] == 11  # n + 1


def test_implicit_example_runs(tmp_path):
    cache_dir = tmp_path / "implicit_cache"
    res = testimplicit.run(cache_dir=str(cache_dir))
    assert res == 9
