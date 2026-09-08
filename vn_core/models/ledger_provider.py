# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""Domain provider (extension point).

The Domain is pure Python and therefore has no ``_inherit``. This model is the
seam that restores the Open/Closed behaviour the framework promises: a customer
module inherits ``vn.ledger.provider`` and overrides ``ledger_engine_class`` to
return its own subclass, without touching framework code.

An import-time Python registry would not do: a global dict populated when a
module is imported is shared by every database served by the same worker
process, so a customer module installed on one database would leak into another.
Resolution through an Odoo model is per-database by construction.
"""

from odoo import models

from ..domain.cash_flow.engine import CashFlowEngine
from ..domain.financial_statement.engine import FinancialStatementEngine
from ..domain.ledger.engine import LedgerEngine
from ..domain.tax.declaration import VatDeclarationEngine
from ..domain.tax.engine import TaxEngine
from ..infrastructure.odoo_ledger_repository import OdooLedgerRepository
from ..infrastructure.odoo_mapping_repository import OdooMappingRepository
from ..infrastructure.odoo_tax_repository import OdooTaxRepository


class LedgerProvider(models.AbstractModel):
    _name = 'vn.ledger.provider'
    _description = 'Vietnam Ledger Domain Provider'

    def ledger_repository_class(self):
        return OdooLedgerRepository

    def ledger_engine_class(self):
        return LedgerEngine

    def build_ledger_repository(self):
        return self.ledger_repository_class()(self.env)

    def build_ledger_engine(self):
        return self.ledger_engine_class()(self.build_ledger_repository())

    # -- financial statements ------------------------------------------
    def mapping_repository_class(self):
        return OdooMappingRepository

    def financial_statement_engine_class(self):
        return FinancialStatementEngine

    def build_mapping_repository(self):
        return self.mapping_repository_class()(self.env)

    def build_financial_statement_engine(self):
        """The Financial Statement Engine sits on top of the Ledger Engine.

        Domain depending on Domain, which the dependency rule allows; what it
        must never do is reach for a repository of its own to read journal
        items.
        """
        return self.financial_statement_engine_class()(
            self.build_ledger_engine(), self.build_mapping_repository())

    # -- tax -----------------------------------------------------------
    def tax_repository_class(self):
        return OdooTaxRepository

    def tax_engine_class(self):
        return TaxEngine

    def build_tax_repository(self):
        return self.tax_repository_class()(self.env)

    def build_tax_engine(self):
        return self.tax_engine_class()(self.build_tax_repository())

    # -- cash flow -----------------------------------------------------
    def cash_flow_engine_class(self):
        return CashFlowEngine

    def build_cash_flow_engine(self):
        """Reads journal entries, not balances — see the engine's docstring."""
        return self.cash_flow_engine_class()(
            self.build_ledger_engine(), self.build_mapping_repository())

    def vat_declaration_engine_class(self):
        return VatDeclarationEngine

    def build_vat_declaration_engine(self):
        """The declaration needs both engines: the listings and the ledger.

        The listings give the figures; the ledger is what they are checked
        against, since VAT posted by hand never reaches a listing.
        """
        return self.vat_declaration_engine_class()(
            self.build_tax_engine(), self.build_ledger_engine())
