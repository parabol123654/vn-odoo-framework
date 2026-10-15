# -*- coding: utf-8 -*-
# Target: Odoo 20.0 Community Edition
"""A company's notes to the financial statements for one year (B09).

Stored, not generated on the fly, because the circular says where the
comparative figures come from: "Số đầu năm" is copied from the "Số cuối năm"
column of last year's notes and "Năm trước" from last year's "Năm nay"
(TT133 Điều 81 mục 2.5.5, 2.5.6), not recomputed from the ledger. Last year's
figures can differ from what the ledger says today: a restatement adjusts the
opening column and explains why. So each year's notes are kept, and locked
once filed, and next year's notes read them.

When there are no notes for the year before — the first year a company uses
this module — the comparative is read from the ledger instead, and every row
says so.

The text is the company's: it starts from the previous year's notes, or from
the template the first time, and is edited freely until the notes are locked.
"""

from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.core.enums import TargetMove
from odoo.addons.vn_core.core.utils.number import is_zero, round_amount
from odoo.addons.vn_core.domain.financial_statement.formula import (
    FormulaEvaluator,
)
from odoo.addons.vn_core.domain.financial_statement.notes import (
    NotesCalculator,
)
from odoo.addons.vn_core.dto.filters import LedgerFilter
from odoo.addons.vn_core.dto.notes import (
    NoteRowDTO, NoteRowValueDTO, NoteTableDTO,
)

from ..wizard.base_report_wizard import (
    FORM_LEGAL_LINE, FORM_PREPARER, FORM_SIGNER,
)

#: Fields of a row a user may type into. Writing any of them outside a
#: computation marks the row as edited by hand, so recomputing keeps it.
VALUE_FIELDS = ('current', 'comparative', 'increase', 'decrease')


class VnFsNote(models.Model):
    _name = 'vn.fs.note'
    _description = 'Notes to the Financial Statements'
    _order = 'date_to desc, id desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    template_id = fields.Many2one(
        'vn.fs.note.template', string='Form', required=True,
        check_company=True,
        domain="['|', ('company_id', '=', False), "
               "('company_id', '=', company_id)]",
        help="Defaults to the form of the company's circular.")
    version = fields.Char(related='template_id.version')
    date_from = fields.Date(string='Year start', required=True)
    date_to = fields.Date(string='Year end', required=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('locked', 'Locked')],
        default='draft', required=True, readonly=True, copy=False,
        help="Locked notes cannot be changed. Next year's notes copy their "
             "comparative figures from them.")
    computed_on = fields.Datetime(readonly=True, copy=False)
    locked_on = fields.Datetime(readonly=True, copy=False)
    locked_by = fields.Many2one('res.users', readonly=True, copy=False)
    previous_note_id = fields.Many2one(
        'vn.fs.note', compute='_compute_previous_note',
        string="Last year's notes",
        help="The locked notes of the year ending the day before this one "
             "starts. The comparative figures are copied from them.")
    report_date = fields.Date(
        string='Date prepared',
        help="Printed as \"Lập, ngày … tháng … năm …\". Left blank on the "
             "form when empty.")
    preparer_name = fields.Char(string='Prepared by')
    chief_accountant_name = fields.Char(string='Chief accountant')
    representative_name = fields.Char(string='Legal representative')
    accounting_service = fields.Text(
        help="When bookkeeping or the chief accountant's role is outsourced, "
             "the form asks for the service provider's name and practising "
             "certificate number.")
    item_ids = fields.One2many('vn.fs.note.item', 'note_id', string='Items')
    row_ids = fields.One2many('vn.fs.note.row', 'note_id', string='Rows')
    check_ids = fields.One2many('vn.fs.note.check', 'note_id',
                                string='Checks', readonly=True)
    check_state = fields.Selection(
        [('none', 'Not computed'), ('ok', 'Agrees'),
         ('mismatch', 'Differences')],
        compute='_compute_check_state')

    _company_template_year_uniq = models.Constraint(
        'unique(company_id, template_id, date_to)',
        'There are already notes on this form for this year.',
    )

    # ------------------------------------------------------------------
    # Defaults and computed fields
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        company = self.env['res.company'].browse(
            values.get('company_id')) or self.env.company
        if 'date_to' in fields_list and not values.get('date_to'):
            # The year just closed: the notes are written after year end.
            this_year = company.compute_fiscalyear_dates(
                fields.Date.context_today(self))
            last_year = company.compute_fiscalyear_dates(
                this_year['date_from'] - timedelta(days=1))
            values['date_from'] = last_year['date_from']
            values['date_to'] = last_year['date_to']
        if 'template_id' in fields_list and not values.get('template_id'):
            template = self.env['vn.fs.note.template'].search([
                ('version', '=ilike', company.vn_accounting_circular or ''),
                '|', ('company_id', '=', False),
                ('company_id', '=', company.id),
            ], order='company_id desc, sequence, id', limit=1)
            values['template_id'] = template.id
        return values

    @api.depends('template_id.form_code', 'date_to', 'company_id.name')
    def _compute_name(self):
        for note in self:
            note.name = '%s %s' % (note.template_id.form_code or 'B09',
                                   note.date_to.year if note.date_to else '')

    def _compute_previous_note(self):
        for note in self:
            note.previous_note_id = note._previous_note()

    @api.depends('check_ids.state')
    def _compute_check_state(self):
        for note in self:
            if not note.check_ids:
                note.check_state = 'none'
            elif any(c.state == 'mismatch' for c in note.check_ids):
                note.check_state = 'mismatch'
            else:
                note.check_state = 'ok'

    def _previous_note(self):
        """Last year's locked notes on the same form, if any."""
        self.ensure_one()
        if not self.date_from:
            return self.browse()
        return self.search([
            ('company_id', '=', self.company_id.id),
            ('template_id.form_code', '=', self.template_id.form_code),
            ('date_to', '=', self.date_from - timedelta(days=1)),
            ('state', '=', 'locked'),
            ('id', '!=', self.id or 0),
        ], limit=1)

    # ------------------------------------------------------------------
    # Creation: copy the template, and last year's text
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        notes = super().create(vals_list)
        for note in notes:
            note._check_dates()
            note._populate()
        return notes

    def _check_dates(self):
        for note in self:
            if note.date_from > note.date_to:
                raise UserError(_("The year must start before it ends."))

    def _populate(self):
        """Lay out items and rows from the template.

        Text comes from last year's notes when there are some (the circular
        builds this year's notes on last year's, Điều 81 mục 2.5.3), from the
        template otherwise.
        """
        self.ensure_one()
        previous = self._previous_note()
        previous_text = {
            item.template_item_id.id: item.content
            for item in previous.item_ids if item.template_item_id
        }
        placeholders = {
            'date_from': self.date_from.strftime('%d/%m/%Y'),
            'date_to': self.date_to.strftime('%d/%m/%Y'),
            'currency': self.company_id.currency_id.name or '',
        }
        Item = self.env['vn.fs.note.item']
        Row = self.env['vn.fs.note.row']
        for template_item in self.template_id.item_ids:
            default = str(template_item.default_text or '')
            content = previous_text.get(template_item.id)
            # Text built from the dates or the currency (II.1, II.2) is made
            # afresh: last year's says last year's dates.
            if content is None or any('{%s}' % key in default
                                      for key in placeholders):
                content = self._fill(template_item.default_text, placeholders)
            item = Item.create({
                'note_id': self.id,
                'template_item_id': template_item.id,
                'sequence': template_item.sequence,
                'content': content,
            })
            Row.with_context(vn_fs_note_compute=True).create([{
                'note_id': self.id,
                'item_id': item.id,
                'template_row_id': row.id,
                'sequence': row.sequence,
            } for row in template_item.row_ids])

    @staticmethod
    def _fill(text, placeholders):
        if not text:
            return text
        value = str(text)
        for key, replacement in placeholders.items():
            value = value.replace('{%s}' % key, replacement)
        return Markup(value)

    # ------------------------------------------------------------------
    # Locking
    # ------------------------------------------------------------------
    def _check_editable(self):
        if self.env.context.get('vn_fs_note_unlock'):
            return
        if any(note.state == 'locked' for note in self):
            raise UserError(_(
                "These notes are locked. Unlock them first; only an "
                "accounting manager can."))

    def write(self, vals):
        # The state only moves through action_lock and action_unlock, which
        # check who may do it; a plain write must not unlock the notes.
        if {'state', 'locked_on', 'locked_by'} & set(vals) \
                and not self.env.context.get('vn_fs_note_state'):
            raise UserError(_("Use the Lock and Unlock buttons."))
        if set(vals) - {'state', 'locked_on', 'locked_by'}:
            self._check_editable()
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        return super().unlink()

    def action_lock(self):
        for note in self:
            if note.state != 'draft':
                continue
            if not note.computed_on:
                raise UserError(_(
                    "Compute the figures before locking the notes."))
            note.with_context(vn_fs_note_state=True).write({
                'state': 'locked', 'locked_on': fields.Datetime.now(),
                'locked_by': self.env.uid})

    def action_unlock(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_("Only an accounting manager can unlock notes."))
        self.with_context(vn_fs_note_unlock=True, vn_fs_note_state=True).write(
            {'state': 'draft', 'locked_on': False, 'locked_by': False})

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            'l10n_vn_vas_reports.action_report_fs_note').report_action(self)

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------
    def _ledger_filter(self, date_from, date_to):
        return LedgerFilter(
            date_from=date_from, date_to=date_to,
            company_ids=(self.company_id.id,),
            target_move=TargetMove.POSTED)

    def _previous_filter(self):
        last_day = self.date_from - timedelta(days=1)
        year = self.company_id.compute_fiscalyear_dates(last_day)
        return self._ledger_filter(year['date_from'], last_day)

    def action_compute(self):
        """Read the tables from the ledger and check them.

        Rows edited by hand keep their figures; formula rows are totalled
        again, hand-filled rows included. The comparative column is copied
        from last year's notes when they exist.
        """
        for note in self:
            note._check_editable()
            note._compute_tables()
            note._compute_checks()
            note.with_context(vn_fs_note_compute=True).computed_on = \
                fields.Datetime.now()
        return True

    def _compute_tables(self):
        self.ensure_one()
        calculator = self.env['vn.ledger.provider'].build_notes_calculator()
        rounding = self.company_id.currency_id.rounding
        year = self._ledger_filter(self.date_from, self.date_to)
        previous_year = self._previous_filter()
        previous = self._previous_note()
        last_year = {
            (row.template_row_id.item_id.id, row.code): row.current
            for row in previous.row_ids
        }
        Row = self.env['vn.fs.note.row'].with_context(vn_fs_note_compute=True)

        for item in self.item_ids.filtered(lambda i: i.kind == 'table'):
            table = item._table_dto()
            ledger = calculator.compute(table, year, previous_year)
            values, updates = {}, []
            for row in item.row_ids:
                if row.source in ('formula', 'previous'):
                    continue
                if row.manual:
                    # Typed in by hand: every column stays as typed.
                    values[row.code] = row._value_dto()
                    continue
                if row.source == 'ledger':
                    figure = ledger.get(row.code, NoteRowValueDTO(row.code))
                    origin = 'ledger' if figure.opening is not None else 'none'
                else:
                    figure, origin = row._value_dto(), row.comparative_origin
                key = (row.template_row_id.item_id.id, row.code)
                if key in last_year:
                    # The comparative is last year's notes, not the ledger.
                    figure = figure._replace(opening=last_year[key])
                    origin = 'previous'
                values[row.code] = figure
                updates.append((row, figure, origin))

            # Rows that print another row's comparative (TT99's "… năm
            # trước" lines): last year's figures, by way of that row.
            for row in item.row_ids.filtered(
                    lambda r: r.source == 'previous'):
                source = values.get(row.template_row_id.formula.strip())
                figure = NoteRowValueDTO(
                    row.code,
                    current=(source.opening or 0.0) if source else 0.0)
                values[row.code] = figure
                updates.append((row, figure, 'previous' if previous
                                else 'ledger' if source else 'none'))

            totals = NotesCalculator.apply_formulas(table, values, rounding)
            for row in item.row_ids.filtered(lambda r: r.source == 'formula'):
                figure = totals[row.code]
                origin = ('previous' if previous else
                          'ledger' if figure.opening is not None else 'none')
                updates.append((row, figure, origin))

            for row, figure, origin in updates:
                Row.browse(row.id).write({
                    'current': figure.current,
                    'comparative': figure.opening or 0.0,
                    'increase': figure.increase or 0.0,
                    'decrease': figure.decrease or 0.0,
                    'comparative_origin': origin,
                })

    def _compute_checks(self):
        """Compare rows with the statements and with their breakdown."""
        self.ensure_one()
        rounding = self.company_id.currency_id.rounding
        self.check_ids.unlink()
        checks = []
        statements = {}
        rows = self.row_ids.sorted(lambda r: (r.item_id.sequence, r.sequence))
        for row in rows:
            template_row = row.template_row_id
            if template_row.statement_check:
                checks.append(self._statement_check(row, statements,
                                                    rounding))
            if template_row.detail_formula:
                checks.append(self._detail_check(row, rounding))
        self.env['vn.fs.note.check'].create(
            [dict(c, note_id=self.id) for c in checks if c])

    def _statement_check(self, row, statements, rounding):
        form_code, _sep, line_code = \
            row.template_row_id.statement_check.partition(':')
        label = '%s %s ↔ %s, mã số %s' % (row.item_id.reference or '',
                                         row.name, form_code,
                                         line_code.lstrip('-'))
        if form_code not in statements:
            statements[form_code] = self._statement(form_code)
        mapping, report = statements[form_code]
        if report is None:
            return {'row_id': row.id, 'name': label, 'state': 'skipped',
                    'message': mapping}
        # "-152": the statement prints the item negative, the notes don't.
        factor = -1 if line_code.startswith('-') else 1
        line = report.by_code(line_code.lstrip('-'))
        if line is None:
            return {'row_id': row.id, 'name': label, 'state': 'skipped',
                    'message': _("Item %(code)s is not on %(form)s.")
                    % {'code': line_code, 'form': form_code}}
        expected = factor * line.amount
        difference = round_amount(row.current - expected, rounding)
        if row.source == 'manual' and not row.manual \
                and not is_zero(difference, rounding):
            # A row filled in by hand that nobody has filled in yet: a to-do,
            # not a disagreement (TT99 VII.11 "Lợi nhuận kế toán trước thuế").
            return {'row_id': row.id, 'name': label, 'state': 'info',
                    'expected': expected, 'actual': row.current,
                    'difference': difference,
                    'message': _("Not filled in yet.")}
        return {
            'row_id': row.id, 'name': label,
            'expected': expected, 'actual': row.current,
            'difference': difference,
            'state': 'ok' if is_zero(difference, rounding) else 'mismatch',
        }

    def _statement(self, form_code):
        """-> (mapping or reason, statement DTO or None) for a form number.

        A row is only checked against the form the company actually presents:
        under TT133 a company files B01a-DNN or B01b-DNN, not both.
        """
        circular = self.company_id.vn_accounting_circular or 'TT200'
        Mapping = self.env['vn.report.mapping']
        mapping = Mapping.search([
            ('form_code', '=', form_code),
            ('version', '=ilike', circular),
            '|', ('company_id', '=', False),
            ('company_id', '=', self.company_id.id),
        ], order='company_id desc, sequence, id', limit=1)
        if not mapping:
            return (_("No %(form)s statement under %(circular)s.")
                    % {'form': form_code, 'circular': circular}, None)
        presented = Mapping.default_for(mapping.report_type, self.company_id)
        if presented != mapping:
            return (_("The company presents %(form)s instead.")
                    % {'form': presented.form_code}, None)
        date_from = self.date_from if mapping.basis == 'movement' else None
        engine = self.env['vn.ledger.provider'] \
            .build_financial_statement_engine()
        report = engine.compute(self._ledger_filter(date_from, self.date_to),
                                mapping.code, with_diagnostics=False)
        return mapping, report

    def _detail_check(self, row, rounding):
        formula = row.template_row_id.detail_formula
        siblings = {r.code: r for r in row.item_id.row_ids}
        codes = FormulaEvaluator.referenced_codes(formula)
        amounts = {c: siblings[c].current for c in codes if c in siblings}
        label = '%s %s: %s' % (row.item_id.reference or '', row.name,
                               _('breakdown'))
        if all(is_zero(v, rounding) for v in amounts.values()):
            if is_zero(row.current, rounding):
                return None
            return {'row_id': row.id, 'name': label, 'state': 'info',
                    'expected': row.current, 'actual': 0.0,
                    'difference': row.current,
                    'message': _("Not broken down yet: fill in the rows "
                                 "below it.")}
        total = round_amount(FormulaEvaluator.evaluate(formula, amounts),
                             rounding)
        difference = round_amount(total - row.current, rounding)
        return {
            'row_id': row.id, 'name': label,
            'expected': row.current, 'actual': total,
            'difference': difference,
            'state': 'ok' if is_zero(difference, rounding) else 'mismatch',
        }

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------
    def _template_values(self):
        self.ensure_one()
        circular = self.version or 'TT200'
        return {
            'doc': self,
            'company': self.company_id,
            'currency': self.company_id.currency_id,
            'form_code': self.template_id.form_code,
            'form_title': self.template_id.form_title,
            'form_legal': FORM_LEGAL_LINE.get(circular, ()),
            'form_signer': FORM_SIGNER.get(circular, FORM_SIGNER['TT200']),
            'form_preparer': FORM_PREPARER.get(circular, 'Người lập biểu'),
        }


class VnFsNoteItem(models.Model):
    _name = 'vn.fs.note.item'
    _description = 'Notes to the Financial Statements: Item'
    _order = 'sequence, id'

    note_id = fields.Many2one('vn.fs.note', required=True,
                              ondelete='cascade', index=True)
    state = fields.Selection(related='note_id.state')
    template_item_id = fields.Many2one('vn.fs.note.template.item',
                                       required=True, ondelete='restrict')
    sequence = fields.Integer()
    number = fields.Char(related='template_item_id.number')
    reference = fields.Char(related='template_item_id.reference')
    name = fields.Char(related='template_item_id.name')
    level = fields.Integer(related='template_item_id.level')
    kind = fields.Selection(related='template_item_id.kind')
    layout = fields.Selection(related='template_item_id.layout')
    display = fields.Selection(related='template_item_id.display')
    column_labels = fields.Char(related='template_item_id.column_labels')
    measures = fields.Char(related='template_item_id.measures')
    periods = fields.Selection(related='template_item_id.periods')
    guidance = fields.Text(related='template_item_id.guidance')
    show_unit = fields.Boolean(related='template_item_id.show_unit')
    content = fields.Html(sanitize=True)
    hidden = fields.Boolean(
        string='Leave out',
        help="Not printed. An item with nothing to report need not be "
             "presented (TT133 Điều 72 khoản 6).")
    row_ids = fields.One2many('vn.fs.note.row', 'item_id', string='Rows')

    def write(self, vals):
        self.note_id._check_editable()
        return super().write(vals)

    def _table_dto(self):
        """The table as the Domain sees it."""
        self.ensure_one()
        rows = []
        for row in self.row_ids:
            template_row = row.template_row_id
            rows.append(NoteRowDTO(
                code=template_row.code,
                expression=(template_row.expression
                            if template_row.source == 'ledger' else ''),
                formula=(template_row.formula
                         if template_row.source == 'formula' else ''),
                sign=template_row.sign,
                side=template_row.side,
                split_by_partner=template_row.split_by_partner,
                movement_side=template_row.movement_side,
                figure=(template_row.figure or ''
                        if template_row.source == 'ledger' else ''),
                maturity=template_row.maturity or 'all'))
        return NoteTableDTO(
            code=self.reference or str(self.template_item_id.id),
            layout=self.layout, rows=tuple(rows),
            closing_expression=self.note_id.template_id.closing_expression
            or '')


    #: Column headings the forms print, per layout and display.
    DEFAULT_LABELS = {
        'balance': ('Cuối năm', 'Đầu năm'),
        'period': ('Năm nay', 'Năm trước'),
        'standard': ('Số dư đầu năm', 'Tăng trong năm', 'Giảm trong năm',
                     'Số dư cuối năm'),
        'tax': ('Đầu năm', 'Số phải nộp trong năm',
                'Số đã thực nộp trong năm', 'Cuối năm'),
        'loan': ('Cuối năm', 'Tăng', 'Giảm', 'Đầu năm'),
        'equity': ('Số dư đầu năm', 'Tăng vốn trong năm',
                   'Giảm vốn trong năm', 'Số dư cuối năm'),
    }

    def print_grid(self):
        """A table with several measures, laid out as the form prints it.

        -> ``(period_headers, measure_headers, lines)``. ``period_headers`` is
        ``[(label, span), …]`` or empty when the table has one column per
        measure; ``lines`` is ``[(label_row, [(row or None, field), …]), …]``
        with one cell per printed column.
        """
        self.ensure_one()
        measures = (self.measures or '').split('|')
        if self.periods == 'current':
            periods = [('', 'current')]
        else:
            labels = (tuple(self.column_labels.split('|'))
                      if self.column_labels
                      else self.DEFAULT_LABELS.get(self.layout, ('', '')))
            periods = list(zip(labels, ('current', 'comparative')))
        lines = {}
        for row in self.row_ids.filtered(lambda r: r.printed):
            lines.setdefault(row.line or row.code, {})[row.measure] = row
        grid = []
        for cells in lines.values():
            label = cells.get(0) or cells[min(cells)]
            grid.append((label, [(cells.get(index), field)
                                 for _label, field in periods
                                 for index in range(len(measures))]))
        period_headers = ([(label, len(measures)) for label, _f in periods]
                          if self.periods != 'current' else [])
        return period_headers, measures * len(periods), grid

    def print_columns(self):
        """-> ((heading, field name), ...) in the order the form prints.

        For the equity table these are the printed rows, since the form
        turns the table on its side.
        """
        self.ensure_one()
        key = self.layout if self.layout != 'movement' else self.display
        labels = (tuple(self.column_labels.split('|')) if self.column_labels
                  else self.DEFAULT_LABELS.get(key, ()))
        fields_ = {
            'balance': ('current', 'comparative'),
            'period': ('current', 'comparative'),
            'standard': ('comparative', 'increase', 'decrease', 'current'),
            'tax': ('comparative', 'increase', 'decrease', 'current'),
            'loan': ('current', 'increase', 'decrease', 'comparative'),
            'equity': ('comparative', 'increase', 'decrease', 'current'),
        }.get(key, ())
        return tuple(zip(labels, fields_))


class VnFsNoteRow(models.Model):
    _name = 'vn.fs.note.row'
    _description = 'Notes to the Financial Statements: Row'
    _order = 'sequence, id'

    note_id = fields.Many2one('vn.fs.note', required=True,
                              ondelete='cascade', index=True)
    state = fields.Selection(related='note_id.state')
    item_id = fields.Many2one('vn.fs.note.item', required=True,
                              ondelete='cascade', index=True)
    template_row_id = fields.Many2one('vn.fs.note.template.row',
                                      required=True, ondelete='restrict')
    sequence = fields.Integer()
    code = fields.Char(related='template_row_id.code')
    name = fields.Char(related='template_row_id.name')
    style = fields.Selection(related='template_row_id.style')
    printed = fields.Boolean(related='template_row_id.printed')
    measure = fields.Integer(related='template_row_id.measure')
    line = fields.Char(related='template_row_id.line')
    indent = fields.Integer(related='template_row_id.indent')
    source = fields.Selection(related='template_row_id.source')
    source_note = fields.Char(related='template_row_id.source_note')
    currency_id = fields.Many2one(related='note_id.currency_id')
    current = fields.Monetary(
        help="Closing balance, or this year's figure.")
    comparative = fields.Monetary(
        help="Opening balance, or last year's figure.")
    increase = fields.Monetary()
    decrease = fields.Monetary()
    comparative_origin = fields.Selection(
        [('previous', "Last year's notes"),
         ('ledger', 'Read from the ledger'),
         ('none', 'None')],
        default='none', readonly=True,
        help="Where the comparative figure came from. The circular takes it "
             "from last year's notes; the ledger is the fallback when there "
             "are none.")
    manual = fields.Boolean(
        string='Edited',
        help="Figures typed in by hand. Recomputing keeps them; clear this "
             "to read the row from the ledger again.")

    def write(self, vals):
        self.note_id._check_editable()
        if not self.env.context.get('vn_fs_note_compute') \
                and set(vals) & set(VALUE_FIELDS) and 'manual' not in vals:
            if any(row.source in ('formula', 'previous') for row in self):
                raise UserError(_(
                    "A total is computed from the rows above it; change "
                    "those instead."))
            vals = dict(vals, manual=True)
        return super().write(vals)

    def action_reset(self):
        """Forget hand edits; the next computation reads the ledger again."""
        self.write({'manual': False})

    def _value_dto(self):
        self.ensure_one()
        return NoteRowValueDTO(
            code=self.code, current=self.current, opening=self.comparative,
            increase=self.increase, decrease=self.decrease)


class VnFsNoteCheck(models.Model):
    _name = 'vn.fs.note.check'
    _description = 'Notes to the Financial Statements: Check'
    _order = 'id'

    note_id = fields.Many2one('vn.fs.note', required=True,
                              ondelete='cascade', index=True)
    row_id = fields.Many2one('vn.fs.note.row', ondelete='cascade')
    name = fields.Char(required=True)
    currency_id = fields.Many2one(related='note_id.currency_id')
    expected = fields.Monetary()
    actual = fields.Monetary(string='In the notes')
    difference = fields.Monetary()
    state = fields.Selection(
        [('ok', 'Agrees'), ('mismatch', 'Differs'), ('info', 'To do'),
         ('skipped', 'Not checked')],
        required=True)
    message = fields.Char()
