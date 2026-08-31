# Examples

The files in this directory demonstrate the primary decorator-first API:

- basic.py creates a deferred computation with @evalcache.operation;
- disk_cache.py persists results with DirectoryCacheStore;
- expression_tree.py composes a graph of dependent operations;
- operators.py uses the operators supported by Deferred;
- advanced_decorators.py supplies operation identity, version, validation,
  custom hashing, and cache policy;
- file_artifact.py caches immutable file contents.

Examples for the original Lazy API live in legacy/.
