# -*- coding: utf-8 -*-
"""Manufacturing repository interface (Part 6 §11).

Cost and quantity both come from the valuation layers of the moves attached to a
manufacturing order, for the same reason the inventory reports do: the layer is
what Odoo posted to accounts 152 and 155, so a cost sheet built on it agrees
with the ledger by construction. Reading quantities from the order and values
from a price field would drift the moment a cost changed.
"""

import abc


class IManufacturingRepository(abc.ABC):

    @abc.abstractmethod
    def get_productions(self, manufacturing_filter, done=True):
        """-> Tuple[ProductionDTO, ...].

        ``done=True`` returns orders completed within the period; ``done=False``
        returns those still open at ``date_to``, which are work in progress
        rather than finished cost.
        """

    @abc.abstractmethod
    def get_productions_open_at(self, manufacturing_filter, at_date):
        """Orders that were work in progress at the end of ``at_date``.

        -> Tuple[ProductionDTO, ...]: started on or before the date and not
        finished by it. Unlike ``get_productions(done=False)`` this includes
        orders that have since been completed — the cost card needs the WIP as
        it stood on a historical date, not as it stands today.
        """

    @abc.abstractmethod
    def get_material_costs(self, production_ids, date_from=None, date_to=None):
        """-> ``{production_id: cost}`` from the components consumed.

        Positive: the value that left stock and went into the order. The
        optional bounds restrict to consumption dated within them (inclusive),
        which is what opening and closing WIP on a cost card are made of;
        without bounds the whole life of the order counts, as the production
        cost report expects.
        """

    @abc.abstractmethod
    def get_outputs(self, production_ids):
        """-> ``{production_id: (quantity, value)}`` of the finished goods."""

    @abc.abstractmethod
    def get_currency(self, company_ids):
        """-> CurrencyDTO of the reporting company."""
