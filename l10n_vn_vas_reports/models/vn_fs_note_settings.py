# -*- coding: utf-8 -*-
# Target: Odoo 16.0 Community Edition
"""What a company decides about its notes (B09), on its own form.

The circulars leave two kinds of question open that have no single answer:

* **Which of its own accounts** feed a row. A table breaks a statement line
  down ("Giá vốn của hàng hóa đã bán", "Tương đương tiền", "Các khoản phải
  nộp theo lương"), and whether that is readable from the ledger depends on
  the sub-accounts the company opened. Such rows are *configurable*: the
  company names the accounts, the row then reads them like any ledger row.
* **Its own policies and data**: which partners are related parties, after
  how many days a debt counts as overdue, whether loans are split by their
  due dates, whether empty tables are printed.

Questions of interpretation the law answers once for everybody are not
here: they are the template's defaults.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.domain.financial_statement.formula import (
    FormulaEvaluator,
)

#: Rows a company setting can fill in, by (circular, item reference, row
#: code). 'copy' reads like that row of the same table, plus the changes
#: given; otherwise the row reads the expression given.
AUTO_ROWS = {
    # -- TT133 B09-DNN ------------------------------------------------------
    ('TT133', 'V.3', 'a1'): {'kind': 'related', 'copy': 'a'},
    ('TT133', 'V.3', 'b1'): {'kind': 'related', 'copy': 'b'},
    ('TT133', 'V.3', 'e'): {'kind': 'overdue', 'expression': '131*',
                            'side': 'debit_only', 'split': True},
    ('TT133', 'V.9', 'a1'): {'kind': 'related', 'copy': 'a'},
    ('TT133', 'V.9', 'b1'): {'kind': 'related', 'copy': 'b'},
    ('TT133', 'V.9', 'd'): {'kind': 'overdue', 'expression': '331*',
                            'sign': -1, 'side': 'credit_only', 'split': True},
    ('TT133', 'V.11', 'a'): {'kind': 'loan', 'expression': '3411*',
                             'sign': -1, 'maturity': 'short'},
    ('TT133', 'V.11', 'b'): {'kind': 'loan', 'expression': '3411*',
                             'sign': -1, 'maturity': 'long'},
    ('TT133', 'V.11', 'a1'): {'kind': 'related', 'copy': 'a'},
    ('TT133', 'V.11', 'b1'): {'kind': 'related', 'copy': 'b'},
    ('TT133', 'V.11', 'c1'): {'kind': 'related', 'copy': 'c'},
    ('TT133', 'VI.1', 'b'): {'kind': 'related', 'expression': '511*',
                             'sign': -1, 'movement_side': 'credit'},
    # -- TT99 B09-DN --------------------------------------------------------
    ('TT99', 'V.3', 'c'): {'kind': 'related', 'expression': '131*',
                           'side': 'debit_only', 'split': True},
    ('TT99', 'V.6', 'a_cost'): {'kind': 'overdue', 'expression': '131*',
                                'side': 'debit_only', 'split': True},
    ('TT99', 'V.16', 'c'): {'kind': 'related', 'copy': 'a',
                            'maturity': 'all'},
    ('TT99', 'V.17', 'd'): {'kind': 'related', 'expression': '331*',
                            'sign': -1, 'side': 'credit_only',
                            'split': True},
    ('TT99', 'VII.1', 'related'): {'kind': 'related', 'expression': '511*',
                                   'sign': -1, 'movement_side': 'credit'},
    # -- TT200 B09-DN -------------------------------------------------------
    ('TT200', 'VI.3', 'c'): {'kind': 'related', 'expression': '131*',
                             'side': 'debit_only', 'split': True},
    ('TT200', 'VI.6', 'a_cost'): {'kind': 'overdue', 'expression': '131*',
                                  'side': 'debit_only', 'split': True},
    ('TT200', 'VI.16', 'rp'): {'kind': 'related', 'expression': '331*',
                               'sign': -1, 'side': 'credit_only',
                               'split': True},
    ('TT200', 'VII.1', 'related'): {'kind': 'related', 'expression': '511*',
                                    'sign': -1, 'movement_side': 'credit'},
}

#: The note a row's source note carries when its accounts are a default an
#: accountant should confirm; such a ledger row is configurable.
CONFIRM_MARK = 'Cần kế toán xác nhận'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    vn_related_party = fields.Boolean(
        string='Related party',
        help="A related party as the notes to the financial statements "
             "present them (VAS 26). The notes can add up the balances and "
             "revenue of these partners in their \"of which: related "
             "parties\" rows.")


class ResCompany(models.Model):
    _inherit = 'res.company'

    vn_fs_note_related_auto = fields.Boolean(
        string='Compute related-party rows',
        help="Fill the notes' \"of which: related parties\" rows from the "
             "ledger, for the partners marked as related parties. Off: those "
             "rows are typed in by hand.")
    vn_fs_note_overdue_days = fields.Integer(
        string='Overdue after (days)',
        help="Fill the notes' overdue and bad-debt rows from the due dates "
             "of the journal items: an amount counts as overdue once its due "
             "date is more than this many days before the year end. 0: those "
             "rows are typed in by hand.")
    vn_fs_note_loan_split = fields.Boolean(
        string='Split loans by due date',
        help="Split loans into short and long term by the due dates of the "
             "journal items, as the balance sheet does. Off: typed in by "
             "hand. Used where the circular's chart has one loan account "
             "(TT133 V.11).")
    vn_fs_note_hide_zero = fields.Boolean(
        string='Leave out empty items when printing',
        help="Do not print a table whose figures are all zero, nor a text "
             "item with nothing written. TT133 Điều 72 khoản 6 and TT99 "
             "Điều 17 khoản 4 let a company leave out items with no "
             "figures.")
    vn_fs_note_config_ids = fields.One2many(
        'vn.fs.note.row.config', 'company_id', string='Accounts for notes rows')

    def action_vn_fs_note_load_rows(self):
        """List every configurable row of the company's notes form."""
        self.ensure_one()
        template = self.env['vn.fs.note.template'].default_for(self)
        have = set(self.vn_fs_note_config_ids.mapped('template_row_id').ids)
        rows = self.env['vn.fs.note.template.row'].search([
            ('item_id.template_id', '=', template.id),
            ('configurable', '=', True), ('id', 'not in', list(have))])
        self.env['vn.fs.note.row.config'].create([{
            'company_id': self.id,
            'template_row_id': row.id,
            'expression': row.expression if row.source == 'ledger' else '',
        } for row in rows])
        return True


class VnFsNoteRowConfig(models.Model):
    _name = 'vn.fs.note.row.config'
    _description = 'Notes to the Financial Statements: Company Accounts for a Row'
    _order = 'template_id, item_sequence, row_sequence, id'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', required=True, index=True,
                                 ondelete='cascade',
                                 default=lambda self: self.env.company)
    template_row_id = fields.Many2one(
        'vn.fs.note.template.row', string='Row', required=True,
        ondelete='cascade', domain=[('configurable', '=', True)])
    template_id = fields.Many2one(
        related='template_row_id.item_id.template_id', store=True,
        string='Form')
    item_reference = fields.Char(related='template_row_id.item_id.reference',
                                 string='Item')
    item_sequence = fields.Integer(related='template_row_id.item_id.sequence',
                                   store=True)
    row_sequence = fields.Integer(related='template_row_id.sequence',
                                  store=True)
    row_name = fields.Char(related='template_row_id.name', string='Row label')
    default_expression = fields.Char(
        related='template_row_id.expression', string='Default accounts')
    source_note = fields.Char(related='template_row_id.source_note')
    expression = fields.Char(
        string='Accounts',
        help="The company's accounts for this row, as an account expression: "
             "6321*\\,6322* or 1281*\\,-12811*. Empty: the row keeps its "
             "default (typed in by hand, or the default accounts).")
    sign = fields.Selection(
        [('1', 'As read (debit positive)'), ('-1', 'Reversed (credit positive)')],
        help="Leave empty to read like the total the row breaks down.")
    movement_side = fields.Selection(
        [('net', 'Net movement'), ('debit', 'Debit movement'),
         ('credit', 'Credit movement')],
        help="For a figure of the year. Leave empty to read like the total "
             "the row breaks down.")

    _sql_constraints = [
        ('company_row_uniq',
         'unique(company_id, template_row_id)',
         'A row is configured once per company.'),
    ]

    @api.constrains('expression')
    def _check_expression(self):
        from odoo.addons.vn_core.domain.financial_statement.expression import (
            AccountExpression,
        )
        from odoo.addons.vn_core.core.exceptions import MappingException
        for config in self.filtered('expression'):
            try:
                AccountExpression.parse(config.expression)
            except MappingException as error:
                raise UserError(_("Row %(row)s: %(error)s")
                                % {'row': config.row_name, 'error': error})


class VnFsNoteTemplateRow(models.Model):
    _inherit = 'vn.fs.note.template.row'

    configurable = fields.Boolean(
        compute='_compute_company_settings', store=True,
        help="The company can name its own accounts for this row (Settings "
             "→ company → Notes to the financial statements). Set for rows "
             "that break a statement line down where the circular gives no "
             "account, and for default accounts an accountant should "
             "confirm.")
    auto_kind = fields.Selection(
        [('related', 'Related parties'), ('overdue', 'Overdue'),
         ('loan', 'Loans by due date')],
        compute='_compute_company_settings', store=True,
        help="A company setting can fill this row from the ledger.")
    value_kind = fields.Selection(
        [('money', 'Amount'), ('percent', 'Rate'), ('quantity', 'Quantity')],
        compute='_compute_value_kind', store=True,
        help="How the figure prints: an amount in the company's currency, a "
             "rate in %, or a plain number (shares, years).")

    @api.depends('code', 'source', 'expression', 'formula', 'detail_formula',
                 'statement_check', 'source_note', 'style',
                 'item_id.reference', 'item_id.template_id.version',
                 'item_id.row_ids.formula', 'item_id.row_ids.detail_formula',
                 'item_id.row_ids.statement_check')
    def _compute_company_settings(self):
        for row in self:
            key = ((row.item_id.template_id.version or '').upper(),
                   row.item_id.reference, row.code)
            auto = AUTO_ROWS.get(key)
            row.auto_kind = auto['kind'] if auto else False
            row.configurable = (not auto) and row._is_breakdown()

    def _is_breakdown(self):
        """A row the company may need to point at its own accounts."""
        self.ensure_one()
        if self.style == 'heading' or self.source in ('formula', 'previous'):
            return False
        if self.source == 'ledger':
            return CONFIRM_MARK in (self.source_note or '')
        for sibling in self.item_id.row_ids:
            if sibling == self:
                continue
            if sibling.detail_formula and self.code in \
                    FormulaEvaluator.referenced_codes(sibling.detail_formula):
                return True
            if sibling.source == 'formula' and sibling.statement_check \
                    and sibling.formula and self.code in \
                    FormulaEvaluator.referenced_codes(sibling.formula):
                return True
        return False

    @api.depends('name', 'measure', 'item_id.measures')
    def _compute_value_kind(self):
        for row in self:
            measures = (row.item_id.measures or '').split('|')
            label = (measures[row.measure].strip()
                     if row.item_id.measures and row.measure < len(measures)
                     else '')
            name = (row.name or '').lstrip('-+ ').lower()
            if 'suất' in label.lower() or name.startswith('thuế suất') \
                    or name.startswith('lãi suất'):
                row.value_kind = 'percent'
            elif label in ('Số lượng', 'Kỳ hạn') \
                    or name.startswith('số lượng'):
                row.value_kind = 'quantity'
            else:
                row.value_kind = 'money'
