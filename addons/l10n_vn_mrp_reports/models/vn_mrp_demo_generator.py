# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Demo manufacturing orders for the production cost reports.

Self-contained on purpose: this module does not depend on
``l10n_vn_stock_reports``, so it builds its own component with stock and its
own real-time categories rather than borrowing another demo's. Two orders
finish (the cost report and S37-DN get figures), one stays open with its
materials issued (the cost card gets a closing WIP).

Runs once; done manufacturing orders cannot be unlinked, so a rerun reports
itself as already loaded. Marker: any product coded ``VNDEMO-MRP-NVL``.
"""

from odoo import _, api, models
from odoo.exceptions import UserError

_ACCOUNT_FALLBACKS = {
    'valuation_nvl': ('1521', '152'),
    'valuation_tp': ('1551', '155'),
    'input_nvl': ('331',),
    'output_nvl': ('621', '154'),
    'input_tp': ('154',),
    'output_tp': ('632',),
}


class VnMrpDemoGenerator(models.AbstractModel):
    _name = 'vn.demo.mrp.generator'
    _description = 'Vietnam VAS Demo Data - Manufacturing'

    @api.model
    def generate(self, company=None):
        company = company or self.env.company
        Product = self.env['product.product']
        if Product.search([('default_code', '=', 'VNDEMO-MRP-NVL')], limit=1):
            return {'company': company.name, 'skipped': True}

        nvl_categ, tp_categ = self._ensure_categories(company)
        component = Product.create({
            'name': 'Gỗ sồi ghép thanh (demo SX)',
            'default_code': 'VNDEMO-MRP-NVL',
            'type': 'product',
            'categ_id': nvl_categ.id,
            'standard_price': 400000.0,
        })
        finished = Product.create({
            'name': 'Tủ quần áo 4 cánh (demo SX)',
            'default_code': 'VNDEMO-MRP-TP',
            'type': 'product',
            'categ_id': tp_categ.id,
        })

        self._add_stock(company, component, 500.0)
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': finished.product_tmpl_id.id,
            'product_qty': 1,
            'bom_line_ids': [(0, 0, {'product_id': component.id,
                                     'product_qty': 4})],
        })

        for quantity in (10.0, 5.0):
            self._run_order(finished, bom, quantity, finish=True)
        # One order stays open with its materials already issued: that is the
        # closing WIP the cost card exists to show.
        self._run_order(finished, bom, 8.0, finish=False)

        return {'company': company.name, 'skipped': False, 'orders': 3}

    # ------------------------------------------------------------------
    def _account(self, company, key):
        Account = self.env['account.account']
        for prefix in _ACCOUNT_FALLBACKS[key]:
            account = Account.search([
                ('company_id', '=', company.id),
                ('code', '=like', prefix + '%'),
            ], order='code', limit=1)
            if account:
                return account
        raise UserError(_(
            'No account found for %s; install a chart of accounts or run '
            'the accounting demo first.') % (_ACCOUNT_FALLBACKS[key],))

    def _ensure_categories(self, company):
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

        return (category('VAS demo SX - Nguyên vật liệu',
                         'valuation_nvl', 'input_nvl', 'output_nvl'),
                category('VAS demo SX - Thành phẩm',
                         'valuation_tp', 'input_tp', 'output_tp'))

    def _add_stock(self, company, product, quantity):
        inventory = self.env['stock.inventory'].create({
            'name': 'VAS demo SX - tồn nguyên liệu',
            'company_id': company.id,
            'product_ids': [(4, product.id)],
        })
        inventory.action_start()
        self.env['stock.inventory.line'].create({
            'inventory_id': inventory.id,
            'product_id': product.id,
            'location_id': self.env['stock.warehouse'].search(
                [('company_id', '=', company.id)], limit=1).lot_stock_id.id,
            'product_qty': quantity,
            'product_uom_id': product.uom_id.id,
        })
        inventory.action_validate()

    def _run_order(self, finished, bom, quantity, finish):
        # Imported lazily: odoo.tests is a heavyweight import that production
        # code should not pull at registry load; only this demo path needs the
        # Form emulator to run the manufacturing onchanges.
        from odoo.tests import Form
        order_form = Form(self.env['mrp.production'])
        order_form.product_id = finished
        order_form.bom_id = bom
        order_form.product_qty = quantity
        order = order_form.save()
        order.action_confirm()
        order.action_assign()
        if finish:
            order_form = Form(order)
            order_form.qty_producing = quantity
            order = order_form.save()
            order.button_mark_done()
        else:
            # Issue the components without finishing: the raw moves complete,
            # the order stays in progress, and the consumed value is exactly
            # the closing WIP an accountant computes for TK 154.
            for move in order.move_raw_ids:
                move.quantity_done = move.product_uom_qty
            order.move_raw_ids._action_done()
        return order
