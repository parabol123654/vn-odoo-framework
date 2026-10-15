# Changelog

Notable changes to these modules. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Bản thuyết minh báo cáo tài chính, form B09-DNN of Thông tư 133/2016 (Phụ lục 2; Điều 81 mục 2.5): Accounting → Reporting → Vietnam (VAS) → Financial Statements.
- The notes are kept per company and year, and locked once filed. As the circular requires, the "Số đầu năm" / "Năm trước" columns are copied from last year's locked notes; the first year they are read from the ledger and every row says so. Text carries over from last year's notes.
- The 22 numeric tables (V.1–V.13, VI.1–VI.9) are read from the ledger with the same accounts as the balance sheet and income statement, and every total is checked against the statement line it explains. Rows the circular gives no account for (related parties, bad debts, short/long-term loans, cost of sales by kind…) are filled in by hand and checked against their total. Hand-typed figures are kept when the notes are computed again.
- The "Thuyết minh" column of B01a-DNN, B01b-DNN and B02-DNN now points at the matching note (V.1, VI.3…). On upgrade it is filled only where it is empty.
- Printed in the form's layout (PDF). Items with nothing to report can be left out.
- The notes forms of Thông tư 99/2025 and 200/2014 are not included yet.
- Thông tư 99/2025/TT-BTC (in force for financial years starting on or after 1 January 2026): balance sheet B01-DN, income statement B02-DN, and cash flow statement B03-DN by the direct and the indirect method. Choose "Thông tư 99/2025" as the company's accounting regime.
- TT133: the balance sheet B01b-DNN (for companies that do not meet the going-concern assumption), the cash flow statement B03-DNN by the direct method, and the account balance sheet printed as F01-DNN.
- Each company can choose which balance sheet and which cash flow method its regime uses (Settings → company).
- Statement mappings carry the official form number and title; printed reports show the form number, the "issued with Circular …" line, and the signers that the company's circular prescribes.
- Lint configuration: pre-commit, black, isort, flake8, pylint-odoo, .editorconfig.

### Changed

- The TT133 balance sheet B01a-DNN, income statement B02-DNN and cash flow statement B03-DNN now follow the line numbers and line definitions of the circular's appendix.
- Liabilities are split into short and long term by the due date of the journal item (more than twelve months after the report date is long term).

### Fixed

- Income statements no longer net to zero when the year-end transfer to 911 / 421 is posted: entries touching 911 and 421 are left out of the period's movements.
- TT200 balance sheet: provisions on lines 122, 137 and 149 are shown as negative figures, and loans on account 341 are split between line 320 (short term) and line 338 (long term).
- On upgrade, statement lines that still hold the old shipped values are corrected; lines you edited yourself are kept and listed in the server log.
- Notes on the report wizards show in Vietnamese again. Their catalogue entries had lost the line breaks Odoo matches the view text on, so they stayed in English on a Vietnamese database.
- The module tests run on a current Odoo 14.0 image (date filters).

### Verified

- Installed on a fresh Odoo 14.0 database with demo data (all five modules, with OCA `account_asset_management` 14.0): every report opens on screen and exports to Excel, and the module tests pass. Figures have not yet been reconciled against a company's own books.
- Upgrading from the previous release on a database where one statement line had been edited by hand: the shipped lines are corrected, the edited line is kept, and the statements match the new data.
