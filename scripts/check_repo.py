#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Structural checks that do not need Odoo.

Run before committing. Each check exists because the corresponding mistake has
already happened once and produced no error message at the time:

* invalid UTF-8 — a Vietnamese character loses a byte and the file still looks
  fine in a diff;
* Odoo imports leaking into the Domain — the architecture rule stops being a
  rule the moment nobody checks it;
* a bare group index in ``t-att-data-group`` — QWeb silently drops the
  attribute when the value is 0 and the first group stops collapsing;
* a translation entry with no ``model:ir.ui.menu`` reference — the menu quietly
  stays in English;
* APIs that only exist in Odoo 15 or 16;
* a README that claims a statutory form number the code does not implement —
  documentation drifting from code is how a reader ends up trusting the wrong
  thing;
* a design document with no entry in the Part 17 status map, which is how a
  reader ends up following a design that was never built;
* a Vietnamese source string in a menu or a view label, which produces a menu
  that is half translated whichever language the user picks;
* a statutory form number on a menu that the report behind it does not actually
  declare, which is a wrong number in front of an accountant;
* a method called on one of this project's own models that no class actually
  defines — appending to a file drops code into whichever class happens to be
  last, and Odoo only complains when a user clicks the button;
* a handoff file that no longer names every module, so whoever takes the
  project over updates the wrong set;
* an xlsxwriter call outside the version Odoo 14 pins, which works on the
  developer's machine and raises on the customer's;
* a toolbar button with no handler behind it, which renders perfectly and does
  nothing when clicked;
* a spreadsheet layout a wizard names but which does not exist, which fails
  only when somebody clicks Export;
* a translation left empty, which shows the English source to a Vietnamese user
  and never raises anything;
* a template that calls a shared table without declaring the variables that
  table reads — QWeb raises on an undefined name, so the report simply fails to
  render;
* an install or update command in the documentation that leaves a module out.
  The TT200 data writes to fields declared in vn_core, so updating only the
  downstream module fails on a missing column — and the command people copy is
  the one written here.

Usage:
    python3 scripts/check_repo.py
"""

import ast
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILURES = []


def fail(check, detail):
    FAILURES.append('%s: %s' % (check, detail))


def check_utf8():
    patterns = ('addons/**/*.py', 'addons/**/*.xml', 'addons/**/*.csv',
                'addons/**/*.po', 'addons/**/*.js', 'addons/**/*.scss',
                'docs/*.md', '*.md')
    for pattern in patterns:
        for path in glob.glob(os.path.join(ROOT, pattern), recursive=True):
            try:
                io.open(path, encoding='utf-8').read()
            except UnicodeDecodeError as error:
                fail('utf8', '%s — %s' % (os.path.relpath(path, ROOT), error))


def check_domain_is_pure():
    for path in glob.glob(os.path.join(ROOT, 'addons/*/'), recursive=False):
        for layer in ('core', 'dto', 'domain'):
            for source in glob.glob(os.path.join(path, layer, '**/*.py'),
                                    recursive=True):
                tree = ast.parse(io.open(source, encoding='utf-8').read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        names = [a.name for a in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        names = [node.module or '']
                    else:
                        continue
                    if any(n.split('.')[0] == 'odoo' for n in names):
                        fail('domain-purity', os.path.relpath(source, ROOT))


def check_group_keys():
    for path in glob.glob(os.path.join(ROOT, 'addons/*/report/*.xml')):
        content = io.open(path, encoding='utf-8').read()
        for match in re.finditer(r't-att-data-group(?:-child)?="([^"]+)"',
                                 content):
            if not match.group(1).startswith("'g%s'"):
                fail('qweb-group-key', '%s — %s'
                     % (os.path.relpath(path, ROOT), match.group(1)))


def check_menu_translations():
    for module in glob.glob(os.path.join(ROOT, 'addons/*/')):
        menus = os.path.join(module, 'views/menus.xml')
        po = os.path.join(module, 'i18n/vi.po')
        if not (os.path.exists(menus) and os.path.exists(po)):
            continue
        catalogue = io.open(po, encoding='utf-8').read()
        for name in re.findall(r'<menuitem[^>]*?name="([^"]+)"',
                               io.open(menus, encoding='utf-8').read(), re.S):
            block = re.search(
                r'((?:#[^\n]*\n)+)msgid "%s"' % re.escape(name), catalogue)
            if not block or 'ir.ui.menu' not in block.group(1):
                fail('menu-translation', '%s — %s'
                     % (os.path.basename(os.path.dirname(module)), name))


def check_odoo14_api():
    banned = (
        (r'\bfrom odoo import [^\n]*\bCommand\b', 'odoo.Command is 15.0+'),
        (r"_\(\s*'[^']*'\s*,", 'multi-argument _() is 16.0+'),
        (r'\btools\.create_index\b', 'import create_index from odoo.tools.sql'),
    )
    for source in glob.glob(os.path.join(ROOT, 'addons/**/*.py'),
                            recursive=True):
        content = io.open(source, encoding='utf-8').read()
        for pattern, message in banned:
            if re.search(pattern, content):
                fail('odoo14-api', '%s — %s'
                     % (os.path.relpath(source, ROOT), message))


def check_readme_matches_code():
    """The README's list of delivered reports must match the code.

    Scoped to the "Báo cáo đã có" section on purpose. Elsewhere the README
    names forms that are deliberately *not* built yet — the status table and the
    roadmap exist to say so — and flagging those would punish honesty.
    """
    readme_path = os.path.join(ROOT, 'README.md')
    if not os.path.exists(readme_path):
        return
    readme = io.open(readme_path, encoding='utf-8').read()
    if '## Báo cáo đã có' not in readme:
        fail('readme-forms', 'section "Báo cáo đã có" is missing')
        return
    section = readme.split('## Báo cáo đã có')[1].split('\n## ')[0]

    declared = set()
    for source in glob.glob(os.path.join(ROOT, 'addons/*/wizard/*.py')):
        declared |= set(re.findall(
            r"'(S\d+[a-z]?-DN|B\d+-DN|F\d+-DNN)'",
            io.open(source, encoding='utf-8').read()))

    for code in sorted(declared):
        if code not in section:
            fail('readme-forms', '%s implemented but absent from the list' % code)
    for code in sorted(set(re.findall(
            r'\b(S\d+[a-z]?-DN|B\d+-DN|F\d+-DNN)\b', section))):
        if code not in declared:
            fail('readme-forms', '%s listed as delivered but no wizard '
                                 'declares it' % code)

    menu_count = sum(
        len(re.findall(r'<menuitem id="menu_vn_report_[a-z_]+"',
                       io.open(path, encoding='utf-8').read()))
        for path in glob.glob(os.path.join(ROOT, 'addons/*/views/menus.xml')))
    rows = [line for line in section.split('\n')
            if line.startswith('|') and '---' not in line]
    listed = max(len(rows) - 1, 0)          # first row is the header
    if menu_count and listed != menu_count:
        fail('readme-forms',
             'README lists %s reports, menus declare %s' % (listed, menu_count))


def check_docs_have_status():
    """Every numbered design doc must appear in the Part 17 status map.

    Part 01-15 were written before the code and several of them describe
    structures that were deliberately not built. A reader who opens one of them
    cold has no way to know that, so each must carry a pointer and each must be
    accounted for in the map.
    """
    docs = sorted(glob.glob(os.path.join(ROOT, 'docs/[0-9]*.md')))
    status_path = os.path.join(ROOT, 'docs/17-implementation-status.md')
    if not docs:
        return
    if not os.path.exists(status_path):
        fail('docs-status', 'docs/17-implementation-status.md is missing')
        return
    status = io.open(status_path, encoding='utf-8').read()

    for path in docs:
        name = os.path.basename(path)
        number = name.split('-')[0]
        if name.startswith('17'):
            continue
        content = io.open(path, encoding='utf-8').read()
        if 'Part 17' not in content:
            fail('docs-status', '%s carries no pointer to Part 17' % name)
        if not re.search(r'\|\s*%s\b' % number, status):
            fail('docs-status', '%s has no row in the Part 17 status map' % name)


def check_source_strings_are_english():
    """Menu and view labels must be English in source, Vietnamese via i18n.

    Mixing the two conventions in one module guarantees an inconsistent menu:
    a Vietnamese source string never gets translated, so an English user sees
    it untouched next to properly translated neighbours — and a Vietnamese user
    sees the reverse whenever a translation fails to load.

    The statutory headings printed inside the reports are exempt: they live in
    QWeb templates, are fixed by Thông tư 200, and must print in Vietnamese
    regardless of the interface language.
    """
    patterns = (
        (r'<menuitem[^>]*?name="([^"]+)"', 'menu name'),
        (r'\bstring="([^"]+)"', 'view label'),
        (r'<field name="string">([^<]+)</field>', 'field label'),
    )
    for path in glob.glob(os.path.join(ROOT, 'addons/*/views/*.xml')):
        content = io.open(path, encoding='utf-8').read()
        for pattern, kind in patterns:
            for match in re.finditer(pattern, content, re.S):
                value = match.group(1)
                if any(ord(char) > 127 for char in value):
                    fail('source-language', '%s — %s %r is not English'
                         % (os.path.relpath(path, ROOT), kind, value))


FORM_CODE = re.compile(r'\b(S\d+[a-z]?-DN|B\d+-DN|F\d+-DNN)\b')


def check_menu_form_codes():
    """A form number on a menu must match what the report declares.

    The number lives in the wizard's ``_report_form_code``; repeating it in the
    menu label is a second copy, and two copies drift. So every number written
    on a menu is checked against the wizard the menu's action points at. A menu
    is free to carry no number — the aged balances and the VAT listings have
    none to carry — but it may not carry the wrong one.
    """
    for module_path in glob.glob(os.path.join(ROOT, 'addons/*/')):
        module = os.path.basename(os.path.dirname(module_path))
        menus_path = os.path.join(module_path, 'views/menus.xml')
        if not os.path.exists(menus_path):
            continue

        declared = {}
        for source in glob.glob(os.path.join(module_path, 'wizard/*.py')):
            content = io.open(source, encoding='utf-8').read()
            name = re.search(r"_name = '([\w.]+)'", content)
            if not name:
                continue
            body = re.search(
                r'def _report_form_code\(self\):(.*?)(?=\n    def |\Z)',
                content, re.S)
            declared[name.group(1)] = set(
                FORM_CODE.findall(body.group(1)) if body else [])

        views = ''.join(
            io.open(path, encoding='utf-8').read()
            for path in glob.glob(os.path.join(module_path, 'views/*.xml')))
        actions = dict(re.findall(
            r'<record id="([^"]+)" model="ir\.actions\.act_window">'
            r'.*?<field name="res_model">([^<]+)</field>', views, re.S))

        for menu_id, attrs in re.findall(r'<menuitem id="([^"]+)"(.*?)/>',
                                         views, re.S):
            label = re.search(r'name="([^"]+)"', attrs)
            action = re.search(r'action="([^"]+)"', attrs)
            if not label:
                continue
            used = set(FORM_CODE.findall(label.group(1)))
            if not used:
                continue
            if not action:
                fail('menu-form-code',
                     '%s — %s carries %s but opens no report'
                     % (module, menu_id, ', '.join(sorted(used))))
                continue
            model = actions.get(action.group(1).split('.')[-1])
            available = declared.get(model, set())
            for code in sorted(used - available):
                fail('menu-form-code',
                     '%s — %s claims %s, which %s does not declare'
                     % (module, menu_id, code, model or 'its report'))


def check_update_commands_are_complete():
    """Every -i / -u command in the docs must name all modules of this repo.

    The mapping data in l10n_vn_reports writes to fields declared on vn_core
    models. Odoo sorts the dependency graph itself, so updating them together
    always works — but it does not update a dependency you did not ask for, and
    a command missing one module fails with an undefined column. People copy
    these commands verbatim, so a command written short here becomes a broken
    database somewhere else.
    """
    modules = {os.path.basename(path.rstrip('/'))
               for path in glob.glob(os.path.join(ROOT, 'addons/*/'))}
    if not modules:
        return

    sources = ([os.path.join(ROOT, 'README.md')]
               + glob.glob(os.path.join(ROOT, 'docs/*.md')))
    for path in sources:
        if not os.path.exists(path):
            continue
        content = io.open(path, encoding='utf-8').read()
        for match in re.finditer(r'\s-[iu]\s+([\w,\\\s]+?)(?:\s|$)', content):
            listed = {name.strip() for name in match.group(1).split(',')
                      if name.strip() and name.strip() != '\\'}
            if not listed & modules:
                continue                      # not one of our commands
            for missing in sorted(modules - listed):
                fail('update-command',
                     '%s — command omits %s'
                     % (os.path.relpath(path, ROOT), missing))


#: Shared table templates and the variables a caller must set before t-call.
SHARED_TEMPLATE_VARS = {
    'statement_table': ('current_label', 'previous_label', 'drillable'),
}


def check_shared_template_contracts():
    """A caller of a shared table must set every variable that table reads.

    QWeb raises on an undefined name rather than treating it as false, so a
    caller that forgets one does not quietly lose a feature — the whole report
    fails to render. Making the contract explicit at each call site also states
    the intent: a print template setting ``drillable = False`` is saying that a
    sheet of paper has nothing to click, not merely forgetting to.
    """
    for path in glob.glob(os.path.join(ROOT, 'addons/*/report/*.xml')):
        content = io.open(path, encoding='utf-8').read()
        for name, body in re.findall(
                r'<template id="([^"]+)"[^>]*>(.*?)</template>', content, re.S):
            for shared, variables in SHARED_TEMPLATE_VARS.items():
                if name == shared:
                    continue
                if not re.search(r't-call="[\w.]*\.%s"' % shared, body):
                    continue
                for variable in variables:
                    if not re.search(r't-set="%s"' % variable, body):
                        fail('template-contract',
                             '%s — %s calls %s without setting %s'
                             % (os.path.relpath(path, ROOT), name, shared,
                                variable))


def check_translations_are_complete():
    """No catalogue entry may be left with an empty translation.

    An untranslated entry is not an error anywhere: Odoo falls back to the
    English source and the interface simply comes out in the wrong language. It
    is also how translations disappear — a regeneration that fails to carry an
    entry across leaves it empty, and without a check the loss is invisible
    until a user notices. The menu check above only covers menus; this covers
    everything.

    Parsing is wrap-aware on purpose: gettext splits long strings over several
    quoted lines, and a single-line reader misses exactly the longest entries.
    """
    for path in glob.glob(os.path.join(ROOT, 'addons/*/i18n/*.po')):
        module = os.path.basename(os.path.dirname(os.path.dirname(path)))
        msgid = msgstr = None
        mode = None
        empty = []

        def flush():
            if msgid and not msgstr:
                empty.append(msgid)

        for raw in io.open(path, encoding='utf-8'):
            line = raw.rstrip('\n')
            if line.startswith('msgid '):
                flush()
                msgid, msgstr, mode = line[7:-1], '', 'id'
            elif line.startswith('msgstr '):
                msgstr, mode = line[8:-1], 'str'
            elif line.startswith('"') and mode:
                if mode == 'id':
                    msgid += line[1:-1]
                else:
                    msgstr += line[1:-1]
            elif not line.strip():
                flush()
                msgid = msgstr = mode = None
        flush()

        for entry in empty:
            fail('translation', '%s — %r has no translation'
                 % (module, entry[:60]))


def check_xlsx_layouts_exist():
    """Every layout a wizard names must be registered.

    The name is a string, so a typo compiles, installs and sits quietly until an
    accountant clicks Export at the end of a quarter.
    """
    registry = os.path.join(ROOT,
                            'addons/l10n_vn_reports/report/xlsx_layouts.py')
    if not os.path.exists(registry):
        return
    content = io.open(registry, encoding='utf-8').read()
    block = re.search(r'LAYOUTS = \{(.*?)\}', content, re.S)
    available = set(re.findall(r"'([\w]+)':", block.group(1))) if block else set()

    for source in glob.glob(os.path.join(ROOT, 'addons/*/wizard/*.py')):
        text = io.open(source, encoding='utf-8').read()
        for match in re.finditer(
                r'def _xlsx_layout\(self\):\s*\n\s*return \'([\w]+)\'', text):
            if match.group(1) not in available:
                fail('xlsx-layout', '%s names layout %r, which is not registered'
                     % (os.path.relpath(source, ROOT), match.group(1)))


def check_toolbar_buttons_have_handlers():
    """Every viewer button must be bound to a handler.

    A button whose class appears in no events map still renders, still looks
    enabled, and does nothing at all when clicked. Nothing raises and nothing is
    logged — the user simply concludes the report is broken.
    """
    for module_path in glob.glob(os.path.join(ROOT, 'addons/*/')):
        module = os.path.basename(os.path.dirname(module_path))
        templates = glob.glob(os.path.join(module_path, 'static/src/xml/*.xml'))
        scripts = glob.glob(os.path.join(module_path, 'static/src/js/*.js'))
        if not (templates and scripts):
            continue

        handlers = ''.join(io.open(path, encoding='utf-8').read()
                           for path in scripts)
        for path in templates:
            markup = io.open(path, encoding='utf-8').read()
            for match in re.finditer(r'<button[^>]*class="([^"]*)"', markup):
                for css in match.group(1).split():
                    if not css.startswith('o_vn_'):
                        continue
                    if ("'click .%s'" % css) not in handlers:
                        fail('dead-button', '%s — %s has no handler'
                             % (module, css))


#: Workbook and worksheet methods present in XlsxWriter 1.1.2, the version
#: Odoo 14 pins. Anything else exists on some servers and not others, so it has
#: to be feature-detected rather than assumed.
XLSXWRITER_BASELINE = {
    'add_worksheet', 'add_format', 'close', 'write', 'write_string',
    'write_number', 'write_datetime', 'write_blank', 'set_column', 'set_row',
    'merge_range', 'freeze_panes', 'autofilter', 'set_landscape',
    'set_paper', 'hide_gridlines',
}


def check_xlsxwriter_baseline():
    """Calls into xlsxwriter must exist in the version Odoo 14 ships.

    This guard was written after ``Worksheet.ignore_errors`` — added in
    XlsxWriter 3.0 — shipped in an export and raised on a server running the
    pinned 1.1.2. The sandbox it was tested in had a newer library, so "verified
    against a real workbook" quietly meant "verified against a version the
    customer does not have".

    A newer method may still be used; it just has to be guarded by ``hasattr``
    so the export degrades instead of failing.
    """
    for path in glob.glob(os.path.join(ROOT, 'addons/*/report/*.py')):
        content = io.open(path, encoding='utf-8').read()
        if 'xlsxwriter' not in content:
            continue
        # Only the variables actually holding a workbook or a worksheet count.
        # Matching on names alone flagged a plain dict called ``sheet``, and a
        # guard that cries wolf gets switched off.
        holders = set(re.findall(r'(\w+)\s*=\s*xlsxwriter\.Workbook\(', content))
        holders |= set(re.findall(r'(\w+)\s*=\s*\w+\.add_worksheet\(', content))
        if not holders:
            continue

        pattern = r'\b(?:%s)\.(\w+)\(' % '|'.join(sorted(holders))
        for match in re.finditer(pattern, content):
            method = match.group(1)
            if method in XLSXWRITER_BASELINE:
                continue
            if "hasattr(" in content and ("'%s'" % method) in content:
                continue          # feature-detected, fine
            fail('xlsxwriter-version',
                 '%s calls %s(), which is not in the 1.1.2 baseline and is not '
                 'feature-detected' % (os.path.relpath(path, ROOT), method))


def check_handoff_is_current():
    """AGENTS.md must still name every module and both verification commands.

    It is the first thing whoever takes this over will read, and a handoff file
    that has fallen behind the code is worse than none: it is confidently wrong
    about the thing its reader has least ability to check.
    """
    path = os.path.join(ROOT, 'AGENTS.md')
    if not os.path.exists(path):
        fail('handoff', 'AGENTS.md is missing')
        return
    content = io.open(path, encoding='utf-8').read()

    modules = sorted(os.path.basename(p.rstrip('/'))
                     for p in glob.glob(os.path.join(ROOT, 'addons/*/')))
    if str(len(modules)) not in content:
        fail('handoff', 'AGENTS.md does not state the module count (%d)'
             % len(modules))
    for command in ('run_domain_tests.py', 'check_repo.py', 'update.sh'):
        if command not in content:
            fail('handoff', 'AGENTS.md does not mention %s' % command)


#: ORM methods every Odoo model inherits, so a call to one proves nothing.
ORM_BASICS = {
    'search', 'search_count', 'search_read', 'browse', 'create', 'write',
    'unlink', 'read', 'copy', 'exists', 'ensure_one', 'sudo', 'with_user',
    'with_company', 'with_context', 'with_env', 'ref', 'flush', 'fields_get',
    'name_get', 'name_search', 'default_get', 'mapped', 'filtered', 'sorted',
    'get_metadata', 'next_by_code',
}


def _declared_models():
    """-> ``{model_name: {method, ...}}`` for models this project defines.

    Methods are unioned across every class declaring the name, because Odoo
    composes a model from all of them: ``vn.ledger.provider`` picks up
    ``build_inventory_engine`` from a different module entirely.
    """
    import ast

    owned, methods = set(), {}
    for path in glob.glob(os.path.join(ROOT, 'addons/*/**/*.py'), recursive=True):
        try:
            tree = ast.parse(io.open(path, encoding='utf-8').read())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            names, is_own = [], False
            for stmt in node.body:
                if not (isinstance(stmt, ast.Assign)
                        and isinstance(stmt.value, ast.Constant)):
                    continue
                for target in stmt.targets:
                    if getattr(target, 'id', None) == '_name':
                        names.append(stmt.value.value)
                        is_own = True
                    elif getattr(target, 'id', None) == '_inherit':
                        names.append(stmt.value.value)
            for name in names:
                # Registering the name even with no methods matters: a model
                # missing from the map is silently treated as an Odoo core one,
                # which is exactly how the first version of this check passed
                # over a real bug.
                methods.setdefault(name, set())
                for stmt in node.body:
                    if isinstance(stmt, ast.FunctionDef):
                        methods[name].add(stmt.name)
            if is_own:
                owned.update(n for n in names)
    return {name: found for name, found in methods.items() if name in owned}


def check_model_methods_exist():
    """``self.env['x'].method()`` must resolve on a model this project owns.

    Appending a method to a file puts it in whichever class comes last, and a
    model is a runtime lookup — nothing fails at import, at install, or in any
    test that does not exercise that path. It fails when an accountant opens the
    report.
    """
    declared = _declared_models()
    if not declared:
        return
    pattern = re.compile(r"env\[[\'\"]([\w.]+)[\'\"]\]\s*\.\s*(\w+)\s*\(")

    for path in glob.glob(os.path.join(ROOT, 'addons/**/*.py'), recursive=True):
        content = io.open(path, encoding='utf-8').read()
        for match in pattern.finditer(content):
            model, method = match.group(1), match.group(2)
            if model not in declared or method in ORM_BASICS:
                continue
            if method not in declared[model]:
                fail('model-method',
                     '%s calls %s.%s(), which no class defines'
                     % (os.path.relpath(path, ROOT), model, method))


def main():
    for check in (check_utf8, check_domain_is_pure, check_group_keys,
                  check_menu_translations, check_odoo14_api,
                  check_readme_matches_code, check_docs_have_status,
                  check_source_strings_are_english,
                  check_menu_form_codes,
                  check_update_commands_are_complete,
                  check_shared_template_contracts,
                  check_translations_are_complete,
                  check_xlsx_layouts_exist,
                  check_toolbar_buttons_have_handlers,
                  check_xlsxwriter_baseline,
                  check_handoff_is_current,
                  check_model_methods_exist):
        check()
    if FAILURES:
        print('FAILED (%d)' % len(FAILURES))
        for failure in FAILURES:
            print('  ' + failure)
        return 1
    print('All structural checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
