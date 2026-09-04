# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Demo journal entries for a Vietnamese furniture SME.

One implementation, two entry points: the ``demo/`` data file calls it at module
install, and ``scripts/load_demo_data.py`` calls the same method against an
existing database. Nothing is duplicated between them.

The dataset is built to exercise the parts of the Ledger Engine that are easy to
get wrong, rather than to look plentiful:

* Entries in **two fiscal years**, so the Sổ Cái shows a balance-sheet account
  carrying 2025 forward while revenue resets on 1 January.
* A year-end closing entry to 421, so the Bảng cân đối phát sinh actually
  balances. Delete that one entry and the report's imbalance warning appears —
  which is the behaviour, not a bug.
* Three-line VAT entries, so the "TK đối ứng" column has to render ``511, 3331``
  rather than a single counterpart.
* A partly-collected receivable, leaving a partner balance for aging work later.
* Real **customer and supplier invoices carrying VAT**, so the Bảng kê hoá đơn
  has something to list. Hand-written journal entries with a manual 3331 line
  look right on the Sổ Cái but carry no ``tax_line_id``, and the VAT listings
  read tax lines — which is why the earlier dataset left those two reports
  empty.

Accounts are resolved by code prefix and created when missing, so the script
works whether or not ``l10n_vn`` is installed.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

DEMO_REF_PREFIX = 'VAS-DEMO'

# code -> (name, account type xmlid, reconcile)
ACCOUNT_SPECS = {
    '111': ('Tiền mặt', 'account.data_account_type_liquidity', False),
    '112': ('Tiền gửi ngân hàng', 'account.data_account_type_liquidity', False),
    '131': ('Phải thu của khách hàng',
            'account.data_account_type_receivable', True),
    '133': ('Thuế GTGT được khấu trừ',
            'account.data_account_type_current_assets', False),
    '152': ('Nguyên liệu, vật liệu',
            'account.data_account_type_current_assets', False),
    '154': ('Chi phí SXKD dở dang',
            'account.data_account_type_current_assets', False),
    '155': ('Thành phẩm', 'account.data_account_type_current_assets', False),
    '331': ('Phải trả cho người bán',
            'account.data_account_type_payable', True),
    '3331': ('Thuế GTGT phải nộp',
             'account.data_account_type_current_liabilities', False),
    '411': ('Vốn đầu tư của chủ sở hữu',
            'account.data_account_type_equity', False),
    '421': ('Lợi nhuận sau thuế chưa phân phối',
            'account.data_account_type_equity', False),
    '511': ('Doanh thu bán hàng và cung cấp dịch vụ',
            'account.data_account_type_revenue', False),
    '632': ('Giá vốn hàng bán',
            'account.data_account_type_direct_costs', False),
    '642': ('Chi phí quản lý kinh doanh',
            'account.data_account_type_expenses', False),
}

PARTNERS = {
    'truong_thanh': ('Công ty TNHH Gỗ Trường Thành', '0301234567'),
    'hoa_binh': ('Đại lý Nội thất Hoà Bình', '0102345678'),
    'an_cuong': ('Công ty CP Vật liệu An Cường', '0303456789'),
}

#: (ref, kind, amount, rate, partner) — invoices dated March onward so they do
#: not disturb the opening balances the ledger reports are documented against.
INVOICE_SPECS = [
    ('AA/26E0001', 'out_invoice', '2026-03-05', 300000000, 10, 'hoa_binh',
     'Bộ bàn ăn gỗ sồi 6 ghế'),
    ('AA/26E0002', 'out_invoice', '2026-03-28', 150000000, 10, 'truong_thanh',
     'Ghế văn phòng lưng lưới'),
    ('AA/26E0003', 'out_invoice', '2026-04-18', 80000000, 5, 'hoa_binh',
     'Giường ngủ gỗ công nghiệp'),
    ('AA/26E0004', 'out_refund', '2026-04-25', 20000000, 10, 'hoa_binh',
     'Điều chỉnh giảm do hàng lỗi'),
    ('AA/26E0005', 'out_invoice', '2026-05-14', 220000000, 10, 'hoa_binh',
     'Tủ quần áo 4 cánh'),
    ('BB/26E0201', 'in_invoice', '2026-03-02', 180000000, 10, 'an_cuong',
     'Ván MDF phủ melamine'),
    ('BB/26E0202', 'in_invoice', '2026-04-08', 90000000, 10, 'truong_thanh',
     'Gỗ sồi xẻ sấy'),
    ('BB/26E0203', 'in_invoice', '2026-05-06', 40000000, 5, 'an_cuong',
     'Phụ kiện bản lề, ray trượt'),
]


class VnDemoDataGenerator(models.AbstractModel):
    _name = 'vn.demo.data.generator'
    _description = 'Vietnam VAS Demo Data Generator'

    # ==================================================================
    # Entry point
    # ==================================================================
    @api.model
    def generate(self, company=None, clear=True):
        """Create the demo ledger. Returns a summary dict.

        Idempotent: every move carries a ``VAS-DEMO/...`` reference, and by
        default the previous batch is removed first, so the script can be re-run
        without piling up duplicates.
        """
        company = company or self.env.company
        if clear:
            self._clear(company)

        journal = self._ensure_journal(company)
        accounts = self._ensure_accounts(company)
        partners = self._ensure_partners(company, accounts)

        moves = self.env['account.move']
        for spec in self._entry_specs():
            moves |= self._create_entry(company, journal, accounts, partners,
                                        spec)

        invoices = self._create_invoices(company, accounts, partners)
        moves |= invoices
        moves.action_post()

        return {
            'company': company.name,
            'journal': journal.code,
            'moves': len(moves),
            'invoices': len(invoices),
            'lines': sum(len(m.line_ids) for m in moves),
            'accounts': len(accounts),
            'date_range': (min(m.date for m in moves),
                           max(m.date for m in moves)),
        }

    # ==================================================================
    # The dataset
    # ==================================================================
    def _entry_specs(self):
        """(ref, date, label, [(account_code, debit, credit, partner_key)])."""
        return [
            # ---------------- Năm 2025 ----------------
            ('2025/01', '2025-03-01', 'Chủ sở hữu góp vốn bằng tiền gửi', [
                ('112', 800000000, 0, None),
                ('411', 0, 800000000, None),
            ]),
            ('2025/02', '2025-06-15', 'Mua gỗ nguyên liệu nhập kho', [
                ('152', 300000000, 0, None),
                ('133', 30000000, 0, None),
                ('331', 0, 330000000, 'truong_thanh'),
            ]),
            ('2025/03', '2025-06-20', 'Xuất kho nguyên liệu cho sản xuất', [
                ('154', 300000000, 0, None),
                ('152', 0, 300000000, None),
            ]),
            ('2025/04', '2025-07-31', 'Nhập kho thành phẩm bàn ghế', [
                ('155', 300000000, 0, None),
                ('154', 0, 300000000, None),
            ]),
            ('2025/05', '2025-08-20', 'Bán bộ bàn ăn cho đại lý', [
                ('131', 495000000, 0, 'hoa_binh'),
                ('511', 0, 450000000, None),
                ('3331', 0, 45000000, None),
            ]),
            ('2025/06', '2025-08-20', 'Giá vốn lô hàng bán tháng 8', [
                ('632', 270000000, 0, None),
                ('155', 0, 270000000, None),
            ]),
            # Cố ý thu thiếu 150 triệu: số dư 131 phải chuyển sang 2026 thì
            # mới thấy được tài khoản bảng cân đối luỹ kế qua năm.
            ('2025/07', '2025-09-30', 'Khách hàng thanh toán một phần', [
                ('112', 345000000, 0, 'hoa_binh'),
                ('131', 0, 345000000, 'hoa_binh'),
            ]),
            ('2025/08', '2025-10-15', 'Chi phí quản lý quý III', [
                ('642', 60000000, 0, None),
                ('112', 0, 60000000, None),
            ]),
            # Kết chuyển cuối năm. Bỏ hai bút toán này đi thì Bảng cân đối
            # phát sinh năm 2026 sẽ lệch, và cảnh báo trên báo cáo hiện ra.
            ('2025/90', '2025-12-31', 'Kết chuyển doanh thu năm 2025', [
                ('511', 450000000, 0, None),
                ('421', 0, 450000000, None),
            ]),
            ('2025/91', '2025-12-31', 'Kết chuyển chi phí năm 2025', [
                ('421', 330000000, 0, None),
                ('632', 0, 270000000, None),
                ('642', 0, 60000000, None),
            ]),

            # ---------------- Năm 2026 ----------------
            ('2026/01', '2026-01-05', 'Mua ván MDF nhập kho', [
                ('152', 200000000, 0, None),
                ('133', 20000000, 0, None),
                ('331', 0, 220000000, 'an_cuong'),
            ]),
            ('2026/02', '2026-01-12', 'Thanh toán tiền hàng cho nhà cung cấp', [
                ('331', 220000000, 0, 'an_cuong'),
                ('112', 0, 220000000, None),
            ]),
            # Bán nốt tồn kho đầu năm. Bút toán này tồn tại để khi đổi kỳ
            # sang 01/03/2026 thì TK 511 hiện số dư đầu kỳ của tháng 1-2.
            ('2026/02b', '2026-01-28', 'Bán ghế tồn kho đầu năm', [
                ('131', 55000000, 0, 'hoa_binh'),
                ('511', 0, 50000000, None),
                ('3331', 0, 5000000, None),
            ]),
            ('2026/02c', '2026-01-28', 'Giá vốn ghế tồn kho', [
                ('632', 30000000, 0, None),
                ('155', 0, 30000000, None),
            ]),
            ('2026/03', '2026-02-20', 'Xuất kho vật liệu cho phân xưởng', [
                ('154', 180000000, 0, None),
                ('152', 0, 180000000, None),
            ]),
            ('2026/04', '2026-02-28', 'Nhập kho thành phẩm tủ quần áo', [
                ('155', 180000000, 0, None),
                ('154', 0, 180000000, None),
            ]),
            ('2026/05', '2026-03-10', 'Bán tủ quần áo cho đại lý Hoà Bình', [
                ('131', 330000000, 0, 'hoa_binh'),
                ('511', 0, 300000000, None),
                ('3331', 0, 30000000, None),
            ]),
            ('2026/06', '2026-03-10', 'Giá vốn lô tủ quần áo', [
                ('632', 180000000, 0, None),
                ('155', 0, 180000000, None),
            ]),
            # Thu một phần, cố ý để lại số dư 131 cho báo cáo công nợ sau này.
            ('2026/07', '2026-03-25', 'Khách hàng trả trước một phần', [
                ('111', 200000000, 0, 'hoa_binh'),
                ('131', 0, 200000000, 'hoa_binh'),
            ]),
            ('2026/08', '2026-04-05', 'Chi phí quản lý tháng 4', [
                ('642', 45000000, 0, None),
                ('111', 0, 45000000, None),
            ]),
            ('2026/09', '2026-05-20', 'Bán lô ghế văn phòng', [
                ('131', 165000000, 0, 'truong_thanh'),
                ('511', 0, 150000000, None),
                ('3331', 0, 15000000, None),
            ]),
            ('2026/10', '2026-06-01', 'Nộp thuế GTGT quý I', [
                ('3331', 30000000, 0, None),
                ('112', 0, 30000000, None),
            ]),
        ]

    # ==================================================================
    # Setup helpers
    # ==================================================================
    def _clear(self, company):
        # Invoices carry the statutory number in ``ref``, so they are marked in
        # ``narration`` instead. Both are cleared together.
        moves = self.env['account.move'].search([
            ('company_id', '=', company.id),
            '|',
            ('ref', '=like', DEMO_REF_PREFIX + '%'),
            ('narration', 'ilike', DEMO_REF_PREFIX),
        ])
        if moves:
            moves.filtered(lambda m: m.state == 'posted').button_draft()
            moves.with_context(force_delete=True).unlink()

    def _ensure_journal(self, company):
        journal = self.env['account.journal'].search([
            ('company_id', '=', company.id),
            ('type', '=', 'general'),
        ], limit=1)
        if journal:
            return journal
        return self.env['account.journal'].create({
            'name': 'Nhật ký chung',
            'code': 'NKC',
            'type': 'general',
            'company_id': company.id,
        })

    def _ensure_accounts(self, company):
        """Resolve by code prefix, create when absent. -> {code: account}."""
        Account = self.env['account.account']
        accounts = {}
        for code, (name, type_xmlid, reconcile) in ACCOUNT_SPECS.items():
            existing = Account.search([
                ('company_id', '=', company.id),
                ('code', '=like', code + '%'),
            ], order='code', limit=1)
            if existing:
                accounts[code] = existing
                continue

            account_type = self.env.ref(type_xmlid, raise_if_not_found=False)
            if not account_type:
                raise UserError(_(
                    "Account type %s not found; is the 'account' module "
                    "installed?") % type_xmlid)
            accounts[code] = Account.create({
                'code': code,
                'name': name,
                'user_type_id': account_type.id,
                'reconcile': reconcile,
                'company_id': company.id,
            })
        return accounts

    def _ensure_partners(self, company, accounts):
        Partner = self.env['res.partner']
        partners = {}
        for key, (name, vat) in PARTNERS.items():
            partner = Partner.search([('name', '=', name)], limit=1)
            if not partner:
                partner = Partner.create({
                    'name': name, 'company_type': 'company'})
            # The tax code is what the Bảng kê prints; set it even on partners
            # that already existed.
            if not partner.vat:
                partner.vat = vat
            # On a database without a chart of accounts the company-dependent
            # receivable/payable properties are empty, and the payment-term
            # line Odoo balances the invoice with would then carry no account,
            # violating check_accountable_required_fields at demo install.
            partner_c = partner.with_company(company)
            if not partner_c.property_account_receivable_id:
                partner_c.property_account_receivable_id = accounts['131']
            if not partner_c.property_account_payable_id:
                partner_c.property_account_payable_id = accounts['331']
            partners[key] = partner
        return partners

    # ==================================================================
    # Invoices carrying VAT
    # ==================================================================
    def _ensure_tax(self, company, accounts, rate, direction):
        """Find a percentage VAT tax, creating one only if the chart has none.

        Repartition lines are written explicitly so the tax posts to 3331 for
        sales and 133 for purchases. Relying on the default would send the tax
        wherever the chart happens to point, and the VAT listing reads the tax
        line, not the base line.
        """
        Tax = self.env['account.tax']
        existing = Tax.search([
            ('company_id', '=', company.id),
            ('type_tax_use', '=', direction),
            ('amount_type', '=', 'percent'),
            ('amount', '=', rate),
        ], limit=1)
        if existing:
            return existing

        tax_account = accounts['3331'] if direction == 'sale' else accounts['133']
        repartition = [
            (0, 0, {'factor_percent': 100, 'repartition_type': 'base'}),
            (0, 0, {'factor_percent': 100, 'repartition_type': 'tax',
                    'account_id': tax_account.id}),
        ]
        return Tax.create({
            'name': 'Thuế GTGT %d%% %s' % (
                rate, 'đầu ra' if direction == 'sale' else 'đầu vào'),
            'amount_type': 'percent',
            'amount': rate,
            'type_tax_use': direction,
            'company_id': company.id,
            'invoice_repartition_line_ids': repartition,
            'refund_repartition_line_ids': [
                (0, 0, {'factor_percent': 100, 'repartition_type': 'base'}),
                (0, 0, {'factor_percent': 100, 'repartition_type': 'tax',
                        'account_id': tax_account.id}),
            ],
        })

    def _ensure_invoice_journal(self, company, kind):
        journal_type = 'sale' if kind.startswith('out') else 'purchase'
        journal = self.env['account.journal'].search([
            ('company_id', '=', company.id),
            ('type', '=', journal_type),
        ], limit=1)
        if journal:
            return journal
        return self.env['account.journal'].create({
            'name': ('Bán hàng' if journal_type == 'sale' else 'Mua hàng'),
            'code': 'BH' if journal_type == 'sale' else 'MH',
            'type': journal_type,
            'company_id': company.id,
        })

    def _ensure_invoice_product(self, label):
        """A non-stocked product per invoice line, so the Sổ chi tiết bán
        hàng (S35-DN) has something to group by.

        Type ``consu`` on purpose: these carry no inventory and need no stock
        module — they exist so the 511 lines are attributable to a product,
        which is the whole premise of that book.
        """
        Product = self.env['product.product']
        product = Product.search([('name', '=', label)], limit=1)
        if product:
            return product
        return Product.create({'name': label, 'type': 'consu'})

    def _create_invoices(self, company, accounts, partners):
        """Customer and supplier invoices with VAT attached.

        The invoice number goes into ``ref`` because that is where the VAT
        listing looks for it — Vietnamese e-invoice providers write the
        statutory number there rather than into the journal entry name.
        """
        Move = self.env['account.move']
        invoices = Move
        for ref, kind, when, amount, rate, partner_key, label in INVOICE_SPECS:
            direction = 'sale' if kind.startswith('out') else 'purchase'
            tax = self._ensure_tax(company, accounts, rate, direction)
            income = accounts['511'] if direction == 'sale' else accounts['152']
            invoices |= Move.create({
                'move_type': kind,
                'partner_id': partners[partner_key].id,
                'invoice_date': fields.Date.to_date(when),
                'date': fields.Date.to_date(when),
                'ref': ref,
                'narration': DEMO_REF_PREFIX,
                'journal_id': self._ensure_invoice_journal(company, kind).id,
                'company_id': company.id,
                'invoice_line_ids': [(0, 0, {
                    'name': label,
                    'product_id': self._ensure_invoice_product(label).id,
                    'quantity': 1.0,
                    'price_unit': amount,
                    'account_id': income.id,
                    'tax_ids': [(6, 0, tax.ids)],
                })],
            })
        return invoices

    def _create_entry(self, company, journal, accounts, partners, spec):
        ref, date, label, lines = spec
        move_lines = []
        for code, debit, credit, partner_key in lines:
            move_lines.append((0, 0, {
                'account_id': accounts[code].id,
                'partner_id': partners[partner_key].id if partner_key else False,
                'name': label,
                'debit': debit,
                'credit': credit,
            }))
        return self.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.to_date(date),
            'ref': '%s/%s' % (DEMO_REF_PREFIX, ref),
            'journal_id': journal.id,
            'company_id': company.id,
            'line_ids': move_lines,
        })
