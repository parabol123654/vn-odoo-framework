# -*- coding: utf-8 -*-
"""Ledger Engine (Part 4 §7).

Pure Python. No Odoo import, no ORM, no SQL, no knowledge of PDF/XLSX/QWeb. The
Engine orchestrates: it asks calculators for business rules, asks the Repository
interface for data, and returns DTOs.

Because the only collaborator is ``ILedgerRepository``, the whole Engine can be
exercised against an in-memory fake — see ``tests/test_ledger_engine.py``.

Deliberately absent: user-facing strings. The Engine emits codes and names taken
from DTOs and leaves labels such as "All accounts" to the presentation layer, so
the Domain needs no translation machinery.
"""

from ...core.enums import AgingBasis, AgingSide, GroupBy
from ...core.exceptions import BusinessException, ValidationException
from ...core.utils.number import is_zero, round_amount
from ...dto.ledger import (
    AgingDTO, AgingGroupDTO, AllocationRowDTO, AllocationTableDTO,
    BalanceSummaryDTO, AgingLineDTO, BalanceDTO,
    ExpenseLedgerDTO, ExpenseLedgerGroupDTO, ExpenseLedgerLineDTO, LedgerDTO,
    LedgerGroupDTO, LedgerLineDTO, SalesLedgerDTO, SalesLedgerGroupDTO,
    SalesLedgerLineDTO, TrialBalanceDTO, TrialBalanceRowDTO,
)
from .calculators.aging import AgingCalculator, DEFAULT_BUCKETS
from .calculators.closing_balance import ClosingBalanceCalculator
from .calculators.counterpart import CounterpartCalculator
from .calculators.opening_balance import OpeningBalanceCalculator
from .calculators.running_balance import RunningBalanceCalculator
from .calculators.sided_balance import SidedBalanceCalculator

_EMPTY = BalanceDTO()


class LedgerEngine:

    def __init__(self, repository):
        self._repo = repository

    # ==================================================================
    # Public API
    # ==================================================================
    def compute_trial_balance(self, ledger_filter, include_empty=False):
        """Bảng cân đối phát sinh."""
        context = self._load_context(ledger_filter)
        opening, movement = self._compute_aggregates(
            ledger_filter, context, GroupBy.ACCOUNT)

        rounding = context['currency'].rounding
        accounts = context['accounts_by_id']

        # An account with no opening and no movement appears in neither
        # aggregate, so "show all accounts" has to start from the chart itself.
        keys = set(opening) | set(movement)
        if include_empty:
            keys |= {(account.id,) for account in context['accounts']}

        rows = []
        for key in keys:
            account = accounts.get(key[0])
            if account is None:
                continue
            row = self._build_trial_row(
                key, account, opening.get(key, _EMPTY),
                movement.get(key, _EMPTY), rounding)
            if include_empty or not self._row_is_empty(row, rounding):
                rows.append(row)

        rows.sort(key=lambda r: (r.code, r.name))
        return self._total_trial_balance(rows, context['currency'])

    def compute_ledger(self, ledger_filter, group_by=GroupBy.ACCOUNT,
                       with_counterpart=False, with_running_balance=True):
        """General Ledger, Account Ledger, Partner Ledger, Cash/Bank Book."""
        context = self._load_context(ledger_filter)
        opening, movement = self._compute_aggregates(
            ledger_filter, context, group_by)

        lines = tuple(self._repo.get_move_lines(ledger_filter))
        buckets = self._bucket(lines, group_by)

        counterpart_index = {}
        naming = context['accounts_by_id']
        if with_counterpart and lines:
            counterpart_index = CounterpartCalculator.index(
                self._repo.get_move_account_sums(
                    tuple({line.move_id for line in lines})))
            naming = self._counterpart_names(ledger_filter, counterpart_index,
                                             context)

        lookups = self._build_lookups(
            context, group_by, set(buckets) | set(opening) | set(movement))
        rounding = context['currency'].rounding

        groups = []
        for key in set(buckets) | set(opening) | set(movement):
            groups.append(self._build_group(
                key, group_by, lookups, naming,
                buckets.get(key, ()), opening.get(key, _EMPTY),
                movement.get(key, _EMPTY), rounding, counterpart_index,
                with_running_balance))

        groups.sort(key=lambda g: (g.code, g.name))
        totals = self._sum_balances(g.movement for g in groups)
        return LedgerDTO(
            groups=tuple(groups),
            totals=self._round_balance(totals, rounding),
            currency=context['currency'],
            group_by=group_by.fields,
        )

    def compute_journal(self, ledger_filter):
        """Sổ Nhật ký chung — strictly chronological, ungrouped.

        Lines keep their ``date, move, id`` order so the items of one voucher
        stay adjacent, which the VAS form requires.
        """
        return self.compute_ledger(
            ledger_filter, group_by=GroupBy.NONE, with_counterpart=True,
            with_running_balance=False)

    def compute_expense_ledger(self, ledger_filter, breakdown_limit=6,
                               root_length=3):
        """Sổ chi phí sản xuất, kinh doanh (S36-DN).

        A debit-side detail ledger of the cost accounts, with the "chia ra"
        breakdown the form asks for. TT200 leaves the breakdown headings to the
        bookkeeper; here each column is a counterpart account root (``152`` is
        materials, ``334`` labour, ``214`` depreciation...), which is how the
        khoản mục are derived in practice and keeps every column reconcilable
        to the ledger.

        Rules the numbers follow:

        * Only debit lines are detailed. The credit side is the closing
          transfer and prints as one "Ghi Có TK" figure, as the form does.
        * A line is never split across columns by guesswork. One counterpart
          root — that column; several roots, or none — the residual column,
          whole. The counterpart calculator allocates no amounts (see its
          docstring), and inventing an allocation here would print figures
          nobody can trace.
        * At most ``breakdown_limit`` named columns, ranked by amount; the
          rest joins the residual column. A page has finite width, and a
          column too small to rank rarely deserves one.
        """
        ledger = self.compute_ledger(ledger_filter, group_by=GroupBy.ACCOUNT,
                                     with_counterpart=True,
                                     with_running_balance=False)
        rounding = ledger.currency.rounding

        groups = []
        for group in ledger.groups:
            debit_lines = [line for line in group.lines
                           if not is_zero(line.debit, rounding)
                           and line.debit > 0]

            roots = {}
            for line in debit_lines:
                roots[line] = self._counterpart_root(line, root_length)

            totals_by_root = {}
            for line, root in roots.items():
                totals_by_root[root] = totals_by_root.get(root, 0.0) + line.debit
            named = sorted((root for root in totals_by_root if root),
                           key=lambda r: -totals_by_root[r])[:breakdown_limit]
            columns = tuple(sorted(named))
            residual_used = any(root not in named for root in totals_by_root)
            if residual_used:
                columns += ('',)

            lines = []
            for line in debit_lines:
                root = roots[line]
                position = (columns.index(root) if root in named
                            else len(columns) - 1)
                amounts = [0.0] * len(columns)
                amounts[position] = round_amount(line.debit, rounding)
                lines.append(ExpenseLedgerLineDTO(
                    source=line, amounts=tuple(amounts)))

            column_totals = tuple(
                round_amount(sum(line.amounts[i] for line in lines), rounding)
                for i in range(len(columns)))

            groups.append(ExpenseLedgerGroupDTO(
                account_id=group.key[0],
                code=group.code,
                name=group.name,
                opening=group.opening,
                columns=columns,
                lines=tuple(lines),
                debit_total=group.movement.debit,
                column_totals=column_totals,
                credit_total=group.movement.credit,
                closing=group.closing,
            ))

        return ExpenseLedgerDTO(
            groups=tuple(groups),
            total_debit=ledger.totals.debit,
            total_credit=ledger.totals.credit,
            currency=ledger.currency,
        )

    def compute_sales_ledger(self, ledger_filter, deduction_prefix='521',
                             closing_roots=('911', '421'), root_length=3):
        """Sổ chi tiết bán hàng (S35-DN): doanh thu theo sản phẩm.

        Reads the revenue and deduction accounts the filter names (511* and
        521* by default), one row per journal item, grouped by product. Three
        rules:

        * a line on a ``deduction_prefix`` account is a "khoản giảm trừ" (net
          debit); everything else is revenue (net credit);
        * the year-end transfer — a revenue line facing one of the
          ``closing_roots`` (911, or 421 for books that close revenue
          directly to retained earnings) — is not a sale and never enters
          the book;
        * lines with no product are grouped under their own block rather than
          dropped, so the book still adds up to account 511. The VAT columns
          of the paper form are not here: tax is a property of the invoice,
          not of the 511 line, and the Bảng kê 01/GTGT already reports it
          from the tax lines themselves.
        """
        ledger = self.compute_ledger(ledger_filter, group_by=GroupBy.NONE,
                                     with_counterpart=True,
                                     with_running_balance=False)
        rounding = ledger.currency.rounding

        buckets = {}
        for group in ledger.groups:
            for line in group.lines:
                is_deduction = line.account_code.startswith(deduction_prefix)
                if not is_deduction and (self._counterpart_root(
                        line, root_length) in closing_roots):
                    continue
                revenue = deduction = 0.0
                if is_deduction:
                    deduction = round_amount(line.debit - line.credit,
                                             rounding)
                else:
                    revenue = round_amount(line.credit - line.debit, rounding)
                if is_zero(revenue, rounding) and is_zero(deduction, rounding):
                    continue
                buckets.setdefault(line.source.product_id, []).append(
                    SalesLedgerLineDTO(source=line, revenue=revenue,
                                       deduction=deduction))

        products = {p.id: p for p in self._repo.get_products(
            tuple(pid for pid in buckets if pid))}

        groups = []
        for product_id, lines in buckets.items():
            lines.sort(key=lambda l: (l.date, l.source.source.move_id,
                                      l.source.source.id))
            groups.append(SalesLedgerGroupDTO(
                product=products.get(product_id),
                lines=tuple(lines),
                quantity_total=sum(
                    l.quantity for l in lines if l.revenue),
                revenue_total=round_amount(
                    sum(l.revenue for l in lines), rounding),
                deduction_total=round_amount(
                    sum(l.deduction for l in lines), rounding),
            ))
        # Products in code order; the productless block closes the book.
        groups.sort(key=lambda g: (g.product is None,
                                   g.product.code if g.product else '',
                                   g.product.name if g.product else ''))

        return SalesLedgerDTO(
            groups=tuple(groups),
            total_revenue=round_amount(
                sum(g.revenue_total for g in groups), rounding),
            total_deduction=round_amount(
                sum(g.deduction_total for g in groups), rounding),
            currency=ledger.currency,
        )

    def compute_allocation_table(self, ledger_filter, root_length=3):
        """Bảng phân bổ nguyên liệu, vật liệu, công cụ, dụng cụ (07-VT).

        A period cross-tab: columns are the credited accounts the filter names
        (152, 153, 242 — what left the stores or was amortised), rows are the
        debit-side roots the value went to (621, 627, 641, 642, 632...), each
        cell the amount allocated between them. Built from the credit lines of
        the ledger itself, so every column total reconciles to the "Ghi Có"
        of that account by construction.

        The same no-guesswork rule as the expense ledger: an entry whose debit
        side spans several roots lands whole on the residual row rather than
        being split by an invented ratio. Debits to the source accounts —
        returns to store — are not netted off: the form reports what was
        issued, and a return is a receipt.
        """
        ledger = self.compute_ledger(ledger_filter, group_by=GroupBy.ACCOUNT,
                                     with_counterpart=True,
                                     with_running_balance=False)
        rounding = ledger.currency.rounding

        cells, column_roots = {}, []
        for group in ledger.groups:
            column = (group.code or '')[:root_length]
            if column not in column_roots:
                column_roots.append(column)
            for line in group.lines:
                if line.credit <= 0 or is_zero(line.credit, rounding):
                    continue
                row = self._counterpart_root(line, root_length)
                key = (row, column)
                cells[key] = cells.get(key, 0.0) + line.credit

        columns = tuple(sorted(column_roots))
        # The residual row ('') would sort first; it belongs last.
        row_roots = sorted({row for row, _ in cells}, key=lambda r: (not r, r))

        rows = []
        for root in row_roots:
            amounts = tuple(
                round_amount(cells.get((root, column), 0.0), rounding)
                for column in columns)
            rows.append(AllocationRowDTO(
                code=root,
                amounts=amounts,
                total=round_amount(sum(amounts), rounding),
            ))

        column_totals = tuple(
            round_amount(sum(row.amounts[i] for row in rows), rounding)
            for i in range(len(columns)))
        return AllocationTableDTO(
            columns=columns,
            rows=tuple(rows),
            column_totals=column_totals,
            grand_total=round_amount(sum(column_totals), rounding),
            currency=ledger.currency,
        )

    @staticmethod
    def _counterpart_root(line, root_length):
        """The single breakdown key of a debit line, or '' when there is none.

        Derived from the counterpart codes the line already carries, so the
        breakdown can never disagree with the "TK đối ứng" column beside it.
        """
        codes = [code.strip()
                 for code in line.counterpart_label.split(',') if code.strip()]
        roots = {code[:root_length] for code in codes}
        return roots.pop() if len(roots) == 1 else ''

    def compute_residual_at_date(self, ledger_filter):
        """``{line_id: residual}`` as it stood on ``date_to``.

        ``amount_residual`` is only ever correct for today, so every partial
        reconciliation dated after ``date_to`` is added back. Aged receivable
        and payable reports must use this rather than the raw field.
        """
        rounding = self._load_context(ledger_filter)['currency'].rounding
        lines = tuple(self._repo.get_move_lines(ledger_filter))
        undo = self._repo.get_reconciled_after(
            tuple(line.id for line in lines), ledger_filter.date_to)
        return {
            line.id: round_amount(line.amount_residual + undo.get(line.id, 0.0),
                                  rounding)
            for line in lines
        }

    # ==================================================================
    # Balances only
    # ==================================================================
    def compute_balances(self, ledger_filter, group_by=GroupBy.ACCOUNT):
        """``{key: BalanceSummaryDTO}`` — aggregates with no detail lines.

        This is what a financial statement consumes. Loading journal items to
        build a balance sheet would be wasteful, and the Financial Statement
        Domain has no business seeing them.
        """
        context = self._load_context(ledger_filter)
        rounding = context['currency'].rounding
        opening, movement = self._compute_aggregates(
            ledger_filter, context, group_by)

        result = {}
        for key in set(opening) | set(movement):
            op = opening.get(key, _EMPTY)
            mv = movement.get(key, _EMPTY)
            result[key] = BalanceSummaryDTO(
                opening=round_amount(op.balance, rounding),
                movement=self._round_balance(mv, rounding),
                closing=round_amount(op.balance + mv.balance, rounding),
            )
        return result

    # ==================================================================
    # Aged receivable / payable
    # ==================================================================
    def compute_aging(self, ledger_filter, side=AgingSide.RECEIVABLE,
                      basis=AgingBasis.DUE_DATE, buckets=DEFAULT_BUCKETS):
        """Bảng tổng hợp công nợ theo tuổi nợ.

        The filter's ``date_from`` is deliberately ignored. An aged balance is an
        as-at picture of everything still open on ``date_to``, so restricting it
        to a period would silently drop the older invoices that are exactly what
        the report exists to surface.
        """
        as_at = ledger_filter.replace(date_from=None)
        context = self._load_context(as_at)
        rounding = context['currency'].rounding
        accounts = context['accounts_by_id']

        lines = tuple(self._repo.get_move_lines(as_at))
        residuals = self.compute_residual_at_date(as_at)
        sign = AgingCalculator.sign(side)
        basis_due = basis is AgingBasis.DUE_DATE

        by_partner = {}
        for line in lines:
            residual = residuals.get(line.id, 0.0)
            if not AgingCalculator.keeps(residual, side, rounding):
                continue
            days = AgingCalculator.days_overdue(line, as_at.date_to, basis_due)
            index = AgingCalculator.bucket_index(days, buckets)
            account = accounts.get(line.account_id)
            by_partner.setdefault(line.partner_id, []).append(AgingLineDTO(
                source=line,
                residual=round_amount(residual * sign, rounding),
                days_overdue=days,
                bucket_index=index,
                account_code=account.code if account else '',
                account_name=account.name if account else '',
            ))

        partners = {p.id: p for p in self._repo.get_partners(
            tuple(pid for pid in by_partner if pid))}

        groups = []
        for partner_id, items in by_partner.items():
            amounts = [0.0] * len(buckets)
            for item in items:
                amounts[item.bucket_index] += item.residual
            partner = partners.get(partner_id)
            groups.append(AgingGroupDTO(
                partner_id=partner_id,
                partner_name=partner.name if partner else '',
                lines=tuple(sorted(items,
                                   key=lambda l: (l.due_date, l.source.id))),
                amounts=tuple(round_amount(a, rounding) for a in amounts),
                total=round_amount(sum(amounts), rounding),
            ))
        groups.sort(key=lambda g: (g.partner_name or '', g.partner_id or 0))

        totals = tuple(
            round_amount(sum(g.amounts[i] for g in groups), rounding)
            for i in range(len(buckets)))
        return AgingDTO(
            buckets=tuple(buckets),
            groups=tuple(groups),
            totals=totals,
            grand_total=round_amount(sum(totals), rounding),
            currency=context['currency'],
            as_of=as_at.date_to,
        )

    # ==================================================================
    # Context
    # ==================================================================
    def _load_context(self, ledger_filter):
        if not ledger_filter.company_ids:
            raise ValidationException('No company supplied in the filter.')
        if ledger_filter.date_from and ledger_filter.date_from > ledger_filter.date_to:
            raise ValidationException('date_from must precede date_to.')

        companies = self._repo.get_companies(ledger_filter.company_ids)
        if not companies:
            raise ValidationException('None of the requested companies exist.')

        currencies = {c.currency.id for c in companies}
        if len(currencies) > 1:
            raise BusinessException(
                'The selected companies use different currencies; amounts '
                'cannot be summed into one ledger.')

        accounts = self._repo.get_accounts(ledger_filter)
        return {
            'companies': companies,
            'currency': companies[0].currency,
            'accounts': accounts,
            'accounts_by_id': {a.id: a for a in accounts},
        }

    def _compute_aggregates(self, ledger_filter, context, group_by):
        """Opening (fiscal-year aware) and period movement, per group key."""
        opening = {}
        if ledger_filter.include_opening:
            windows = OpeningBalanceCalculator.windows(
                context['companies'], context['accounts'],
                ledger_filter.date_from)
            opening = OpeningBalanceCalculator.merge(
                self._repo.aggregate_balances(
                    ledger_filter, group_by.fields, window.date_from,
                    window.date_to, account_ids=window.account_ids,
                    company_ids=window.company_ids)
                for window in windows)

        movement = self._repo.aggregate_balances(
            ledger_filter, group_by.fields, ledger_filter.date_from,
            ledger_filter.date_to)
        return opening, movement

    # ==================================================================
    # Assembly
    # ==================================================================
    def _bucket(self, lines, group_by):
        buckets = {}
        for line in lines:
            key = tuple(getattr(line, field) for field in group_by.fields)
            buckets.setdefault(key, []).append(line)
        return {key: tuple(value) for key, value in buckets.items()}

    def _build_lookups(self, context, group_by, keys):
        """Resolve display names for every key component, in batch."""
        lookups = {}
        for position, field in enumerate(group_by.fields):
            ids = tuple({key[position] for key in keys if key[position]})
            if field == 'account_id':
                lookups[field] = context['accounts_by_id']
            elif field == 'partner_id':
                lookups[field] = {p.id: p for p in self._repo.get_partners(ids)}
            elif field == 'journal_id':
                lookups[field] = {j.id: j for j in self._repo.get_journals(ids)}
            elif field == 'analytic_account_id':
                lookups[field] = {
                    a.id: a for a in self._repo.get_analytic_accounts(ids)}
            else:
                lookups[field] = {}
        return lookups

    def _describe(self, key, group_by, lookups):
        codes, names = [], []
        for position, field in enumerate(group_by.fields):
            record = lookups.get(field, {}).get(key[position])
            codes.append(getattr(record, 'code', '') if record else '')
            names.append(record.name if record else '')
        return ' / '.join(filter(None, codes)), ' / '.join(filter(None, names))

    def _build_group(self, key, group_by, lookups, accounts_by_id, lines,
                     opening, movement, rounding, counterpart_index,
                     with_running_balance):
        code, name = self._describe(key, group_by, lookups)
        opening_sided = SidedBalanceCalculator.split(opening.balance, rounding)
        closing = ClosingBalanceCalculator.compute(
            opening_sided.balance, movement, rounding)

        running = ()
        if with_running_balance:
            running = RunningBalanceCalculator.apply(
                opening_sided.balance, lines, rounding)

        ledger_lines = []
        for position, line in enumerate(lines):
            counterparts = CounterpartCalculator.for_line(
                line, counterpart_index) if counterpart_index else ()
            account = accounts_by_id.get(line.account_id)
            ledger_lines.append(LedgerLineDTO(
                source=line,
                running_balance=running[position] if running else 0.0,
                counterpart_account_ids=counterparts,
                counterpart_label=self._counterpart_label(
                    counterparts, accounts_by_id),
                account_code=account.code if account else '',
                account_name=account.name if account else '',
            ))

        return LedgerGroupDTO(
            key=key,
            code=code,
            name=name,
            opening=opening_sided,
            movement=self._round_balance(movement, rounding),
            closing=SidedBalanceCalculator.split(closing, rounding),
            lines=tuple(ledger_lines),
        )

    def _counterpart_names(self, ledger_filter, index, context):
        """Names for the accounts facing these entries.

        A counterpart is almost never inside the report's own account filter: a
        partner ledger restricted to 131 has 511 and 3331 facing it, and the
        cash book restricted to 111 has everything else. The filtered catalogue
        cannot name them, so without this the column printed raw database ids —
        "143, 78" where the accountant expected "511, 3331".

        Only the accounts actually referenced are fetched, and only when the
        counterpart column was asked for, so the common case costs nothing.
        """
        wanted = set()
        for debit_ids, credit_ids in index.values():
            wanted.update(debit_ids)
            wanted.update(credit_ids)

        known = context['accounts_by_id']
        missing = tuple(sorted(wanted - set(known)))
        if not missing:
            return known

        resolved = dict(known)
        resolved.update({
            account.id: account
            for account in self._repo.get_accounts(
                ledger_filter.replace(account_ids=missing,
                                      account_type_ids=()))
        })
        return resolved

    def _counterpart_label(self, account_ids, accounts_by_id):
        """Render counterparts as "511, 3331" from the account catalogue.

        Resolved against every account in scope rather than the group-by
        lookups, so an ungrouped Sổ Nhật ký chung still shows codes.
        """
        return ', '.join(
            getattr(accounts_by_id.get(account_id), 'code', None) or str(account_id)
            for account_id in account_ids)

    def _build_trial_row(self, key, account, opening, movement, rounding):
        opening_sided = SidedBalanceCalculator.split(opening.balance, rounding)
        closing = ClosingBalanceCalculator.compute(
            opening_sided.balance, movement, rounding)
        return TrialBalanceRowDTO(
            account_id=account.id,
            code=account.code,
            name=account.name,
            opening=opening_sided,
            opening_gross=self._round_balance(opening, rounding),
            movement=self._round_balance(movement, rounding),
            closing=SidedBalanceCalculator.split(closing, rounding),
        )

    def _total_trial_balance(self, rows, currency):
        rounding = currency.rounding
        movement = self._sum_balances(r.movement for r in rows)
        opening = SidedBalanceCalculator.split(
            sum(r.opening.balance for r in rows), rounding)
        closing = SidedBalanceCalculator.split(
            sum(r.closing.balance for r in rows), rounding)
        # An imbalance is reported, not hidden: it almost always means draft
        # entries are included or a move was written outside the ORM.
        total_debit = sum(r.closing.debit_balance for r in rows)
        total_credit = sum(r.closing.credit_balance for r in rows)
        return TrialBalanceDTO(
            rows=tuple(rows),
            total_opening=opening,
            total_movement=self._round_balance(movement, rounding),
            total_closing=closing,
            currency=currency,
            is_balanced=is_zero(total_debit - total_credit, rounding),
        )

    # ==================================================================
    # Small helpers
    # ==================================================================
    def _sum_balances(self, balances):
        total = _EMPTY
        for balance in balances:
            total = total.plus(balance)
        return total

    def _round_balance(self, balance, rounding):
        return BalanceDTO(
            round_amount(balance.debit, rounding),
            round_amount(balance.credit, rounding),
            round_amount(balance.balance, rounding),
        )

    def _row_is_empty(self, row, rounding):
        return all(is_zero(value, rounding) for value in (
            row.opening.balance, row.movement.debit, row.movement.credit,
            row.closing.balance))
