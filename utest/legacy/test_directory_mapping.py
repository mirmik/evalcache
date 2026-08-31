import os
import pickle
import threading

import pytest

from evalcache.legacy import DirCache_v2


class Unpicklable:
    def __reduce__(self):
        raise RuntimeError("cannot pickle")


class SlowPickle:
    def __init__(self, started, proceed):
        self.started = started
        self.proceed = proceed

    def __reduce__(self):
        self.started.set()
        if not self.proceed.wait(timeout=5):
            raise RuntimeError("timed out waiting to finish pickling")
        return str, ("new value",)


def test_new_prefix_is_visible_immediately(tmp_path):
    cache = DirCache_v2(str(tmp_path / "cache"))
    key = "ab" + "1" * 62

    cache[key] = {"value": 42}

    assert key in cache
    assert cache[key] == {"value": 42}
    assert key in cache.keys()


def test_cache_instances_see_each_others_writes(tmp_path):
    first = DirCache_v2(str(tmp_path / "cache"))
    second = DirCache_v2(str(tmp_path / "cache"))
    key = "cd" + "2" * 62

    first[key] = "written by first"

    assert key in second
    assert second[key] == "written by first"
    assert key in second.keys()


def test_failed_write_keeps_previous_value(tmp_path):
    cache = DirCache_v2(str(tmp_path / "cache"))
    key = "ef" + "3" * 62
    cache[key] = "complete value"

    with pytest.raises(RuntimeError, match="cannot pickle"):
        cache[key] = Unpicklable()

    assert cache[key] == "complete value"
    assert os.listdir(cache.tmpdir()) == []


def test_readers_keep_seeing_complete_value_during_write(tmp_path):
    cache = DirCache_v2(str(tmp_path / "cache"))
    key = "fa" + "4" * 62
    cache[key] = "old value"
    started = threading.Event()
    proceed = threading.Event()
    writer = threading.Thread(
        target=cache.__setitem__,
        args=(key, SlowPickle(started, proceed)),
    )

    writer.start()
    assert started.wait(timeout=5)
    assert cache[key] == "old value"
    proceed.set()
    writer.join(timeout=5)

    assert not writer.is_alive()
    assert cache[key] == "new value"


def test_make_path_to_keeps_v1_layout(tmp_path):
    cache = DirCache_v2(str(tmp_path / "cache"))
    key = "12" + "a" * 62

    assert cache.makePathTo(key) == str(tmp_path / "cache" / "12" / ("a" * 62))


def test_existing_v1_cache_entry_remains_readable(tmp_path):
    key = "34" + "b" * 62
    prefix = tmp_path / "cache" / "34"
    prefix.mkdir(parents=True)
    with (prefix / ("b" * 62)).open("wb") as cache_file:
        pickle.dump({"from": "v1"}, cache_file)

    cache = DirCache_v2(str(tmp_path / "cache"))

    assert key in cache
    assert cache[key] == {"from": "v1"}
