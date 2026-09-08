# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""Demo stock movements for the inventory reports.

The accounting demo (``vn.demo.data.generator``) writes journal entries; this
writes what the stock reports actually read — valuation layers — through the
regular inventory-adjustment flow, with **real-time valuation** wired to the
Vietnamese accounts so S10-DN has a "TK đối ứng" column worth printing and
07-VT has issues to allocate.

Unlike the ledger demo this is **not clear-and-rebuild**: done stock moves
cannot be unlinked, so ``generate`` runs once and afterwards reports itself as
already loaded. Marker: any product coded ``VNDEMO-NVL1``.
"""

from odoo import _, api, models
from odoo.exceptions import UserError

#: (code, name, list of (account prefix fallbacks)) resolved best-first, so a
#: TT200 chart yields 1521/6210... while the generic demo accounts still work.
_ACCOUNT_FALLBACKS = {
    'valuation_nvl': ('1521', '152'),
    'valuation_tp': ('1551', '155'),
    'input_nvl': ('331',),
    'output_nvl': ('621', '154'),
    'input_tp': ('154',),
    'output_tp': ('632',),
}

PRODUCTS = (
    # (code, name, category key, cost, opening qty)
    ('VNDEMO-NVL1', 'Ván MDF phủ melamine', 'nvl', 250000.0, 200.0),
    ('VNDEMO-NVL2', 'Gỗ sồi xẻ sấy', 'nvl', 1200000.0, 50.0),
    ('VNDEMO-TP1', 'Bộ bàn ăn gỗ sồi (demo kho)', 'tp', 0.0, 0.0),
)


class VnStockDemoGenerator(models.AbstractModel):
    _name = 'vn.demo.stock.generator'
    _description = 'Vietnam VAS Demo Data - Inventory'

    @api.model
    def generate(self, company=None):
        company = company or self.env.company
        Product = self.env['product.product']
        if Product.search([('default_code', '=', PRODUCTS[0][0])], limit=1):
            return {'company': company.name, 'skipped': True}

        categories = self._ensure_categories(company)
        products = {}
        for code, name, categ_key, cost, _qty in PRODUCTS:
            products[code] = Product.create({
                'name': name,
                'default_code': code,
                # Odoo 18: storable goods are type consu with is_storable.
                'type': 'consu',
                'is_storable': True,
                'categ_id': categories[categ_key].id,
                'standard_price': cost,
            })

        self._opening_inventory(company, products)
        return {
            'company': company.name,
            'skipped': False,
            'products': len(products),
        }

    # ------------------------------------------------------------------
    def _account(self, company, key):
        Account = self.env['account.account'].with_company(company)
        for prefix in _ACCOUNT_FALLBACKS[key]:
            account = Account.search([
                ('company_ids', 'in', [company.id]),
                ('code', '=like', prefix + '%'),
            ], order='code', limit=1)
            if account:
                return account
        raise UserError(_(
            'No account found for %s; install a chart of accounts or run '
            'the accounting demo first.') % (_ACCOUNT_FALLBACKS[key],))

    def _ensure_categories(self, company):
        """Two real-time categories: raw materials and finished goods.

        Real-time valuation is what makes the demo worth having — the layers
        then post entries, and both S10-DN's counterpart column and 07-VT's
        allocation read those entries.
        """
        journal = self.env['account.journal'].search([
            ('company_id', '=', company.id), ('type', '=', 'general')],
            limit=1)
        Category = self.env['product.category']

        def category(name, valuation_key, input_key, output_key):
            return Category.create({
                'name': name,
                'property_valuation': 'real_time',
                'property_cost_method': 'average',
                'property_stock_valuation_account_id':
                    self._account(company, valuation_key).id,
                'property_stock_account_input_categ_id':
                    self._account(company, input_key).id,
                'property_stock_account_output_categ_id':
                    self._account(company, output_key).id,
                'property_stock_journal': journal.id,
            })

        return {
            'nvl': category('VAS demo - Nguyên vật liệu',
                            'valuation_nvl', 'input_nvl', 'output_nvl'),
            'tp': category('VAS demo - Thành phẩm',
                           'valuation_tp', 'input_tp', 'output_tp'),
        }

    def _set_stock(self, company, product, quantity):
        """Set on-hand through the quant inventory flow.

        ``stock.inventory`` left Odoo in 15.0; the counted quantity on the
        quant plus ``action_apply_inventory`` is the supported way since.
        """
        location = self.env['stock.warehouse'].search(
            [('company_id', '=', company.id)], limit=1).lot_stock_id
        quant = self.env['stock.quant'].with_context(
            inventory_mode=True).create({
                'product_id': product.id,
                'location_id': location.id,
                'inventory_quantity': quantity,
            })
        quant.action_apply_inventory()

    def _opening_inventory(self, company, products):
        for code, _name, _categ, _cost, qty in PRODUCTS:
            if qty:
                self._set_stock(company, products[code], qty)
