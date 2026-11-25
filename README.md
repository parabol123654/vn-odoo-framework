# Vietnam VAS Reports for Odoo 14 Community

Vietnamese statutory accounting books, financial statements and VAT returns
under the Vietnamese Accounting Standards (VAS), for **Odoo 14 Community
Edition**. Supports **Circular 99 (TT99, from 2026)**, **Circular 200 (TT200)**
and **Circular 133 (TT133)**.

Every report has an on-screen viewer (collapsible groups, filters, click through
to the journal entry), a PDF print sharing the same QWeb template, and an Excel
export.

## Modules

| Module | Depends on | Purpose |
| --- | --- | --- |
| `vn_core` | `account` | Reporting engines, statement mapping model. Nothing Vietnam-specific. |
| `l10n_vn_vas_reports` | `vn_core` | Books, financial statements, VAT returns, cash vouchers, TT99/TT200/TT133 mappings |
| `l10n_vn_stock_reports` | `stock_account` | Inventory books |
| `l10n_vn_mrp_reports` | `mrp`, `stock_account` | Production cost reports |
| `l10n_vn_asset_reports` | `vn_account_asset` | Fixed asset books |
| `vn_account_asset` | `account` | OCA's `account_asset_management` asset subledger, branch 14.0, without its XLSX report (see below) |

Install only what you need. A trading or services company does not have to
install Inventory or Manufacturing to get the accounting books.

## Reports

| Report | Form | Menu |
| --- | --- | --- |
| Sổ Nhật ký chung | S03a-DN | Accounting books |
| Sổ Cái | S03b-DN | Accounting books |
| Bảng cân đối số phát sinh / Bảng cân đối tài khoản | S06-DN · F01-DNN | Accounting books |
| Sổ chi tiết thanh toán với người mua (người bán) | S31-DN | Detail books |
| Sổ chi tiết thanh toán với người mua (người bán) bằng ngoại tệ | S32-DN | Detail books |
| Sổ quỹ tiền mặt / Sổ tiền gửi ngân hàng | S07-DN / S08-DN | Detail books |
| Sổ chi tiết bán hàng | S35-DN | Detail books |
| Sổ chi phí sản xuất, kinh doanh | S36-DN | Detail books |
| Bảng phân bổ nguyên liệu, vật liệu, công cụ, dụng cụ | 07-VT | Detail books |
| Công nợ phải thu / phải trả theo tuổi nợ | management | Detail books |
| Bảng cân đối kế toán / Báo cáo tình hình tài chính | B01-DN · B01a-DNN · B01b-DNN | Financial statements |
| Báo cáo kết quả hoạt động kinh doanh | B02-DN · B02-DNN | Financial statements |
| Báo cáo lưu chuyển tiền tệ | B03-DN direct · B03-DNN indirect or direct | Financial statements |
| Bản thuyết minh báo cáo tài chính | B09-DN · B09-DNN | Financial statements |
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
straight from the journal entry. Period-end revaluation of foreign-currency
balances is under Accounting → Accounting → Actions → Foreign Currency Revaluation.

## Installation

1. Put this repository on the server and add its root folder to `addons_path`.
   Each module is a folder at the root.
2. `vn_account_asset` is OCA's asset module `account_asset_management`
   (Noviat, OCA, AGPL-3) from
   [OCA/account-financial-tools](https://github.com/OCA/account-financial-tools)
   branch `14.0`, without its XLSX report, so no OCA repository has to be
   added for `l10n_vn_asset_reports`. It is renamed because the Odoo Apps
   Store reserves the name `account_asset_management` for OCA's own module;
   the two cannot be installed together. A database that already runs OCA's
   `account_asset_management` (which `l10n_vn_asset_reports` used to depend
   on) has to be migrated: the data model is the same, but the module's
   records and XML ids have to be renamed to `vn_account_asset` (see
   CHANGELOG). Test it on a copy first. Skip both modules if you don't use
   fixed asset accounting.
3. Install the modules together, so the TT200 mapping data in
   `l10n_vn_vas_reports` and the model fields in `vn_core` stay in step:

```bash
odoo-bin -c odoo.conf -d YOURDB --stop-after-init \
    -i vn_core,l10n_vn_vas_reports,l10n_vn_stock_reports,l10n_vn_mrp_reports,vn_account_asset,l10n_vn_asset_reports
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

* **Settings → Companies → Accounting circular**: TT99, TT200 or TT133. Financial
  statements pick the matching layout automatically.
* **Accounting → Configuration → Statement Mappings**: the lines of each
  financial statement. Accounts are selected by expression (`511*`,
  `111*,112*,-1113`) and totals by formula (`10 - 11`). Formulas are parsed, not
  passed to `eval`. No account code is hard-coded in Python.
* **Accounting → Accounting → Actions → Period-End Closing**: the accounts closed to 911 are
  expressions too, defaulted from the circular; check them, and the 511, 911
  and 4212 accounts, the first time. Only the selected company's own entries
  are closed, not its branches'. The income statement leaves out entries
  touching 911 or 421, so closing does not change it. One exception by design:
  under TT200, B02-DN item 02 is the debit of 511, so sales deductions appear
  there only once 521 has been transferred.

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
| Odoo | 14.0 Community Edition |
| Python | 3.8+ |
| PostgreSQL | 12+ |

Other Odoo versions are on the branches of this repository.

## Development

The reporting engines in `vn_core` (`core`, `domain`, `dto`) do not depend on
Odoo, and most of their tests are plain `unittest` cases. Odoo's test runner
does not pick those up, so run them directly, no Odoo or database needed:

```bash
python3 tools/run_domain_tests.py        # add -v to list each test
```

Test modules that import `odoo` are skipped there; they run with
`odoo-bin --test-enable`.

CI (`.github/workflows/ci.yml`) runs both suites on every push and pull
request to `14.0`: the domain tests on plain Python 3.8, and the Odoo tests of
all six modules on Odoo 14.0 with PostgreSQL 16. It also runs the
`.pre-commit-config.yaml` hooks on the files a change adds
(new code must pass them; existing files predate the formatter).

## License and support

[AGPL-3.0](LICENSE). Copyright 2026 Manh Nguyen.

Support: parabol123654@gmail.com ·
[Issues](https://github.com/parabol123654/vn-odoo-framework/issues)
