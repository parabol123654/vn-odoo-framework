# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""QWeb report adapters.

These exist only to hand the wizard's DTO to the template. No queries, no
calculations — Part 7 §2.
"""

from odoo import models


class VnQwebReportMixin(models.AbstractModel):
    _name = 'report.vn.qweb.mixin'
    _description = 'Vietnam QWeb Report Mixin'

    #: Wizard model whose id arrives in ``docids``.
    _wizard_model = None

    def _get_report_values(self, docids, data=None):
        wizard = self.env[self._wizard_model].browse(docids)
        wizard.ensure_one()
        values = wizard._template_values(wizard._build_report())
        values.update({
            'doc_ids': docids,
            'doc_model': wizard._name,
            'docs': wizard,
        })
        return values


class VnGeneralLedgerQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_general_ledger'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'General Ledger QWeb Report'
    _wizard_model = 'vn.general.ledger.wizard'


class VnTrialBalanceQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_trial_balance'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'Trial Balance QWeb Report'
    _wizard_model = 'vn.trial.balance.wizard'


class VnGeneralJournalQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_general_journal'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'General Journal QWeb Report'
    _wizard_model = 'vn.general.journal.wizard'


class VnExpenseLedgerQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_expense_ledger'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'Expense Ledger QWeb Report'
    _wizard_model = 'vn.expense.ledger.wizard'


class VnSalesLedgerQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_sales_ledger'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'Sales Ledger QWeb Report'
    _wizard_model = 'vn.sales.ledger.wizard'


class VnMaterialAllocationQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_material_allocation'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'Material Allocation QWeb Report'
    _wizard_model = 'vn.material.allocation.wizard'


class VnPartnerLedgerQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_partner_ledger'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'Partner Ledger QWeb Report'
    _wizard_model = 'vn.partner.ledger.wizard'


class VnCashBookQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_cash_book'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'Cash / Bank Book QWeb Report'
    _wizard_model = 'vn.cash.book.wizard'


class VnAgingQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_aging'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'Aged Receivable / Payable QWeb Report'
    _wizard_model = 'vn.aging.wizard'


class VnIncomeStatementQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_income_statement'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'Income Statement QWeb Report'
    _wizard_model = 'vn.income.statement.wizard'


class VnVatListingQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_vat_listing'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'VAT Invoice Listing QWeb Report'
    _wizard_model = 'vn.vat.listing.wizard'


class VnBalanceSheetQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_balance_sheet'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'Balance Sheet QWeb Report'
    _wizard_model = 'vn.balance.sheet.wizard'


class VnCashFlowQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_cash_flow'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'Cash Flow Statement QWeb Report'
    _wizard_model = 'vn.cash.flow.wizard'


class VnVatDeclarationQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_vas_reports.report_vat_declaration'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'VAT Declaration QWeb Report'
    _wizard_model = 'vn.vat.declaration.wizard'
