# -*- coding: utf-8 -*-
"""Mapping repository interface (Part 5 §4, Part 6 §6).

The Financial Statement Engine knows this contract and nothing else, so a
mapping can come from Odoo records, a YAML file or an in-memory fixture without
the Domain noticing.
"""

import abc


class IMappingRepository(abc.ABC):

    @abc.abstractmethod
    def get_mapping(self, code, company_ids):
        """-> ``MappingDTO`` or ``None`` when no such mapping exists."""

    @abc.abstractmethod
    def list_mappings(self, report_type=None, company_ids=None):
        """-> Tuple[MappingDTO, ...] without their lines, for pickers."""
