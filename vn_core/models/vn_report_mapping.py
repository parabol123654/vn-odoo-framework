# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Configurable statement mapping (Part 9 §5-6).

The whole point of these two models is that a change of circular — TT200 to
TT133, or an amendment to either — is a change of *data*, not of Python. No
account code appears anywhere in the framework's source.

They live in ``vn_core`` rather than in a localisation module because nothing
about them is Vietnamese: a mapping from account codes to statement lines is
what every jurisdiction needs. The TT200 rows themselves ship in
``l10n_vn_vas_reports``.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError


class VnReportMapping(models.Model):
    _name = 'vn.report.mapping'
    _description = 'Financial Statement Mapping'
    _order = 'report_type, code'

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True, translate=True)
    report_type = fields.Selection(
        [('balance_sheet', 'Balance Sheet'),
         ('income_statement', 'Income Statement'),
         ('cash_flow', 'Cash Flow Statement')],
        required=True, default='income_statement')
    basis = fields.Selection(
        [('closing', 'Closing balance'),
         ('movement', 'Movement in the period')],
        required=True, default='movement',
        help="A balance sheet reads closing balances; a profit and loss "
             "statement reads the movement of the period. This belongs to the "
             "mapping, not to the engine.")
    version = fields.Char(
        default='TT200', required=True,
        help="Which circular this set of items comes from. A company reports "
             "under one circular, and the reports pick the matching mapping "
             "from here rather than from a hardcoded name.")
    company_id = fields.Many2one(
        'res.company',
        help="Leave empty to make the mapping available to every company.")
    balance_check = fields.Char(
        help="Equality the finished statement must satisfy, written as two "
             "item codes, e.g. 270=440 for a balance sheet. Leave empty when "
             "the form has no such identity.")
    cash_flow_method = fields.Selection(
        [('direct', 'Trực tiếp'), ('indirect', 'Gián tiếp')],
        string='Cash flow method', default='direct',
        help="Which method this cash flow form uses. The direct method reads "
             "journal entries and classifies each cash movement by its "
             "counterpart; the indirect one starts from profit and adjusts it "
             "with balance movements. Ignored by the other statements.")
    cash_expression = fields.Char(
        string='Cash accounts',
        help="Which accounts count as cash on a cash flow statement, written "
             "as an account expression such as 111*,112*,113*. Ignored by the "
             "other statements.")
    active = fields.Boolean(default=True)
    line_ids = fields.One2many('vn.report.mapping.line', 'mapping_id',
                               string='Lines')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'A mapping code must be unique per company.'),
    ]

    @api.model
    def default_for(self, report_type, company):
        """The mapping a company should use for a kind of statement.

        Resolved from the company's circular rather than from a name baked into
        a wizard. That is the whole point of keeping statements as mapping data:
        a small enterprise on Thông tư 133 and a larger one on Thông tư 200 run
        the same engine over different rows, and neither needs a code change.

        A company-specific mapping wins over a shared one, so a client can amend
        a form for itself without losing the shipped version.
        """
        circular = (company.vn_accounting_circular or 'TT200').upper()
        mapping = self.search([
            ('report_type', '=', report_type),
            ('version', '=ilike', circular),
            '|', ('company_id', '=', False), ('company_id', '=', company.id),
        ], order='company_id desc', limit=1)
        if not mapping:
            raise UserError(_(
                "No %(report)s mapping found for %(circular)s. Check "
                "Accounting > Configuration > Statement Mappings."
            ) % {'report': report_type, 'circular': circular})
        return mapping


class VnReportMappingLine(models.Model):
    _name = 'vn.report.mapping.line'
    _description = 'Financial Statement Mapping Line'
    _order = 'sequence, code'

    mapping_id = fields.Many2one('vn.report.mapping', required=True,
                                 ondelete='cascade', index=True)
    code = fields.Char(string='Mã số', required=True,
                       help="The item code printed on the statutory form.")
    name = fields.Char(string='Chỉ tiêu', required=True, translate=True)
    sequence = fields.Integer(default=10)
    level = fields.Integer(default=0, help="Indentation depth when printed.")
    parent_id = fields.Many2one('vn.report.mapping.line', string='Parent',
                                ondelete='set null')
    note_ref = fields.Char(string='Thuyết minh')

    expression = fields.Char(
        string='Account expression',
        help="Selects accounts by code: 111*, 111*\\,112*, 111*\\,-1113. "
             "Leave empty for a heading or a computed line.")
    formula = fields.Char(
        help="References other item codes, never accounts: 10 - 11. "
             "A line has either an expression or a formula, not both.")
    sign = fields.Integer(
        default=1, required=True,
        help="Use -1 for accounts that carry a credit balance, such as "
             "revenue, so the statement prints a positive figure.")
    side = fields.Selection(
        [('both', 'Net balance'),
         ('debit_only', 'Debit side only'),
         ('credit_only', 'Credit side only')],
        default='both', required=True,
        help="A Vietnamese balance sheet splits account 131 into a receivable "
             "and a customer prepayment. Combine with 'Split by partner'.")
    split_by_partner = fields.Boolean(
        help="Evaluate the side per partner before summing. Required for "
             "items 131 and 331: netting the account first cancels a customer "
             "who owes against one who has prepaid, and both items come out "
             "too small.")
    visible = fields.Boolean(default=True)
    bold = fields.Boolean(help="Printed in bold, for totals and headings.")

    @api.constrains('expression', 'formula')
    def _check_source(self):
        for line in self:
            if line.expression and line.formula:
                raise ValidationError(_(
                    "Line %s has both an account expression and a formula. "
                    "It must have one or the other.") % line.code)

    @api.constrains('sign')
    def _check_sign(self):
        for line in self:
            if line.sign not in (1, -1):
                raise ValidationError(_("Sign must be 1 or -1."))


class ResCompany(models.Model):
    _inherit = 'res.company'

    vn_accounting_circular = fields.Selection(
        [('TT200', 'Thông tư 200/2014/TT-BTC'),
         ('TT133', 'Thông tư 133/2016/TT-BTC')],
        string='Accounting circular', default='TT200', required=True,
        help="Which circular this company reports under. Thông tư 133 applies "
             "to small and medium enterprises and uses different statement "
             "forms; the reports follow this setting.")
