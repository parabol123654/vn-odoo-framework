# Changelog

Notable changes to these modules. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- Notes on the report wizards show in Vietnamese again. Their catalogue entries had lost the line breaks Odoo matches the view text on, so they stayed in English on a Vietnamese database.
- The cash book (S07-DN / S08-DN) finds the 111 / 112 accounts of the company chosen on the wizard, not of the user's current company.

### Added

- Lint configuration: pre-commit, black, isort, flake8, pylint-odoo, .editorconfig.

### Verified

- Installed on a fresh Odoo 20.0 database with demo data (four modules; the fixed-asset module waits for OCA to port `account_asset_management` to 20.0): every report opens on screen and exports to Excel, and the module tests pass. Figures have not yet been reconciled against a company's own books.
