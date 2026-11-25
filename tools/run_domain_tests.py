#!/usr/bin/env python3
"""Run the pure-Python unit tests of ``vn_core/tests`` without Odoo.

The domain layer of ``vn_core`` (``core``, ``domain``, ``dto``) does not import
Odoo, and most of ``vn_core/tests`` exercises only that layer with plain
``unittest`` test cases. Odoo's test runner does not collect them because they
are not Odoo test cases, so this script runs them instead.

``vn_core/__init__.py`` imports Odoo, so the package cannot be imported the
normal way. The script registers empty ``vn_core`` and ``vn_core.tests``
package objects pointing at the source folders, which lets the tests' relative
imports (``from ..domain import ...``) resolve without executing that
``__init__``.

Test modules that import ``odoo`` themselves are skipped; they run under
``odoo-bin --test-enable``. Any other import error is a failure: it usually
means Odoo crept into the domain layer.

Usage::

    python3 tools/run_domain_tests.py [REPO_ROOT] [-v]

REPO_ROOT defaults to the parent of this script's folder. No dependencies
beyond the standard library.
"""

import argparse
import ast
import importlib
import pathlib
import sys
import types
import unittest

PACKAGE = "vn_core"


def imports_odoo(path):
    """Return True if the module at ``path`` imports ``odoo`` directly."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names = [node.module or ""]
        else:
            continue
        if any(name == "odoo" or name.startswith("odoo.") for name in names):
            return True
    return False


def register_namespace(name, path):
    """Register an empty package ``name`` whose submodules live in ``path``."""
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module


def build_suite(root):
    """Return the suite of Odoo-free tests and the names of skipped files."""
    package_dir = root / PACKAGE
    tests_dir = package_dir / "tests"
    if not tests_dir.is_dir():
        sys.exit(f"error: {tests_dir} not found; pass the repository root")

    register_namespace(PACKAGE, package_dir)
    register_namespace(f"{PACKAGE}.tests", tests_dir)

    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    skipped = []
    for file in sorted(tests_dir.glob("test_*.py")):
        if imports_odoo(file):
            skipped.append(file.name)
            continue
        module = importlib.import_module(f"{PACKAGE}.tests.{file.stem}")
        suite.addTests(loader.loadTestsFromModule(module))
    return suite, skipped


def main(argv=None):
    """Run the tests; return the process exit status."""
    summary = (__doc__ or "Run the vn_core domain tests without Odoo.").splitlines()
    parser = argparse.ArgumentParser(description=summary[0])
    parser.add_argument(
        "root",
        nargs="?",
        default=pathlib.Path(__file__).resolve().parent.parent,
        type=pathlib.Path,
        help="repository root (default: parent of tools/)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    suite, skipped = build_suite(args.root.resolve())
    for name in skipped:
        sys.stderr.write(f"skipped {name}: imports odoo, runs under odoo-bin\n")
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    return 0 if result.wasSuccessful() and result.testsRun else 1


if __name__ == "__main__":
    sys.exit(main())
