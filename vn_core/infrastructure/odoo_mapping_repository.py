# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""Odoo implementation of ``IMappingRepository``.

Maps records to DTOs and nothing else. Every rule about what a mapping *means*
— sides, signs, formulas, validation — lives in the Domain.
"""

from ..domain.financial_statement.repository import IMappingRepository
from ..dto.financial_statement import MappingDTO, MappingLineDTO
from .base_repository import BaseRepository


class OdooMappingRepository(IMappingRepository, BaseRepository):

    def _domain(self, company_ids):
        # A mapping with no company is shared; a company-specific one overrides
        # it, which is how a client can amend a statutory form for itself
        # without touching the shipped data.
        return ['|', ('company_id', '=', False),
                ('company_id', 'in', list(company_ids or []))]

    def get_mapping(self, code, company_ids):
        mappings = self.env['vn.report.mapping'].search(
            self._domain(company_ids) + [('code', '=', code)],
            order='company_id desc', limit=1)
        if not mappings:
            return None
        return self._to_dto(mappings, with_lines=True)

    def list_mappings(self, report_type=None, company_ids=None):
        domain = self._domain(company_ids)
        if report_type:
            domain.append(('report_type', '=', report_type))
        return tuple(self._to_dto(m, with_lines=False)
                     for m in self.env['vn.report.mapping'].search(domain))

    def _to_dto(self, mapping, with_lines):
        lines = ()
        if with_lines:
            lines = tuple(
                MappingLineDTO(
                    code=line.code,
                    name=line.name or '',
                    sequence=line.sequence,
                    level=line.level,
                    parent_code=line.parent_id.code or '',
                    expression=line.expression or '',
                    formula=line.formula or '',
                    sign=line.sign,
                    side=line.side,
                    split_by_partner=line.split_by_partner,
                    note_ref=line.note_ref or '',
                    visible=line.visible,
                    bold=line.bold,
                )
                for line in mapping.line_ids.sorted(
                    key=lambda l: (l.sequence, l.code))
            )
        return MappingDTO(
            code=mapping.code,
            name=mapping.name,
            report_type=mapping.report_type,
            basis=mapping.basis,
            version=mapping.version or '',
            balance_check=mapping.balance_check or '',
            cash_expression=mapping.cash_expression or '',
            cash_flow_method=mapping.cash_flow_method or 'direct',
            lines=lines,
        )
