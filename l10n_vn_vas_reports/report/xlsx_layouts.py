# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""Sheet layouts, one per DTO shape rather than one per report.

Sixteen reports share seven shapes, so seven functions cover the lot. That is
the same reuse that let the partner ledger borrow the general ledger's template
and the VAT declaration borrow the financial statement's: the shape of the data
is what varies, not the report name.

Each function returns the sheet description that ``xlsx_writer`` consumes. No
Odoo here — these read DTOs and produce plain dicts, so they can be exercised
without a server.
"""

TEXT, DATE, NUMBER, MONEY = 'text', 'date', 'number', 'money'


def _heading(report, doc, filter_summary):
    """Provenance lines, matching what the printed header carries.

    A spreadsheet outlives the screen it was exported from and gets mailed
    around, so it has to say which company, which period and which filters
    produced it. Anything else is a file nobody can check.
    """
    lines = []
    if doc.get('company'):
        lines.append('Đơn vị: %s' % doc['company'])
    if doc.get('period'):
        lines.append(doc['period'])
    if doc.get('currency'):
        lines.append('Đơn vị tiền tệ: %s' % doc['currency'])
    for label, value in filter_summary or ():
        lines.append('%s: %s' % (label, value))
    return lines


# ======================================================================
# LedgerDTO — Sổ Cái, Sổ chi tiết công nợ, Sổ quỹ, Nhật ký chung
# ======================================================================
def ledger(report, doc, filter_summary):
    columns = [
        ('Ngày', 12, DATE),
        ('Số hiệu chứng từ', 18, TEXT),
        ('Diễn giải', 45, TEXT),
        ('Số hiệu TK', 12, TEXT),
        ('TK đối ứng', 14, TEXT),
        ('Nợ', 16, MONEY),
        ('Có', 16, MONEY),
        ('Số dư', 16, MONEY),
    ]
    rows = []
    for group in report.groups:
        if group.display_name:
            rows.append(('group', [None, None, group.display_name,
                                   None, None, None, None, None]))
            rows.append(('italic', [None, None, 'Số dư đầu kỳ', None, None,
                                    group.opening.debit_balance or None,
                                    group.opening.credit_balance or None,
                                    group.opening.balance]))
        for line in group.lines:
            rows.append(('', [
                line.date, line.move_name, line.label,
                line.account_code, line.counterpart_label,
                line.debit or None, line.credit or None,
                line.running_balance,
            ]))
        if group.display_name:
            rows.append(('total', [None, None, 'Cộng phát sinh / Số dư cuối kỳ',
                                   None, None,
                                   group.movement.debit, group.movement.credit,
                                   group.closing.balance]))
    return [{
        'name': doc.get('title') or 'So',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': columns,
        'rows': rows,
    }]


# ======================================================================
# TrialBalanceDTO — Bảng cân đối số phát sinh
# ======================================================================
def trial_balance(report, doc, filter_summary):
    columns = [
        ('Số hiệu TK', 14, TEXT), ('Tên tài khoản', 45, TEXT),
        ('Dư đầu kỳ Nợ', 16, MONEY), ('Dư đầu kỳ Có', 16, MONEY),
        ('Phát sinh Nợ', 16, MONEY), ('Phát sinh Có', 16, MONEY),
        ('Dư cuối kỳ Nợ', 16, MONEY), ('Dư cuối kỳ Có', 16, MONEY),
    ]
    rows = [('', [row.code, row.name,
                  row.opening.debit_balance or None,
                  row.opening.credit_balance or None,
                  row.movement.debit or None, row.movement.credit or None,
                  row.closing.debit_balance or None,
                  row.closing.credit_balance or None])
            for row in report.rows]
    rows.append(('total', [None, 'Tổng cộng',
                           report.total_opening.debit_balance,
                           report.total_opening.credit_balance,
                           report.total_movement.debit,
                           report.total_movement.credit,
                           report.total_closing.debit_balance,
                           report.total_closing.credit_balance]))
    return [{
        'name': 'Bang can doi phat sinh',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': columns, 'rows': rows,
    }]


# ======================================================================
# AgingDTO — Bảng tổng hợp công nợ theo tuổi nợ
# ======================================================================
def aging(report, doc, filter_summary):
    # The ageing bands are mapping data, so the columns follow them rather than
    # being fixed here: change the buckets and the workbook follows.
    columns = [
        ('Đối tượng / Chứng từ', 40, TEXT),
        ('Ngày CT', 12, DATE), ('Hạn thanh toán', 14, DATE),
        ('Số ngày quá hạn', 12, NUMBER), ('Tổng nợ', 16, MONEY),
    ] + [(bucket.label, 16, MONEY) for bucket in report.buckets]

    rows = []
    for group in report.groups:
        rows.append(('group', [group.partner_name or 'Không xác định',
                               None, None, None, group.total]
                     + list(group.amounts)))
        for line in group.lines:
            cells = [line.move_name, line.date, line.due_date,
                     line.days_overdue if line.days_overdue > 0 else None,
                     line.residual]
            cells += [line.residual if index == line.bucket_index else None
                      for index in range(len(report.buckets))]
            rows.append(('', cells))
    rows.append(('total', ['Tổng cộng', None, None, None, report.grand_total]
                 + list(report.totals)))
    return [{
        'name': 'Cong no theo tuoi no',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': columns, 'rows': rows,
    }]


# ======================================================================
# FinancialStatementDTO — B01, B02, B03, tờ khai 01/GTGT
# ======================================================================
def statement(report, doc, filter_summary):
    columns = [('CHỈ TIÊU', 55, TEXT), ('Mã số', 10, TEXT),
               ('Thuyết minh', 14, TEXT), ('Số tiền', 20, MONEY)]
    if report.comparative:
        columns.append(('Kỳ trước', 20, MONEY))

    rows = []
    for line in report.lines:
        # Indentation is data on the DTO, so it survives into the workbook
        # instead of being flattened into an undifferentiated list.
        cells = ['    ' * line.level + line.name, line.code, line.note_ref,
                 line.amount]
        if report.comparative:
            cells.append(line.previous_amount or 0.0)
        rows.append(('total' if line.bold else '', cells))

    sheets = [{
        'name': doc.get('title') or 'Bao cao',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': columns, 'rows': rows,
    }]
    if report.unmapped:
        sheets.append(_unmapped_sheet(report))
    return sheets


def _unmapped_sheet(report):
    """The coverage diagnostic gets its own tab rather than a footnote.

    On paper it sits under the statement; in a workbook it is a list to work
    through, so it belongs where it can be sorted and ticked off.
    """
    return {
        'name': 'TK chua anh xa',
        'title': 'Tài khoản có số dư nhưng chưa được ánh xạ',
        'heading': [],
        'columns': [('Số hiệu TK', 14, TEXT), ('Tên tài khoản', 45, TEXT),
                    ('Số dư', 20, MONEY)],
        'rows': [('', [account.code, account.name, account.balance])
                 for account in report.unmapped],
    }


# ======================================================================
# VatListingDTO — Bảng kê hoá đơn
# ======================================================================
def vat_listing(report, doc, filter_summary):
    columns = [('STT', 8, NUMBER), ('Số hoá đơn', 20, TEXT),
               ('Ngày', 12, DATE), ('Tên người bán / người mua', 40, TEXT),
               ('Mã số thuế', 16, TEXT), ('Giá trị chưa thuế', 18, MONEY),
               ('Tiền thuế', 16, MONEY)]
    rows = []
    for group in report.groups:
        rows.append(('group', [None, group.label, None, None, None,
                               group.base_total, group.tax_total]))
        for position, line in enumerate(group.lines, start=1):
            rows.append(('', [position, line.invoice_number, line.invoice_date,
                              line.partner_name, line.partner_vat,
                              line.base_amount, line.tax_amount]))
    rows.append(('total', [None, 'Tổng cộng (%s hoá đơn)' % report.invoice_count,
                           None, None, None,
                           report.base_total, report.tax_total]))
    return [{
        'name': 'Bang ke hoa don',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': columns, 'rows': rows,
    }]


# ======================================================================
# StockCardDTO — Nhập xuất tồn, Thẻ kho
# ======================================================================
def inventory(report, doc, filter_summary):
    detailed = any(group.lines for group in report.groups)
    columns = [
        ('Mã vật tư', 14, TEXT), ('Tên vật tư, hàng hoá', 40, TEXT),
        ('ĐVT', 10, TEXT),
        ('Tồn đầu SL', 12, NUMBER), ('Tồn đầu giá trị', 16, MONEY),
        ('Nhập SL', 12, NUMBER), ('Nhập giá trị', 16, MONEY),
        ('Xuất SL', 12, NUMBER), ('Xuất giá trị', 16, MONEY),
        ('Tồn cuối SL', 12, NUMBER), ('Tồn cuối giá trị', 16, MONEY),
    ]
    rows = []
    for group in report.groups:
        rows.append(('group' if detailed else '', [
            group.product.code, group.product.name, group.product.uom_name,
            group.opening.quantity or None, group.opening.value or None,
            group.incoming.quantity or None, group.incoming.value or None,
            group.outgoing.quantity or None, group.outgoing.value or None,
            group.closing.quantity or None, group.closing.value or None,
        ]))
        for line in group.lines:
            rows.append(('', [
                None, line.reference, line.description,
                None, None,
                line.incoming.quantity or None, line.incoming.value or None,
                line.outgoing.quantity or None, line.outgoing.value or None,
                line.running.quantity, line.running.value,
            ]))
    rows.append(('total', [None, 'Tổng giá trị tồn cuối kỳ'] + [None] * 8
                 + [report.totals.value]))
    return [{
        'name': 'Nhap xuat ton',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': columns, 'rows': rows,
    }]


# ======================================================================
# SalesLedgerDTO — Sổ chi tiết bán hàng (S35-DN)
# ======================================================================
def sales_ledger(report, doc, filter_summary):
    columns = [
        ('Ngày', 12, DATE), ('Số hiệu chứng từ', 18, TEXT),
        ('Diễn giải', 40, TEXT), ('TK đối ứng', 14, TEXT),
        ('Số lượng', 12, NUMBER), ('Đơn giá', 16, MONEY),
        ('Doanh thu', 18, MONEY), ('Các khoản giảm trừ', 18, MONEY),
    ]
    rows = []
    for group in report.groups:
        rows.append(('group', [
            None, None,
            group.display_name or 'Doanh thu không gắn sản phẩm',
            None, None, None, group.revenue_total,
            group.deduction_total or None]))
        for line in group.lines:
            rows.append(('', [
                line.date, line.move_name, line.label,
                line.counterpart_label, line.quantity or None,
                line.unit_price or None, line.revenue or None,
                line.deduction or None]))
        rows.append(('total', [None, None, 'Cộng — doanh thu thuần', None,
                               group.quantity_total or None, None,
                               group.net_revenue, None]))
    rows.append(('total', [None, None, 'Tổng cộng doanh thu thuần', None,
                           None, None, report.total_net_revenue, None]))
    return [{
        'name': 'So chi tiet ban hang',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': columns, 'rows': rows,
    }]


# ======================================================================
# ExpenseLedgerDTO — Sổ chi phí sản xuất, kinh doanh (S36-DN)
# ======================================================================
def expense_ledger(report, doc, filter_summary):
    """One sheet per account: the "chia ra" columns differ between accounts,
    so a shared grid would be mostly blank cells."""
    sheets = []
    for group in report.groups:
        columns = [
            ('Ngày', 12, DATE), ('Số hiệu chứng từ', 18, TEXT),
            ('Diễn giải', 40, TEXT), ('TK đối ứng', 14, TEXT),
            ('Tổng số tiền (Nợ)', 18, MONEY),
        ] + [(code or 'Khác', 16, MONEY) for code in group.columns]

        rows = [('italic', [None, None, 'Số dư đầu kỳ', None,
                            group.opening.debit_balance
                            or -group.opening.credit_balance or None]
                 + [None] * len(group.columns))]
        for line in group.lines:
            rows.append(('', [line.date, line.move_name, line.label,
                              line.counterpart_label, line.debit]
                         + [amount or None for amount in line.amounts]))
        rows.append(('total', [None, None, 'Cộng phát sinh trong kỳ', None,
                               group.debit_total]
                     + [total or None for total in group.column_totals]))
        rows.append(('total', [None, None, 'Ghi Có TK %s' % group.code, None,
                               group.credit_total]
                     + [None] * len(group.columns)))
        rows.append(('total', [None, None, 'Số dư cuối kỳ', None,
                               group.closing.debit_balance
                               or -group.closing.credit_balance or None]
                     + [None] * len(group.columns)))

        sheets.append({
            'name': 'TK %s' % (group.code or group.account_id),
            'title': ('%s — %s' % (doc.get('form_title'), group.display_name)
                      if doc.get('form_title') else group.display_name),
            'heading': _heading(report, doc, filter_summary),
            'columns': columns,
            'rows': rows,
        })
    return sheets or [{
        'name': doc.get('title') or 'So chi phi SXKD',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': [('Diễn giải', 60, TEXT)],
        'rows': [('', ['Không có phát sinh nào trong kỳ đã chọn.'])],
    }]


# ======================================================================
# AllocationTableDTO — Bảng phân bổ NVL, CCDC (07-VT)
# ======================================================================
def allocation(report, doc, filter_summary):
    columns = ([('STT', 8, NUMBER),
                ('Đối tượng sử dụng (Ghi Nợ các TK)', 40, TEXT)]
               + [('Ghi Có TK %s' % code, 18, MONEY)
                  for code in report.columns]
               + [('Cộng', 18, MONEY)])
    rows = [('', [position + 1,
                  ('TK %s' % row.code) if row.code
                  else 'Khác (bút toán nhiều TK ghi Nợ)']
             + [amount or None for amount in row.amounts]
             + [row.total])
            for position, row in enumerate(report.rows)]
    rows.append(('total', [None, 'Cộng']
                 + [total or None for total in report.column_totals]
                 + [report.grand_total]))
    return [{
        'name': 'Bang phan bo NVL CCDC',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': columns, 'rows': rows,
    }]


# ======================================================================
# StockCardDTO — Sổ chi tiết vật liệu, dụng cụ, sản phẩm, hàng hóa (S10-DN)
# ======================================================================
def stock_ledger(report, doc, filter_summary):
    """The stock card's shape with its value columns and TK đối ứng spelled
    out, which is what distinguishes S10-DN from S12-DN."""
    columns = [
        ('Ngày', 12, DATE), ('Chứng từ', 18, TEXT), ('Diễn giải', 40, TEXT),
        ('TK đối ứng', 12, TEXT), ('Đơn giá', 14, MONEY),
        ('Nhập SL', 12, NUMBER), ('Nhập thành tiền', 16, MONEY),
        ('Xuất SL', 12, NUMBER), ('Xuất thành tiền', 16, MONEY),
        ('Tồn SL', 12, NUMBER), ('Tồn thành tiền', 16, MONEY),
    ]
    rows = []
    for group in report.groups:
        rows.append(('group', [None, None, group.product.display_name,
                               None, None, None, None, None, None,
                               group.closing.quantity, group.closing.value]))
        rows.append(('italic', [None, None, 'Tồn đầu kỳ', None, None,
                                None, None, None, None,
                                group.opening.quantity, group.opening.value]))
        for line in group.lines:
            rows.append(('', [
                line.date, line.reference, line.description,
                line.counterpart, line.unit_cost,
                line.incoming.quantity or None, line.incoming.value or None,
                line.outgoing.quantity or None, line.outgoing.value or None,
                line.running.quantity, line.running.value,
            ]))
        rows.append(('total', [None, None, 'Cộng phát sinh / Tồn cuối kỳ',
                               None, None,
                               group.incoming.quantity, group.incoming.value,
                               group.outgoing.quantity, group.outgoing.value,
                               group.closing.quantity, group.closing.value]))
    rows.append(('total', [None, None, 'Tổng giá trị tồn cuối kỳ']
                 + [None] * 7 + [report.totals.value]))
    return [{
        'name': 'So chi tiet vat lieu',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': columns, 'rows': rows,
    }]


# ======================================================================
# CostCardDTO — Thẻ tính giá thành sản phẩm, dịch vụ (S37-DN)
# ======================================================================
def cost_card(report, doc, filter_summary):
    columns = [
        ('Mã SP', 14, TEXT), ('Tên sản phẩm, dịch vụ', 40, TEXT),
        ('ĐVT', 10, TEXT),
        ('Dở dang đầu kỳ', 18, MONEY), ('Phát sinh trong kỳ', 18, MONEY),
        ('Giá thành trong kỳ', 18, MONEY), ('Dở dang cuối kỳ', 18, MONEY),
        ('SL hoàn thành', 14, NUMBER), ('Giá thành đơn vị', 18, MONEY),
        ('Chênh lệch', 16, MONEY),
    ]
    rows = [('', [row.product.code, row.product.name, row.product.uom_name,
                  row.opening_wip or None, row.period_cost or None,
                  row.finished_value or None, row.closing_wip or None,
                  row.finished_quantity or None, row.unit_cost or None,
                  row.imbalance or None])
            for row in report.rows]
    rows.append(('total', [None, 'Tổng cộng', None,
                           report.total_opening_wip, report.total_period_cost,
                           report.total_finished_value,
                           report.total_closing_wip,
                           None, None, report.imbalance or None]))
    return [{
        'name': 'The tinh gia thanh',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': columns, 'rows': rows,
    }]


# ======================================================================
# ManufacturingCostDTO — Chi phí sản xuất
# ======================================================================
def production_cost(report, doc, filter_summary):
    product_sheet = {
        'name': 'Gia thanh theo san pham',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': [('Mã sản phẩm', 14, TEXT), ('Tên sản phẩm', 40, TEXT),
                    ('ĐVT', 10, TEXT), ('Số lệnh', 10, NUMBER),
                    ('Số lượng', 14, NUMBER), ('Chi phí NVL', 18, MONEY),
                    ('Giá trị nhập kho', 18, MONEY),
                    ('Giá thành đơn vị', 18, MONEY)],
        'rows': [('', [row.product.code, row.product.name,
                       row.product.uom_name, row.order_count,
                       row.output_quantity, row.material_cost,
                       row.output_value, row.unit_cost])
                 for row in report.products]
        + [('total', [None, 'Tổng cộng', None, None, None,
                      report.material_cost, report.output_value, None])],
    }
    order_sheet = {
        'name': 'Chi tiet theo lenh',
        'title': None,
        'heading': [],
        'columns': [('Lệnh sản xuất', 20, TEXT), ('Ngày hoàn thành', 14, DATE),
                    ('Sản phẩm', 40, TEXT), ('Số lượng', 14, NUMBER),
                    ('Chi phí NVL', 18, MONEY),
                    ('Giá trị nhập kho', 18, MONEY),
                    ('Chênh lệch', 16, MONEY),
                    ('Giá thành đơn vị', 18, MONEY)],
        'rows': [('', [row.production.name, row.production.date_finished,
                       row.production.product.display_name,
                       row.output_quantity, row.material_cost,
                       row.output_value, row.variance or None, row.unit_cost])
                 for row in report.orders],
    }
    return [product_sheet, order_sheet]


# ======================================================================
# Fixed assets — Sổ TSCĐ (S21-DN), Thẻ TSCĐ (S23-DN), 06-TSCĐ
# ======================================================================
def asset_register(report, doc, filter_summary):
    columns = [
        ('STT', 8, NUMBER), ('Tên, đặc điểm, ký hiệu TSCĐ', 40, TEXT),
        ('Số hiệu TSCĐ', 14, TEXT), ('Chứng từ ghi tăng', 18, TEXT),
        ('Tháng, năm đưa vào SD', 16, DATE), ('Nước sản xuất', 14, TEXT),
        ('Nguyên giá', 18, MONEY), ('Tỷ lệ KH năm (%)', 12, NUMBER),
        ('Khấu hao luỹ kế', 18, MONEY), ('Giá trị còn lại', 18, MONEY),
        ('Ngày ghi giảm', 14, DATE),
    ]
    rows, position = [], 0
    for group in report.groups:
        rows.append(('group', [None, group.profile.name, None, None, None,
                               None, group.total_purchase, None,
                               group.total_accumulated, group.total_residual,
                               None]))
        for row in group.rows:
            position += 1
            rows.append(('', [position, row.asset.name, row.asset.code,
                              row.asset.acquisition_ref, row.asset.date_start,
                              None, row.asset.purchase_value,
                              row.asset.annual_rate or None,
                              row.accumulated or None, row.residual,
                              row.asset.date_remove]))
    rows.append(('total', [None, 'Tổng cộng', None, None, None, None,
                           report.total_purchase, None,
                           report.total_accumulated, report.total_residual,
                           None]))
    return [{
        'name': 'So TSCD',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': columns, 'rows': rows,
    }]


def asset_card(report, doc, filter_summary):
    """One sheet per asset — a Thẻ TSCĐ is one card per asset on paper too."""
    sheets = []
    for index, card in enumerate(report.cards):
        rows = [
            ('italic', [None, 'Nhóm TSCĐ',
                        card.profile.name if card.profile else '']),
            ('italic', [None, 'Chứng từ ghi tăng', card.asset.acquisition_ref]),
            ('italic', [None, 'Ngày đưa vào sử dụng', card.asset.date_start]),
            ('italic', [None, 'Nguyên giá', card.asset.purchase_value]),
        ]
        for year_row in card.years:
            rows.append(('', [year_row.year, year_row.amount,
                              year_row.cumulative]))
        rows.append(('total', [None, 'Hao mòn luỹ kế', card.accumulated]))
        rows.append(('total', [None, 'Giá trị còn lại', card.residual]))
        if card.asset.date_remove:
            rows.append(('italic', [None, 'Ngày ghi giảm',
                                    card.asset.date_remove]))
        sheets.append({
            'name': (card.asset.code or 'The %s' % (index + 1))[:31],
            'title': '%s — %s' % (doc.get('form_title'), card.asset.name),
            'heading': _heading(report, doc, filter_summary),
            'columns': [('Năm', 14, NUMBER),
                        ('Giá trị hao mòn trong năm', 24, MONEY),
                        ('Hao mòn cộng dồn', 24, MONEY)],
            'rows': rows,
        })
    return sheets or [{
        'name': doc.get('title') or 'The TSCD',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': [('Diễn giải', 60, TEXT)],
        'rows': [('', ['Không có tài sản cố định nào trong phạm vi đã chọn.'])],
    }]


def asset_allocation(report, doc, filter_summary):
    columns = ([('STT', 8, NUMBER), ('Nhóm tài sản cố định', 40, TEXT)]
               + [('Ghi Nợ TK %s' % code, 18, MONEY)
                  for code in report.columns]
               + [('Cộng', 18, MONEY)])
    rows = [('', [position + 1, row.profile.name]
             + [amount or None for amount in row.amounts]
             + [row.total])
            for position, row in enumerate(report.rows)]
    rows.append(('total', [None, 'IV. Số khấu hao phải trích kỳ này']
                 + [total or None for total in report.column_totals]
                 + [report.grand_total]))
    blanks = [None] * len(report.columns)
    rows.append(('italic', [None, 'I. Số khấu hao đã trích kỳ trước']
                 + blanks + [report.summary.previous_total]))
    rows.append(('italic', [None, 'II. Số khấu hao của TSCĐ tăng trong kỳ']
                 + blanks + [report.summary.increase]))
    rows.append(('italic', [None, 'III. Số khấu hao của TSCĐ giảm trong kỳ']
                 + blanks + [report.summary.decrease]))
    if report.summary.imbalance:
        rows.append(('italic', [None, 'Chênh lệch (I + II − III − IV)']
                     + blanks + [report.summary.imbalance]))
    return [{
        'name': 'Bang phan bo khau hao',
        'title': doc.get('form_title'),
        'heading': _heading(report, doc, filter_summary),
        'columns': columns, 'rows': rows,
    }]


#: Layout name -> function. Wizards name one of these rather than a report.
LAYOUTS = {
    'ledger': ledger,
    'expense_ledger': expense_ledger,
    'sales_ledger': sales_ledger,
    'allocation': allocation,
    'trial_balance': trial_balance,
    'aging': aging,
    'statement': statement,
    'vat_listing': vat_listing,
    'inventory': inventory,
    'stock_ledger': stock_ledger,
    'production_cost': production_cost,
    'cost_card': cost_card,
    'asset_register': asset_register,
    'asset_card': asset_card,
    'asset_allocation': asset_allocation,
}
