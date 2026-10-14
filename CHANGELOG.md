# Changelog

Notable changes to these modules. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- Notes on the report wizards show in Vietnamese again. Their catalogue entries had lost the line breaks Odoo matches the view text on, so they stayed in English on a Vietnamese database.
- Aged balances, partner ledger and cash book open on Odoo 17: they filtered accounts on `company_ids`, which only exists from 18.0.
- The module tests run on a current Odoo 17.0 image (date filters).

### Added

- Lint configuration: pre-commit, black, isort, flake8, pylint-odoo, .editorconfig.

### Verified

- Installed on a fresh Odoo 17.0 database with demo data (all five modules, with OCA `account_asset_management` 17.0): every report opens on screen and exports to Excel, and the module tests pass. Figures have not yet been reconciled against a company's own books.
