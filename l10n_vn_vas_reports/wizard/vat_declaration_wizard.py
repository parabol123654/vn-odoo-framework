# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Tờ khai thuế giá trị gia tăng, mẫu 01/GTGT."""

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.dto.tax import VatDeclarationInputDTO
from odoo.addons.vn_core.services.general_ledger_service import (
    VatDeclarationService,
)


class VnVatDeclarationWizard(models.TransientModel):
    _name = 'vn.vat.declaration.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'VAT Declaration (01/GTGT)'

    # Figures the ledger cannot supply. Asking for them is more honest than
    # defaulting them to zero and letting the form look complete.
    carried_forward = fields.Monetary(
        string='Credit carried forward (22)',
        help='Item 43 of the previous period. This framework does not store '
             'past declarations, so it cannot be derived.')
    adjustment_decrease = fields.Monetary(string='Adjustment decrease (37)')
    adjustment_increase = fields.Monetary(string='Adjustment increase (38)')
    refund_claimed = fields.Monetary(string='Refund claimed (42)')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    def _declaration_inputs(self):
        self.ensure_one()
        return VatDeclarationInputDTO(
            carried_forward=self.carried_forward,
            adjustment_decrease=self.adjustment_decrease,
            adjustment_increase=self.adjustment_increase,
            refund_claimed=self.refund_claimed,
        )

    def _service(self):
        return VatDeclarationService(self.env)

    def _build_report(self):
        self.ensure_one()
        if not self.date_from:
            raise UserError(_(
                "A VAT declaration covers a period, so a start date is "
                "required."))
        result = self._service().generate(
            self._ledger_filter(), inputs=self._declaration_inputs())
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data

    def _filter_summary_fields(self):
        return ('target_move', 'journal_ids')

    def _report_title(self):
        return _('VAT Declaration')

    def _report_form_code(self):
        return '01/GTGT'

    def _report_form_title(self):
        return 'TỜ KHAI THUẾ GIÁ TRỊ GIA TĂNG'

    def _screen_template(self):
        return 'l10n_vn_vas_reports.vat_declaration_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_vas_reports.action_report_vat_declaration'
