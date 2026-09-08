# -*- coding: utf-8 -*-
"""Smoke test for the VN inventory/manufacturing reports. Run via odoo shell:

    venv/bin/python odoo/odoo-bin shell -c <odoo.conf> -d <database> --no-http --log-level=warn < 3rd_party/vn-odoo-framework/scripts/smoke_test_reports.py

Builds one component with stock, one finished product with a BoM, runs a
manufacturing order to done, then renders every layout of both wizards on
screen and to xlsx. Prints PASS/FAIL lines; raises nothing so the transcript
is always complete.
"""

from datetime import date

from odoo.tests import Form

RESULTS = []


def check(label, fn):
    try:
        value = fn()
        RESULTS.append(('PASS', label, ''))
        return value
    except Exception as error:  # noqa: BLE001 — a smoke test reports, not dies
        RESULTS.append(('FAIL', label, '%s: %s' % (type(error).__name__, error)))
        return None


company = env.company

# ------------------------------------------------------------------
# Real-time valuation so the layers post entries and S10-DN gets a
# counterpart column to print. The demo accounts (152/632/...) exist.
# ------------------------------------------------------------------
Account = env['account.account']


def acc(code):
    return Account.with_company(company).search(
        [('company_ids', 'in', [company.id]),
         ('code', '=like', code + '%')], limit=1)


def setup_valuation():
    categ = env['product.category'].create({
        'name': 'VAS smoke',
        'property_valuation': 'real_time',
        'property_cost_method': 'average',
        'property_stock_valuation_account_id': acc('152').id,
        'property_stock_account_input_categ_id': acc('331').id,
        'property_stock_account_output_categ_id': acc('632').id,
        # Odoo 17+ books MO consumption against the category's production-cost
        # account; 632 keeps the S10-DN counterpart expectation below true.
        'property_stock_account_production_cost_id': acc('632').id,
        'property_stock_journal': env['account.journal'].search(
            [('company_id', '=', company.id), ('type', '=', 'general')],
            limit=1).id,
    })
    return categ


categ = check('real-time valuation category', setup_valuation)

Product = env['product.product']
values = ({'type': 'consu', 'is_storable': True, 'categ_id': categ.id}
          if categ else {'type': 'consu', 'is_storable': True})
comp = Product.create(dict(values, name='NVL smoke', default_code='NVLS',
                           standard_price=100000))
fin = Product.create(dict(values, name='TP smoke', default_code='TPS'))


def add_stock():
    quant = env['stock.quant'].with_context(inventory_mode=True).create({
        'product_id': comp.id,
        'location_id': env['stock.warehouse'].search(
            [('company_id', '=', company.id)], limit=1).lot_stock_id.id,
        'inventory_quantity': 100,
    })
    quant.action_apply_inventory()


check('inventory adjustment', add_stock)


def run_mo():
    bom = env['mrp.bom'].create({
        'product_tmpl_id': fin.product_tmpl_id.id,
        'product_qty': 1,
        'bom_line_ids': [(0, 0, {'product_id': comp.id, 'product_qty': 2})],
    })
    mo_form = Form(env['mrp.production'])
    mo_form.product_id = fin
    mo_form.bom_id = bom
    mo_form.product_qty = 5
    mo = mo_form.save()
    mo.action_confirm()
    mo.action_assign()
    mo_form = Form(mo)
    mo_form.qty_producing = 5
    mo = mo_form.save()
    mo.button_mark_done()
    assert mo.state == 'done', mo.state
    return mo


mo = check('manufacturing order to done', run_mo)

# ------------------------------------------------------------------
# Every layout of both wizards: screen HTML + xlsx.
# ------------------------------------------------------------------
def render(model, layout, expect):
    wizard = env[model].create({'layout': layout})
    html = wizard.get_report_html()
    for token in expect:
        assert token in html, 'missing %r in %s/%s' % (token, model, layout)
    wizard.action_export_xlsx()
    assert wizard.xlsx_file, 'no xlsx produced'
    return html


for layout, expect in (
        ('summary', ['BẢNG TỔNG HỢP CHI TIẾT VẬT LIỆU', 'S11-DN', 'NVLS']),
        ('card', ['THẺ KHO', 'S12-DN', 'NVLS']),
        ('ledger', ['SỔ CHI TIẾT VẬT LIỆU', 'S10-DN', 'TK đối ứng', 'NVLS'])):
    check('stock wizard %s' % layout,
          lambda l=layout, e=expect: render('vn.stock.card.wizard', l, e))

for layout, expect in (
        ('product', ['CHI PHÍ SẢN XUẤT', 'TPS']),
        ('order', ['CHI PHÍ SẢN XUẤT']),
        ('cost_card', ['THẺ TÍNH GIÁ THÀNH', 'S37-DN'])):
    check('mrp wizard %s' % layout,
          lambda l=layout, e=expect: render('vn.production.cost.wizard', l, e))


def counterpart_shows():
    wizard = env['vn.stock.card.wizard'].create({'layout': 'ledger'})
    html = wizard.get_report_html()
    # The MO consumption posts 152 -> counterpart; with our category wiring the
    # issue's counterpart is the output account 632.
    assert '632' in html, 'no counterpart account rendered'


check('S10-DN counterpart column carries an account', counterpart_shows)


def expense_ledger():
    """S36-DN over the demo entries plus the order this script just ran.

    The demo dataset moved 180,000,000 through account 154 in February 2026
    (issue from 152, then transfer to 155), and the manufacturing order above
    posted its consumption to 632 against 152. Both must land in the right
    breakdown column.
    """
    wizard = env['vn.expense.ledger.wizard'].create({})
    html = wizard.get_report_html()
    assert 'SỔ CHI PHÍ SẢN XUẤT, KINH DOANH' in html, 'form title missing'
    assert 'S36-DN' in html, 'form code missing'
    wizard.action_export_xlsx()
    assert wizard.xlsx_file, 'no xlsx produced'

    report = wizard._build_report()
    wip = next(g for g in report.groups if g.code.startswith('154'))
    assert '152' in wip.columns, wip.columns
    # Cross-check against the ledger itself rather than a hard-coded figure:
    # the demo generators also move account 154, and the point of the book is
    # exactly that it reconciles to the GL whatever is in it.
    gl_lines = env['account.move.line'].search([
        ('account_id', '=', wip.account_id),
        ('parent_state', '=', 'posted'),
        ('company_id', '=', company.id),
        ('date', '>=', wizard.date_from), ('date', '<=', wizard.date_to)])
    gl_debit = sum(gl_lines.mapped('debit'))
    gl_credit = sum(gl_lines.mapped('credit'))
    assert wip.debit_total == gl_debit, (wip.debit_total, gl_debit)
    assert wip.credit_total == gl_credit, (wip.credit_total, gl_credit)

    cogs = next(g for g in report.groups if g.code.startswith('632'))
    assert '152' in cogs.columns, cogs.columns


check('S36-DN expense ledger', expense_ledger)


def sales_ledger():
    """S35-DN: the demo invoices carry products, and the book must add up to
    the revenue account whatever else the demo posted."""
    wizard = env['vn.sales.ledger.wizard'].create({})
    html = wizard.get_report_html()
    assert 'SỔ CHI TIẾT BÁN HÀNG' in html and 'S35-DN' in html, 'S35 header'
    wizard.action_export_xlsx()
    assert wizard.xlsx_file, 'no xlsx produced'

    report = wizard._build_report()
    assert report.groups, 'no sales at all'
    assert any(g.product for g in report.groups), 'no product-linked revenue'
    gl_lines = env['account.move.line'].search([
        ('account_id.code', '=like', '511%'),
        ('parent_state', '=', 'posted'),
        ('company_id', '=', company.id),
        ('date', '>=', wizard.date_from), ('date', '<=', wizard.date_to)])
    gl_revenue = sum(gl_lines.mapped('credit')) - sum(gl_lines.mapped('debit'))
    assert report.total_revenue == gl_revenue, (report.total_revenue,
                                                gl_revenue)


check('S35-DN sales ledger reconciles to 511', sales_ledger)


def material_allocation():
    """07-VT over the same books.

    The demo issue to production credited 152 against 154, and the order this
    script ran credited 152 against 632. Each must land in its own row of the
    152 column, and the column must reconcile to what actually left 152.
    """
    wizard = env['vn.material.allocation.wizard'].create({})
    html = wizard.get_report_html()
    assert 'BẢNG PHÂN BỔ NGUYÊN LIỆU' in html, 'form title missing'
    assert '07-VT' in html, 'form code missing'
    wizard.action_export_xlsx()
    assert wizard.xlsx_file, 'no xlsx produced'

    report = wizard._build_report()
    assert '152' in report.columns, report.columns
    column = report.columns.index('152')
    rows = {row.code: row.amounts[column] for row in report.rows}
    # The ledger demo issues 180M against 154; since Odoo 17 the MO demo
    # consumption lands there too (WIP), so 154 carries at least that.
    assert rows.get('154', 0) >= 180000000.0, rows
    assert rows.get('632') == 1000000.0, rows
    assert report.column_totals[column] == sum(rows.values()), report


check('07-VT material allocation', material_allocation)


def cost_card_figures():
    wizard = env['vn.production.cost.wizard'].create({'layout': 'cost_card'})
    result = wizard._service().generate(wizard._manufacturing_filter())
    assert result.success, result.errors
    row = next(r for r in result.data.rows if r.product.id == fin.id)
    assert row.finished_quantity == 5.0, row
    assert row.period_cost == 1000000.0, row       # 10 units * 100,000
    assert row.finished_value == 1000000.0, row
    assert row.closing_wip == 0.0, row
    assert row.imbalance == 0.0, row
    return row


check('S37-DN figures reconcile', cost_card_figures)


# ------------------------------------------------------------------
# Fixed assets (needs l10n_vn_asset_reports + OCA account_asset_management):
# one machine, monthly linear depreciation posted to today, all three
# layouts rendered and their figures reconciled against the posted lines.
# ------------------------------------------------------------------
def make_asset():
    def ensure_account(code, name):
        found = acc(code)
        if found:
            return found
        return env['account.account'].with_company(company).create({
            'code': code, 'name': name, 'account_type': 'asset_fixed',
        })

    profile = env['account.asset.profile'].create({
        'name': 'Máy móc thiết bị smoke',
        'account_asset_id': ensure_account(
            '211', 'Tài sản cố định hữu hình').id,
        'account_depreciation_id': ensure_account('214', 'Hao mòn TSCĐ').id,
        'account_expense_depreciation_id': acc('642').id,
        'journal_id': env['account.journal'].search(
            [('company_id', '=', company.id), ('type', '=', 'general')],
            limit=1).id,
        'method': 'linear',
        'method_number': 5,
        'method_time': 'year',
        'method_period': 'month',
    })
    asset = env['account.asset'].create({
        'name': 'Máy CNC smoke',
        'code': 'TSCD-S01',
        'profile_id': profile.id,
        'purchase_value': 120000000.0,
        'date_start': '2026-01-01',
    })
    asset.compute_depreciation_board()
    asset.validate()
    asset._compute_entries(date.today())
    return asset


asset = None


def build_asset():
    global asset
    asset = make_asset()
    posted = asset.depreciation_line_ids.filtered(
        lambda l: l.type == 'depreciate' and l.move_id)
    assert posted, 'no depreciation was posted'
    return asset


check('asset with posted depreciation', build_asset)


def asset_reports():
    posted_total = sum(
        asset.depreciation_line_ids.filtered(
            lambda l: l.type == 'depreciate' and l.move_id).mapped('amount'))

    wizard = env['vn.asset.report.wizard'].create({'layout': 'register'})
    html = wizard.get_report_html()
    assert 'SỔ TÀI SẢN CỐ ĐỊNH' in html and 'S21-DN' in html, 'S21 header'
    wizard.action_export_xlsx()
    report = wizard._build_report()
    row = next(r for g in report.groups for r in g.rows
               if r.asset.id == asset.id)
    assert row.accumulated == posted_total, (row.accumulated, posted_total)
    assert row.residual == 120000000.0 - posted_total, row
    assert row.asset.annual_rate == 20.0, row.asset.annual_rate

    wizard = env['vn.asset.report.wizard'].create({'layout': 'card'})
    html = wizard.get_report_html()
    assert 'THẺ TÀI SẢN CỐ ĐỊNH' in html and 'S23-DN' in html, 'S23 header'
    wizard.action_export_xlsx()
    card = next(c for c in wizard._build_report().cards
                if c.asset.id == asset.id)
    assert card.years and card.years[-1].cumulative == posted_total, card.years

    # Restricted to this script's own asset: the demo generators post their
    # own depreciation and the totals below are per-asset statements.
    wizard = env['vn.asset.report.wizard'].create({
        'layout': 'allocation', 'asset_ids': [(6, 0, asset.ids)]})
    html = wizard.get_report_html()
    assert 'BẢNG TÍNH VÀ PHÂN BỔ KHẤU HAO' in html, '06-TSCD header'
    wizard.action_export_xlsx()
    report = wizard._build_report()
    assert '642' in report.columns, report.columns
    assert report.grand_total == posted_total, report
    assert report.summary.increase == posted_total, report.summary
    assert report.summary.imbalance == 0.0, report.summary


check('TSCD reports S21/S23/06 reconcile', asset_reports)

print('=' * 60)
for status, label, detail in RESULTS:
    print('%s  %s  %s' % (status, label, detail))
print('=' * 60)
failures = [r for r in RESULTS if r[0] == 'FAIL']
print('SMOKE RESULT: %s (%d/%d passed)' % (
    'FAIL' if failures else 'PASS', len(RESULTS) - len(failures), len(RESULTS)))
