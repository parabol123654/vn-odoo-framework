# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Sổ chi tiết thanh toán với người mua/người bán (mẫu S31-DN)."""

from odoo import _, fields, models

from odoo.addons.vn_core.services.general_ledger_service import (
    PartnerLedgerService,
)


class VnPartnerLedgerWizard(models.TransientModel):
    _name = 'vn.partner.ledger.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'Partner Ledger Report'

    partner_ids = fields.Many2many(
        'res.partner', string='Partners',
        help='Leave empty to include every partner.')
    account_ids = fields.Many2many(
        'account.account', string='Accounts',
        domain=[('reconcile', '=', True)],
        help='Leave empty to use every receivable and payable account.')
    partner_type = fields.Selection(
        [('customer', 'Customers (receivable)'),
         ('supplier', 'Suppliers (payable)'),
         ('both', 'Both')],
        string='Show', default='customer', required=True)

    # -- filter --------------------------------------------------------
    def _default_account_ids(self):
        """Receivable / payable accounts of the company, by account type.

        Resolved through ``account.account.type`` rather than by hardcoding 131
        and 331, so a chart that splits them into sub-accounts still works.
        """
        self.ensure_one()
        types = []
        if self.partner_type in ('customer', 'both'):
            types.append('receivable')
        if self.partner_type in ('supplier', 'both'):
            types.append('payable')
        accounts = self.env['account.account'].search([
            ('company_id', '=', self.company_id.id),
            ('internal_type', 'in', types),
        ])
        return tuple(accounts.ids)

    def _ledger_filter(self, **overrides):
        overrides.setdefault('partner_ids', tuple(self.partner_ids.ids))
        overrides.setdefault(
            'account_ids',
            tuple(self.account_ids.ids) or self._default_account_ids())
        return super()._ledger_filter(**overrides)

    # -- hooks ---------------------------------------------------------
    def _service(self):
        return PartnerLedgerService(self.env)

    def _filter_summary_fields(self):
        return ('target_move', 'partner_type', 'partner_ids', 'account_ids', 'journal_ids')

    def _xlsx_layout(self):
        return 'ledger'

    def _report_title(self):
        return _('Partner Ledger')

    def _report_form_code(self):
        return 'S31-DN'

    def _report_form_title(self):
        return 'SỔ CHI TIẾT THANH TOÁN VỚI NGƯỜI MUA (NGƯỜI BÁN)'

    def _screen_template(self):
        return 'l10n_vn_reports.partner_ledger_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_reports.action_report_partner_ledger'
