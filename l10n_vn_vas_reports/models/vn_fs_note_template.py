# -*- coding: utf-8 -*-
# Target: Odoo 20.0 Community Edition
"""The structure of a circular's notes to the financial statements (B09).

A template is data, like a statement mapping: sections and items in the
circular's order, the text each item starts with, and for the numeric tables
the rows and how each one reads the ledger. A company's notes for a year
(``vn.fs.note``) are built from it and then edited.

The tables read the ledger with the same vocabulary as a mapping line
(expression, sign, side, split by partner, movement side), so a row and the
statement line it explains are computed the same way.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

LAYOUTS = [
    ('balance', 'End of year / Start of year'),
    ('period', 'This year / Last year'),
    ('movement', 'Opening, increase, decrease, closing'),
]

#: How a 'movement' table is laid out on paper. The figures are the same; the
#: forms order and label the columns differently.
DISPLAYS = [
    ('standard', 'Opening, increase, decrease, closing'),
    ('tax', 'Opening, payable, paid, closing'),
    ('loan', 'Closing, increase, decrease, opening'),
    ('equity', 'Rows become columns (equity reconciliation)'),
]


class VnFsNoteTemplate(models.Model):
    _name = 'vn.fs.note.template'
    _description = 'Notes to the Financial Statements: Template'
    _order = 'version, sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    version = fields.Char(
        string='Circular', required=True,
        help="Which circular the template follows: TT133, TT99 or TT200. A "
             "company's notes use the template of its circular.")
    form_code = fields.Char(string='Form number', required=True,
                            help="Printed top right, e.g. B09-DNN.")
    form_title = fields.Char(string='Form heading', required=True)
    form_subtitle = fields.Char(
        string='Form subtitle',
        help="The line under the heading, e.g. \"(Áp dụng cho doanh nghiệp "
             "đáp ứng giả định hoạt động liên tục)\".")
    footnote = fields.Text(
        help="The form's own footnote, printed under the signatures.")
    closing_expression = fields.Char(
        string='Year-end transfer accounts', default='911*,421*',
        help="Journal entries touching these accounts are left out of the "
             "'This year / Last year' tables, as they are left out of the "
             "income statement.")
    company_id = fields.Many2one(
        'res.company',
        help="Leave empty to make the template available to every company. "
             "A company-specific copy wins over the shared one.")
    active = fields.Boolean(default=True)
    item_ids = fields.One2many('vn.fs.note.template.item', 'template_id',
                               string='Items', copy=True)

    @api.model
    def default_for(self, company):
        """The template of the company's circular; its own copy first."""
        circular = (company.vn_accounting_circular or 'TT200').upper()
        template = self.search([
            ('version', '=ilike', circular),
            '|', ('company_id', '=', False), ('company_id', '=', company.id),
        ], order='company_id desc, sequence, id', limit=1)
        if not template:
            raise UserError(_(
                "No template for the notes to the financial statements under "
                "%s. The module ships one for Thông tư 133/2016.") % circular)
        return template


class VnFsNoteTemplateItem(models.Model):
    _name = 'vn.fs.note.template.item'
    _description = 'Notes to the Financial Statements: Template Item'
    _order = 'sequence, id'

    template_id = fields.Many2one('vn.fs.note.template', required=True,
                                  ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    number = fields.Char(
        help="The number printed before the title, e.g. V or 1 or a). The "
             "circular lets a company renumber its notes.")
    reference = fields.Char(
        help="Short reference used by the statements' \"Thuyết minh\" column, "
             "e.g. V.1. Leave empty when nothing on the statements points "
             "here.")
    name = fields.Char(string='Title', required=True)
    level = fields.Integer(
        default=1, help="0 for a section (I, II, …), 1 for an item, 2 below.")
    kind = fields.Selection(
        [('heading', 'Heading only'),
         ('text', 'Text'),
         ('table', 'Table')],
        required=True, default='text')
    default_text = fields.Html(
        sanitize=True,
        help="What the item says in a company's first notes. Later years "
             "start from the previous year's text. May use {date_from}, "
             "{date_to} and {currency}.")
    guidance = fields.Text(
        help="What the circular asks for here, shown to whoever writes the "
             "notes. Not printed.")
    show_unit = fields.Boolean(
        help="Print \"Đơn vị tính\" under this heading. The forms print it "
             "at the start of the balance sheet and income statement parts.")
    layout = fields.Selection(LAYOUTS, help="Columns of a table.")
    display = fields.Selection(DISPLAYS, default='standard')
    column_labels = fields.Char(
        help="Column headings exactly as the form prints them, separated by "
             "|, e.g. Số đầu năm|Tăng trong năm|Giảm trong năm|Số cuối năm. "
             "Leave empty for the usual headings of the layout.")
    row_ids = fields.One2many('vn.fs.note.template.row', 'item_id',
                              string='Rows', copy=True)

    @api.constrains('kind', 'layout')
    def _check_layout(self):
        for item in self:
            if item.kind == 'table' and not item.layout:
                raise ValidationError(_(
                    "Table %s needs a layout.") % item.name)


class VnFsNoteTemplateRow(models.Model):
    _name = 'vn.fs.note.template.row'
    _description = 'Notes to the Financial Statements: Template Row'
    _order = 'sequence, id'

    item_id = fields.Many2one('vn.fs.note.template.item', required=True,
                              ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    code = fields.Char(
        required=True,
        help="Identifies the row within its table, in formulas and from one "
             "year's notes to the next. Letters, digits and _ only.")
    name = fields.Char(required=True)
    style = fields.Selection(
        [('normal', 'Normal'),
         ('bold', 'Bold'),
         ('italic', 'Italic'),
         ('heading', 'Heading, no figures')],
        default='normal', required=True)
    indent = fields.Integer(default=0)
    source = fields.Selection(
        [('ledger', 'From the ledger'),
         ('formula', 'Formula'),
         ('manual', 'Filled in by hand')],
        default='manual', required=True)
    expression = fields.Char(string='Account expression')
    formula = fields.Char(help="Other row codes of the table: a + b - c.")
    sign = fields.Integer(
        default=1, required=True,
        help="-1 for rows that carry a credit balance (liabilities, equity, "
             "revenue, accumulated depreciation). In an opening, increase, "
             "decrease, closing table it also decides which side is the "
             "increase.")
    side = fields.Selection(
        [('both', 'Net balance'),
         ('debit_only', 'Debit side only'),
         ('credit_only', 'Credit side only')],
        default='both', required=True)
    split_by_partner = fields.Boolean()
    movement_side = fields.Selection(
        [('net', 'Net movement'),
         ('debit', 'Debit movement'),
         ('credit', 'Credit movement')],
        default='net', required=True)
    printed = fields.Boolean(
        default=True,
        help="Clear for a total the form does not print but the checks need, "
             "such as the total of B09-DNN V.2 b) against B01a-DNN item 122.")
    statement_check = fields.Char(
        help="The statement line this row must agree with, as form number "
             "and item code: B01a-DNN:110. Put a minus before the code to "
             "compare with the opposite figure, for an item the statement "
             "prints negative (B01a-DNN:-152, accumulated depreciation). "
             "Checked when the notes are computed; skipped when the company "
             "presents another form.")
    detail_formula = fields.Char(
        help="Rows that break this one down, as a formula: a + b + c. Once "
             "any of them is filled in, their total must equal this row.")
    source_note = fields.Char(
        help="Where the figure comes from, as the circular or the "
             "specification states it. Shown to the user, not printed.")

    @api.constrains('source', 'expression', 'formula')
    def _check_source(self):
        for row in self:
            if row.source == 'ledger' and not row.expression:
                raise ValidationError(_(
                    "Row %s reads the ledger but has no account "
                    "expression.") % row.code)
            if row.source == 'formula' and not row.formula:
                raise ValidationError(_(
                    "Row %s is a formula but has none.") % row.code)

    @api.constrains('sign')
    def _check_sign(self):
        for row in self:
            if row.sign not in (1, -1):
                raise ValidationError(_("Sign must be 1 or -1."))
