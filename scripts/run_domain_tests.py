#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the Domain test suite without Odoo and without PostgreSQL.

How it works: a throwaway package is assembled in a temp directory containing
only the layers that must never import Odoo — ``core/``, ``dto/``, ``domain/`` —
plus the pure test modules. Everything Odoo-facing (``models/``,
``infrastructure/``, ``services/``) is left out entirely.

That makes this script a structural test as much as a unit test run. If someone
adds ``from odoo import ...`` anywhere in the Domain, this fails with an
ImportError, and the architecture rule from Part 2 §6 stops being a convention
that only holds while people remember it.

Usage:
    python3 scripts/run_domain_tests.py [-v]
"""

import os
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# addon -> (pure layers, pure test modules)
TARGETS = {
    'vn_core': (
        ('core', 'dto', 'domain'),
        ('fakes', 'test_calculators', 'test_ledger_engine',
         'test_serialization', 'test_aging',
         'test_financial_statement', 'test_tax',
         'test_inventory', 'test_cash_flow',
         'test_manufacturing', 'test_vat_declaration',
         'test_asset'),
    ),
}


def build_package(addon, layers, test_modules, workdir):
    """Assemble the Odoo-free subset of ``addon`` inside ``workdir``."""
    source = os.path.join(REPO_ROOT, addon)
    if not os.path.isdir(source):
        raise SystemExit('Addon not found: %s' % source)

    target = os.path.join(workdir, addon)
    os.makedirs(os.path.join(target, 'tests'))

    # A package root that imports nothing, unlike the real __init__.py which
    # has to pull in models/ for Odoo's registry.
    open(os.path.join(target, '__init__.py'), 'w').close()

    for layer in layers:
        os.symlink(os.path.join(source, layer), os.path.join(target, layer))

    for module in test_modules:
        os.symlink(os.path.join(source, 'tests', module + '.py'),
                   os.path.join(target, 'tests', module + '.py'))

    with open(os.path.join(target, 'tests', '__init__.py'), 'w') as handle:
        for module in test_modules:
            if module.startswith('test_'):
                handle.write('from . import %s\n' % module)

    return ['%s.tests.%s' % (addon, m) for m in test_modules
            if m.startswith('test_')]


def main():
    verbosity = ['-v'] if '-v' in sys.argv else []
    workdir = tempfile.mkdtemp(prefix='vn-domain-tests-')
    try:
        suites = []
        for addon, (layers, tests) in sorted(TARGETS.items()):
            suites += build_package(addon, layers, tests, workdir)

        print('Running Domain tests with no Odoo on the path:')
        for suite in suites:
            print('  %s' % suite)
        print()

        completed = subprocess.run(
            [sys.executable, '-m', 'unittest'] + suites + verbosity,
            cwd=workdir)
        return completed.returncode
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
