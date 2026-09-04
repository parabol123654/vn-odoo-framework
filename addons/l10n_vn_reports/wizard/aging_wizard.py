# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Bảng tổng hợp công nợ theo tuổi nợ.

Deliberately not given a "Mẫu số": this is a management report, not one of the
books prescribed by Thông tư 200, and stamping a form number on it would claim
an official status it does not have.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.core.enums import AgingBasis
from odoo.addons.vn_core.services.general_ledger_service import (
    AgedPayableService, AgedReceivableService,
)


class VnAgingWizard(models.TransientModel):
    _name = 'vn.aging.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'Aged Receivable / Payable Report'

    # An aged balance is an as-at picture, never a period. The mixin makes
    # date_from required; relax it here and hide it in the form rather than
    # letting the user believe it narrows the report.
    date_from = fields.Date(required=False)

    aging_type = fields.Selection(
        [('receivable', 'Receivable (customers)'),
         ('payable', 'Payable (suppliers)')],
        string='Balance', default='receivable', required=True)
    basis = fields.Selection(
        [('due_date', 'Due date'),
         ('document_date', 'Document date')],
        string='Age from', default='due_date', required=True,
        help='Due date measures how late a payment is. Document date is used '
             'when contracts carry no payment term.')
    partner_ids = fields.Many2many(
        'res.partner', string='Partners',
        help='Leave empty to include every partner.')
    account_ids = fields.Many2many(
        'account.account', string='Accounts',
        domain=[('reconcile', '=', True)],
        help='Leave empty to use every receivable or payable account.')

    _INTERNAL_TYPE = {'receivable': 'receivable', 'payable': 'payable'}
    _BASIS = {'due_date': AgingBasis.DUE_DATE,
              'document_date': AgingBasis.DOCUMENT_DATE}

    # -- filter --------------------------------------------------------
    def _default_account_ids(self):
        """Resolved by account type, not by hardcoding 131 / 331."""
        self.ensure_one()
        accounts = self.env['account.account'].search([
            ('company_id', '=', self.company_id.id),
            ('internal_type', '=', self._INTERNAL_TYPE[self.aging_type]),
        ])
        if not accounts:
            raise UserError(_(
                "No %s account was found for %s. Check the chart of accounts."
            ) % (self._INTERNAL_TYPE[self.aging_type],
                 self.company_id.display_name))
        return tuple(accounts.ids)

    def _ledger_filter(self, **overrides):
        overrides.setdefault('partner_ids', tuple(self.partner_ids.ids))
        overrides.setdefault(
            'account_ids',
            tuple(self.account_ids.ids) or self._default_account_ids())
        # The engine ignores date_from for this report; passing None keeps the
        # intent visible instead of relying on that.
        overrides.setdefault('date_from', None)
        return super()._ledger_filter(**overrides)

    # -- hooks ---------------------------------------------------------
    def _service(self):
        return (AgedReceivableService(self.env)
                if self.aging_type == 'receivable'
                else AgedPayableService(self.env))

    def _build_report(self):
        self.ensure_one()
        result = self._service().generate(
            self._ledger_filter(), basis=self._BASIS[self.basis])
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data

    def _filter_summary_fields(self):
        return ('target_move', 'aging_type', 'basis', 'partner_ids', 'account_ids',
                'journal_ids')

    def _xlsx_layout(self):
        return 'aging'

    def _report_title(self):
        return (_('Aged Receivable') if self.aging_type == 'receivable'
                else _('Aged Payable'))

    def _report_form_title(self):
        return ('BẢNG TỔNG HỢP CÔNG NỢ PHẢI THU THEO TUỔI NỢ'
                if self.aging_type == 'receivable'
                else 'BẢNG TỔNG HỢP CÔNG NỢ PHẢI TRẢ THEO TUỔI NỢ')

    def _screen_template(self):
        return 'l10n_vn_reports.aging_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_reports.action_report_aging'
