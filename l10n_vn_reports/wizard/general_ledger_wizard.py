# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Sổ Cái / Sổ chi tiết tài khoản wizard."""

from odoo import _, fields, models

from odoo.addons.vn_core.core.enums import GroupBy
from odoo.addons.vn_core.services.general_ledger_service import (
    GeneralLedgerService,
)


class VnGeneralLedgerWizard(models.TransientModel):
    _name = 'vn.general.ledger.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'General Ledger Report'

    account_ids = fields.Many2many(
        'account.account', string='Accounts',
        help='Leave empty to include every account.')
    partner_ids = fields.Many2many(
        'res.partner', string='Partners',
        help='Leave empty to include every partner.')
    group_by = fields.Selection(
        [('account', 'Account'),
         ('partner', 'Partner'),
         ('account_partner', 'Account, then partner'),
         ('journal', 'Journal')],
        string='Group by', default='account', required=True)
    show_counterpart = fields.Boolean(
        string='Show counterpart accounts', default=True,
        help='Fills the "TK đối ứng" column of the statutory form.')

    _GROUP_BY = {
        'account': GroupBy.ACCOUNT,
        'partner': GroupBy.PARTNER,
        'account_partner': GroupBy.ACCOUNT_PARTNER,
        'journal': GroupBy.JOURNAL,
    }

    # -- filter --------------------------------------------------------
    def _ledger_filter(self, **overrides):
        overrides.setdefault('account_ids', tuple(self.account_ids.ids))
        overrides.setdefault('partner_ids', tuple(self.partner_ids.ids))
        return super()._ledger_filter(**overrides)

    # -- hooks ---------------------------------------------------------
    def _service(self):
        return GeneralLedgerService(self.env)

    def _filter_summary_fields(self):
        return ('target_move', 'group_by', 'journal_ids', 'account_ids',
                'partner_ids', 'analytic_account_ids')

    def _xlsx_layout(self):
        return 'ledger'

    def _report_title(self):
        return _('General Ledger')

    def _report_form_code(self):
        return 'S03b-DN'

    def _report_form_title(self):
        return 'SỔ CÁI'

    def _screen_template(self):
        return 'l10n_vn_reports.general_ledger_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_reports.action_report_general_ledger'

    def _build_report(self):
        self.ensure_one()
        result = self._service().generate(
            self._ledger_filter(),
            group_by=self._GROUP_BY[self.group_by],
            with_counterpart=self.show_counterpart)
        if not result.success:
            from odoo.exceptions import UserError
            raise UserError('\n'.join(result.errors))
        return result.data
