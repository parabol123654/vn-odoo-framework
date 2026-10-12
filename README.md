# Vietnam VAS Reports for Odoo 15 Community

Vietnamese statutory accounting books, financial statements and VAT returns
under the Vietnamese Accounting Standards (VAS), for **Odoo 15 Community
Edition**. Supports **Circular 200 (TT200)** and **Circular 133 (TT133)**.

Every report has an on-screen viewer (collapsible groups, filters, click through
to the journal entry), a PDF print sharing the same QWeb template, and an Excel
export.

## Modules

| Module | Depends on | Purpose |
| --- | --- | --- |
| `vn_core` | `account` | Reporting engines, statement mapping model. Nothing Vietnam-specific. |
| `l10n_vn_vas_reports` | `vn_core` | Books, financial statements, VAT returns, cash vouchers, TT200/TT133 mappings |
| `l10n_vn_stock_reports` | `stock_account` | Inventory books |
| `l10n_vn_mrp_reports` | `mrp`, `stock_account` | Production cost reports |
| `l10n_vn_asset_reports` | OCA `account_asset_management` | Fixed asset books |

Install only what you need. A trading or services company does not have to
install Inventory or Manufacturing to get the accounting books.

## Reports

| Report | Form | Menu |
| --- | --- | --- |
| Sổ Nhật ký chung | S03a-DN | Accounting books |
| Sổ Cái | S03b-DN | Accounting books |
| Bảng cân đối số phát sinh | S06-DN | Accounting books |
| Sổ chi tiết thanh toán với người mua (người bán) | S31-DN | Detail books |
| Sổ quỹ tiền mặt / Sổ tiền gửi ngân hàng | S07-DN / S08-DN | Detail books |
| Sổ chi tiết bán hàng | S35-DN | Detail books |
| Sổ chi phí sản xuất, kinh doanh | S36-DN | Detail books |
| Bảng phân bổ nguyên liệu, vật liệu, công cụ, dụng cụ | 07-VT | Detail books |
| Công nợ phải thu / phải trả theo tuổi nợ | management | Detail books |
| Bảng cân đối kế toán / Báo cáo tình hình tài chính | B01-DN · B01a-DNN | Financial statements |
| Báo cáo kết quả hoạt động kinh doanh | B02-DN · B02-DNN | Financial statements |
| Báo cáo lưu chuyển tiền tệ | B03-DN direct · B03-DNN indirect | Financial statements |
| Bảng kê hoá đơn bán ra / mua vào | 01/GTGT annex | Tax |
| Tờ khai thuế giá trị gia tăng | 01/GTGT | Tax |
| Bảng tổng hợp Nhập - Xuất - Tồn | S11-DN | Inventory |
| Thẻ kho | S12-DN | Inventory |
| Sổ chi tiết vật liệu, dụng cụ, sản phẩm, hàng hóa | S10-DN | Inventory |
| Báo cáo chi phí sản xuất và giá thành | management | Manufacturing |
| Thẻ tính giá thành sản phẩm, dịch vụ | S37-DN | Manufacturing |
| Sổ tài sản cố định / Thẻ tài sản cố định | S21-DN / S23-DN | Fixed assets |
| Bảng tính và phân bổ khấu hao TSCĐ | 06-TSCĐ | Fixed assets |

Cash receipts and payments (**Phiếu thu 01-TT / Phiếu chi 02-TT**) print
straight from the journal entry.

## Installation

1. Put this repository on the server and add its root folder to `addons_path`.
   Each module is a folder at the root.
2. For `l10n_vn_asset_reports` only: also add
   [OCA/account-financial-tools](https://github.com/OCA/account-financial-tools)
   and [OCA/reporting-engine](https://github.com/OCA/reporting-engine), branch
   `15.0`. Skip this module if you don't use fixed asset accounting.
3. Install the modules together, so the TT200 mapping data in
   `l10n_vn_vas_reports` and the model fields in `vn_core` stay in step:

```bash
odoo-bin -c odoo.conf -d YOURDB --stop-after-init \
    -i vn_core,l10n_vn_vas_reports,l10n_vn_stock_reports,l10n_vn_mrp_reports,l10n_vn_asset_reports
```

When upgrading, pass the same list to `-u`. Upgrading `l10n_vn_vas_reports`
without `vn_core` fails with
`column "cash_expression" of relation "vn_report_mapping" does not exist`.

## Demo data

On a database created with demo data, every module loads a sample Vietnamese
furniture company when it is installed: 22 journal entries over two fiscal
years, VAT invoices, stock moves, a manufacturing order and fixed assets. The
generator resolves accounts by code prefix and creates any missing ones, so it
works with `l10n_vn` or any other chart of accounts.

## Configuration

* **Settings → Companies → Accounting circular**: TT200 or TT133. Financial
  statements pick the matching layout automatically.
* **Accounting → Configuration → Statement Mappings**: the lines of each
  financial statement. Accounts are selected by expression (`511*`,
  `111*,112*,-1113`) and totals by formula (`10 - 11`). Formulas are parsed, not
  passed to `eval`. No account code is hard-coded in Python.

Clicking a line of the balance sheet or income statement opens the general
ledger for exactly the accounts behind that figure.

## Known limitations

* B01-DN: 12 rarely used lines have no account expression yet. They are left
  blank rather than guessed. The report lists every account with a balance that
  no line picks up.
* Production cost covers direct materials only. Odoo Community does not post
  labour or overhead to the ledger.
* S21-DN prints the "country / year of manufacture" column blank because the
  asset subledger does not store those fields.

## Compatibility

| | |
| --- | --- |
| Odoo | 15.0 Community Edition |
| Python | 3.8 – 3.10 |
| PostgreSQL | 12+ |

Other Odoo versions are on the branches of this repository.

## License and support

[AGPL-3.0](LICENSE). Copyright 2026 Manh Nguyen.

Support: parabol123654@gmail.com ·
[Issues](https://github.com/parabol123654/vn-odoo-framework/issues)
