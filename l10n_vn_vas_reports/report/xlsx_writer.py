# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""XLSX renderer.

Takes a declarative sheet description and produces a workbook. It knows nothing
about accounting: which columns a report has and what goes in them is decided in
``xlsx_layouts.py``, and there is one layout per **DTO shape** rather than per
report — sixteen reports share seven shapes, which is the reuse the DTOs were
for.

**On the xlsxwriter version.** Odoo 14 pins ``XlsxWriter==1.1.2``, which is
from 2018. Anything newer may be present on a given server but must never be
required: every call outside that baseline is feature-detected, and the workbook
is still correct without it — only less polished. ``scripts/check_repo.py``
enforces this, because the failure otherwise appears at the moment a user clicks
Export rather than at install.

**On OCA report_xlsx.** Not used, and not needed: Odoo 14 already ships
``xlsxwriter`` for its own list-view export, so the workbook can be built with
no dependency beyond the server itself.

**On Part 7.** That document proposed a ``ReportRenderer`` interface with a
family of implementations, and Part 17 §8.3 records why it was not built: one
renderer does not justify an interface. This is the second renderer, and the
answer has not changed — this is a concrete writer, not a polymorphic layer.
Nothing dispatches on renderer type; a wizard that wants a workbook calls this,
and one that wants a PDF calls QWeb.

A sheet is described as::

    {
        'name': 'So Cai',                       # tab name, <= 31 chars
        'heading': ['Đơn vị: ...', '...'],      # rows printed above the table
        'columns': [(label, width, kind), ...], # kind: text|date|number|money
        'rows': [(style, [value, ...]), ...],   # style: '', group, total, italic
    }
"""

import io

try:
    import xlsxwriter
    from xlsxwriter.utility import xl_col_to_name
except ImportError:                                  # pragma: no cover
    xlsxwriter = None
    xl_col_to_name = None

#: Tab names are limited by the file format and must not contain []:*?/\
INVALID_SHEET_CHARS = '[]:*?/\\'
MAX_SHEET_NAME = 31


class VnXlsxWriter:

    def __init__(self, decimal_places=0):
        # A workbook of VND with two decimal places would be noise; the number
        # format follows the reporting currency rather than a fixed guess.
        self.money_format = '#,##0' if not decimal_places else (
            '#,##0.' + '0' * decimal_places)

    # ------------------------------------------------------------------
    def build(self, sheets):
        """-> ``bytes`` of an xlsx workbook."""
        if xlsxwriter is None:                       # pragma: no cover
            raise RuntimeError(
                'xlsxwriter is not installed; it ships with Odoo 14.')

        stream = io.BytesIO()
        book = xlsxwriter.Workbook(stream, {
            'in_memory': True,
            # Dates are written as real dates, not strings, so the recipient can
            # sort and filter them.
            'default_date_format': 'dd/mm/yyyy',
        })
        formats = self._formats(book)
        used_names = set()

        for sheet in sheets:
            self._write_sheet(book, formats, sheet, used_names)

        book.close()
        return stream.getvalue()

    # ------------------------------------------------------------------
    def _formats(self, book):
        money = {'num_format': self.money_format}
        return {
            'title': book.add_format({'bold': True, 'font_size': 13,
                                      'align': 'center'}),
            'heading': book.add_format({'font_size': 9, 'italic': True}),
            'header': book.add_format({
                'bold': True, 'align': 'center', 'valign': 'vcenter',
                'text_wrap': True, 'bg_color': '#EEF1F4', 'border': 1}),
            'text': book.add_format({'border': 1}),
            'text_group': book.add_format({'border': 1, 'bold': True,
                                           'bg_color': '#F6F7F9'}),
            'text_total': book.add_format({'border': 1, 'bold': True,
                                           'top': 2}),
            'text_italic': book.add_format({'border': 1, 'italic': True}),
            'date': book.add_format({'border': 1, 'num_format': 'dd/mm/yyyy'}),
            'date_group': book.add_format({'border': 1, 'bold': True,
                                           'num_format': 'dd/mm/yyyy',
                                           'bg_color': '#F6F7F9'}),
            'date_total': book.add_format({'border': 1, 'bold': True, 'top': 2,
                                           'num_format': 'dd/mm/yyyy'}),
            'date_italic': book.add_format({'border': 1, 'italic': True,
                                            'num_format': 'dd/mm/yyyy'}),
            'money': book.add_format(dict(money, border=1)),
            'money_group': book.add_format(dict(money, border=1, bold=True,
                                                bg_color='#F6F7F9')),
            'money_total': book.add_format(dict(money, border=1, bold=True,
                                                top=2)),
            'money_italic': book.add_format(dict(money, border=1, italic=True)),
            'number': book.add_format({'border': 1, 'num_format': '#,##0.###'}),
            'number_group': book.add_format({'border': 1, 'bold': True,
                                             'num_format': '#,##0.###',
                                             'bg_color': '#F6F7F9'}),
            'number_total': book.add_format({'border': 1, 'bold': True,
                                             'top': 2,
                                             'num_format': '#,##0.###'}),
            'number_italic': book.add_format({'border': 1, 'italic': True,
                                              'num_format': '#,##0.###'}),
        }

    def _safe_name(self, name, used):
        for char in INVALID_SHEET_CHARS:
            name = name.replace(char, ' ')
        name = (name or 'Sheet')[:MAX_SHEET_NAME]
        candidate, suffix = name, 2
        while candidate in used:
            candidate = '%s %d' % (name[:MAX_SHEET_NAME - 3], suffix)
            suffix += 1
        used.add(candidate)
        return candidate

    def _write_sheet(self, book, formats, sheet, used_names):
        page = book.add_worksheet(self._safe_name(sheet.get('name'),
                                                  used_names))
        columns = sheet.get('columns') or []
        row = 0

        if sheet.get('title'):
            page.merge_range(row, 0, row, max(len(columns) - 1, 1),
                             sheet['title'], formats['title'])
            row += 2

        for line in sheet.get('heading') or []:
            page.write(row, 0, line, formats['heading'])
            row += 1
        if sheet.get('heading'):
            row += 1

        for index, (label, width, _kind) in enumerate(columns):
            page.write(row, index, label, formats['header'])
            page.set_column(index, index, width)
        header_row = row
        row += 1

        for style, values in sheet.get('rows') or []:
            for index, value in enumerate(values):
                if index >= len(columns):
                    break
                kind = columns[index][2]
                page.write(row, index, value,
                           self._format_for(formats, kind, style, value))
            row += 1

        # Freezing under the header keeps the column titles visible on a book
        # that runs to thousands of rows, which is the normal case here.
        page.freeze_panes(header_row + 1, 0)
        if columns:
            page.autofilter(header_row, 0, max(row - 1, header_row),
                            len(columns) - 1)
            self._silence_text_warnings(page, columns, header_row + 1, row)

    @staticmethod
    def _silence_text_warnings(page, columns, first_row, last_row):
        """Stop Excel flagging account codes as "number stored as text".

        An account code is text — 111 and 0111 are different accounts — but
        Excel sees digits in a text cell and puts a green triangle on every one
        of them. On a ledger that is a warning triangle against thousands of
        rows, which trains the reader to ignore warnings generally.

        ``ignore_errors`` arrived in XlsxWriter 3.0 while Odoo 14 pins 1.1.2, so
        the call is feature-detected. Without it the triangles come back; the
        figures do not change, and an export that works with a cosmetic blemish
        beats one that raises.
        """
        if last_row <= first_row or xl_col_to_name is None:
            return
        if not hasattr(page, 'ignore_errors'):
            return
        ranges = [
            '%s%d:%s%d' % (xl_col_to_name(index), first_row + 1,
                           xl_col_to_name(index), last_row)
            for index, (_label, _width, kind) in enumerate(columns)
            if kind == 'text'
        ]
        if ranges:
            page.ignore_errors({'number_stored_as_text': ' '.join(ranges)})

    @staticmethod
    def _format_for(formats, kind, style, value):
        if value is None or value == '':
            kind = 'text'
        key = kind if not style else '%s_%s' % (kind, style)
        return formats.get(key, formats.get(kind, formats['text']))
