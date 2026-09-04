# -*- coding: utf-8 -*-
"""Ledger use cases (Part 11 §7).

One Service per use case. Each is a thin coordinator: build the repository, get
the engine from the Odoo-side provider, call it, wrap the DTO in a ``ResultDTO``.
No accounting logic here.
"""

from ..core.enums import AgingBasis, AgingSide, GroupBy, TaxDirection
from ..core.exceptions import MappingException
from .base_service import BaseService


class _LedgerServiceBase(BaseService):

    def _engine(self):
        """Resolve the engine through the addon-side provider.

        Going through ``vn.ledger.provider`` rather than instantiating
        ``LedgerEngine`` directly is what keeps the Open/Closed promise: a
        customer module can ``_inherit`` the provider and return its own engine
        subclass, and because the provider is an Odoo model the override applies
        per database according to which modules are installed.
        """
        return self.env['vn.ledger.provider'].build_ledger_engine()


class GeneralLedgerService(_LedgerServiceBase):
    """Sổ Cái / Sổ chi tiết tài khoản."""

    name = 'general_ledger'

    def generate(self, ledger_filter, group_by=GroupBy.ACCOUNT,
                 with_counterpart=True):
        engine = self._engine()
        return self._execute(
            lambda: engine.compute_ledger(
                ledger_filter, group_by=group_by,
                with_counterpart=with_counterpart),
            date_from=ledger_filter.date_from, date_to=ledger_filter.date_to)


class GeneralJournalService(_LedgerServiceBase):
    """Sổ Nhật ký chung."""

    name = 'general_journal'

    def generate(self, ledger_filter):
        engine = self._engine()
        return self._execute(
            lambda: engine.compute_journal(ledger_filter),
            date_from=ledger_filter.date_from, date_to=ledger_filter.date_to)


class TrialBalanceService(_LedgerServiceBase):
    """Bảng cân đối phát sinh."""

    name = 'trial_balance'

    def generate(self, ledger_filter, include_empty=False):
        engine = self._engine()
        return self._execute(
            lambda: engine.compute_trial_balance(
                ledger_filter, include_empty=include_empty),
            date_from=ledger_filter.date_from, date_to=ledger_filter.date_to)


class SalesLedgerService(_LedgerServiceBase):
    """Sổ chi tiết bán hàng (S35-DN)."""

    name = 'sales_ledger'

    def generate(self, ledger_filter):
        engine = self._engine()
        return self._execute(
            lambda: engine.compute_sales_ledger(ledger_filter),
            date_from=ledger_filter.date_from, date_to=ledger_filter.date_to)


class ExpenseLedgerService(_LedgerServiceBase):
    """Sổ chi phí sản xuất, kinh doanh (S36-DN)."""

    name = 'expense_ledger'

    def generate(self, ledger_filter):
        engine = self._engine()
        return self._execute(
            lambda: engine.compute_expense_ledger(ledger_filter),
            date_from=ledger_filter.date_from, date_to=ledger_filter.date_to)


class MaterialAllocationService(_LedgerServiceBase):
    """Bảng phân bổ nguyên liệu, vật liệu, công cụ, dụng cụ (07-VT)."""

    name = 'material_allocation'

    def generate(self, ledger_filter):
        engine = self._engine()
        return self._execute(
            lambda: engine.compute_allocation_table(ledger_filter),
            date_from=ledger_filter.date_from, date_to=ledger_filter.date_to)


class PartnerLedgerService(_LedgerServiceBase):
    """Sổ chi tiết công nợ."""

    name = 'partner_ledger'

    def generate(self, ledger_filter):
        engine = self._engine()
        return self._execute(
            lambda: engine.compute_ledger(
                ledger_filter, group_by=GroupBy.PARTNER_ACCOUNT,
                with_counterpart=True),
            date_from=ledger_filter.date_from, date_to=ledger_filter.date_to)


class _AgingServiceBase(_LedgerServiceBase):
    """Shared plumbing for the two aged-balance use cases."""

    side = None

    def generate(self, ledger_filter, basis=AgingBasis.DUE_DATE, buckets=None):
        engine = self._engine()
        kwargs = {'side': self.side, 'basis': basis}
        if buckets:
            kwargs['buckets'] = buckets
        return self._execute(
            lambda: engine.compute_aging(ledger_filter, **kwargs),
            date_to=ledger_filter.date_to)


class AgedReceivableService(_AgingServiceBase):
    """Bảng tổng hợp công nợ phải thu theo tuổi nợ."""

    name = 'aged_receivable'
    side = AgingSide.RECEIVABLE


class AgedPayableService(_AgingServiceBase):
    """Bảng tổng hợp công nợ phải trả theo tuổi nợ."""

    name = 'aged_payable'
    side = AgingSide.PAYABLE


class _FinancialStatementServiceBase(BaseService):
    """Shared plumbing for statutory financial statements."""

    mapping_code = None

    def _engine(self):
        return self.env['vn.ledger.provider'].build_financial_statement_engine()

    def generate(self, ledger_filter, comparative_filter=None,
                 mapping_code=None):
        engine = self._engine()
        code = mapping_code or self.mapping_code
        return self._execute(
            lambda: engine.compute(ledger_filter, code,
                                   comparative_filter=comparative_filter),
            mapping=code, date_to=ledger_filter.date_to)


class IncomeStatementService(_FinancialStatementServiceBase):
    """Báo cáo kết quả hoạt động kinh doanh (B02-DN)."""

    name = 'income_statement'
    mapping_code = 'tt200_b02dn'


class _VatListingServiceBase(BaseService):
    """Bảng kê hoá đơn GTGT."""

    direction = None

    def _engine(self):
        return self.env['vn.ledger.provider'].build_tax_engine()

    def generate(self, ledger_filter):
        engine = self._engine()
        return self._execute(
            lambda: engine.compute_vat_listing(ledger_filter, self.direction),
            date_from=ledger_filter.date_from, date_to=ledger_filter.date_to)


class VatSalesService(_VatListingServiceBase):
    """Bảng kê hoá đơn, chứng từ hàng hoá dịch vụ bán ra."""

    name = 'vat_sales'
    direction = TaxDirection.SALE


class VatPurchaseService(_VatListingServiceBase):
    """Bảng kê hoá đơn, chứng từ hàng hoá dịch vụ mua vào."""

    name = 'vat_purchase'
    direction = TaxDirection.PURCHASE


class BalanceSheetService(_FinancialStatementServiceBase):
    """Bảng cân đối kế toán (B01-DN)."""

    name = 'balance_sheet'
    mapping_code = 'tt200_b01dn'


class CashFlowService(BaseService):
    """Báo cáo lưu chuyển tiền tệ, phương pháp trực tiếp (B03-DN)."""

    name = 'cash_flow'
    mapping_code = 'tt200_b03dn'

    def generate(self, ledger_filter, mapping_code=None):
        """Pick the engine the form calls for, not the one the caller guessed.

        A direct cash flow reads journal entries and classifies each movement by
        its counterpart; an indirect one starts from profit and adjusts it with
        balance movements, which is what the Financial Statement Engine already
        does. The method is a property of the form, so the mapping decides.
        """
        provider = self.env['vn.ledger.provider']
        code = mapping_code or self.mapping_code
        mapping = provider.build_mapping_repository().get_mapping(
            code, ledger_filter.company_ids)
        if mapping is None:
            return self._execute(
                lambda: (_ for _ in ()).throw(
                    MappingException("Mapping %r not found." % code)),
                mapping=code)

        if mapping.cash_flow_method == 'indirect':
            engine = provider.build_financial_statement_engine()
            return self._execute(
                lambda: engine.compute(ledger_filter, code),
                mapping=code, date_to=ledger_filter.date_to)

        engine = provider.build_cash_flow_engine()
        return self._execute(
            lambda: engine.compute(ledger_filter, code),
            mapping=code, date_to=ledger_filter.date_to)


class VatDeclarationService(BaseService):
    """Tờ khai thuế giá trị gia tăng (mẫu 01/GTGT)."""

    name = 'vat_declaration'

    def generate(self, ledger_filter, inputs=None):
        engine = self.env['vn.ledger.provider'].build_vat_declaration_engine()
        return self._execute(
            lambda: engine.compute(ledger_filter, inputs=inputs),
            date_from=ledger_filter.date_from, date_to=ledger_filter.date_to)
