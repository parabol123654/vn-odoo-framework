# -*- coding: utf-8 -*-
# Target: Odoo 20.0 Community Edition
"""Sổ chi tiết thanh toán với người mua (người bán) bằng ngoại tệ (S32-DN)."""

from odoo import _, fields, models

from odoo.addons.vn_core.services.general_ledger_service import (
    CurrencyLedgerService,
)


class VnCurrencyLedgerWizard(models.TransientModel):
    _name = 'vn.currency.ledger.wizard'
    _inherit = 'vn.partner.ledger.wizard'
    _description = 'Foreign Currency Partner Ledger'

    foreign_currency_id = fields.Many2one(
        'res.currency', string='Foreign currency', required=True)

    def _ledger_filter(self, **overrides):
        overrides.setdefault('currency_id', self.foreign_currency_id.id)
        return super()._ledger_filter(**overrides)

    def _service(self):
        return CurrencyLedgerService(self.env)

    def _filter_summary_fields(self):
        return ('foreign_currency_id',) + super()._filter_summary_fields()

    def _report_title(self):
        return _('Foreign Currency Partner Ledger')

    def _report_form_code(self):
        # TT133 books foreign-currency payments on another form (S14-DNN).
        return self._by_circular({'TT200': 'S32-DN', 'TT99': 'S32-DN',
                                  'TT133': ''})

    def _report_form_title(self):
        return 'SỔ CHI TIẾT THANH TOÁN VỚI NGƯỜI MUA (NGƯỜI BÁN) BẰNG NGOẠI TỆ'

    def _form_preparer(self):
        return self._book_preparer()

    def _template_values(self, report):
        values = super()._template_values(report)
        values['foreign_currency'] = self.foreign_currency_id
        return values

    def _screen_template(self):
        return 'l10n_vn_vas_reports.currency_ledger_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_vas_reports.action_report_currency_ledger'
