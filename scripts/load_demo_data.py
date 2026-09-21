# -*- coding: utf-8 -*-
"""Load the VAS demo ledger into an existing database.

Most databases are created with ``--without-demo=all``, which means the
``demo/`` hook in the manifest never fires. This script reaches the same
generator directly, so no reinstall is needed and it can be re-run at will.

Usage — pipe it into the Odoo shell:

    ./odoo-bin shell -c odoo.conf -d YOURDB --no-http < scripts/load_demo_data.py

Options via environment variables:

    VAS_DEMO_COMPANY   name of the company to post into (default: current)
    VAS_DEMO_KEEP      set to 1 to add on top of existing demo entries
                       instead of replacing them

The generator is idempotent: every move it creates carries a ``VAS-DEMO/``
reference and the previous batch is removed before the new one is written,
unless VAS_DEMO_KEEP is set.
"""

import os

# ``env`` is injected by ``odoo-bin shell``.
company_name = os.environ.get('VAS_DEMO_COMPANY')
if company_name:
    company = env['res.company'].search([('name', '=', company_name)], limit=1)
    if not company:
        raise SystemExit('Company not found: %s' % company_name)
else:
    company = env.company

clear = os.environ.get('VAS_DEMO_KEEP') != '1'

print('Company : %s (%s)' % (company.name, company.currency_id.name))
print('Mode    : %s' % ('replace existing demo entries' if clear else 'append'))

summary = env['vn.demo.data.generator'].generate(company=company, clear=clear)

# The stock, manufacturing and asset demos live in their own modules and are
# generated here too when those modules are installed. They run once — done
# stock moves and posted depreciation cannot be unlinked — and report
# themselves as skipped afterwards.
for extra_model, what in (('vn.demo.stock.generator', 'inventory'),
                          ('vn.demo.mrp.generator', 'manufacturing'),
                          ('vn.demo.asset.generator', 'fixed assets')):
    if extra_model not in env:
        continue
    extra = env[extra_model].generate(company=company)
    print('Demo %-14s: %s' % (
        what, 'already loaded' if extra.get('skipped') else 'created'))

env.cr.commit()

print('')
print('Created %(moves)s posted entries (%(invoices)s of them invoices), '
      '%(lines)s journal items' % summary)
print('Journal : %(journal)s' % summary)
print('Accounts: %(accounts)s resolved or created' % summary)
print('Dates   : %s to %s' % summary['date_range'])
print('')
print('Now open  Invoicing > Reporting > Vietnam (VAS) > Trial Balance')
print('and set the period to 01/01/2026 - 31/12/2026.')
print('')
print('Two things worth checking on that first run:')
print('  * TK 131 opens at 150,000,000 - carried forward from 2025, because')
print('    a balance-sheet account accumulates from inception;')
print('  * TK 511 opens at 0 even though 2025 booked 450,000,000 of revenue,')
print('    because a P&L account resets at the fiscal year start.')
print('')
print('Then change the period to 01/03/2026 - 31/12/2026:')
print('  * TK 131 opening becomes 205,000,000 (2025 plus the January sale);')
print('  * TK 511 opening becomes 50,000,000 Co - January and February only,')
print('    not the 2025 figure. That is the fiscal-year rule working.')
print('')
print('To see the imbalance warning, delete the two VAS-DEMO/2025/90 and /91')
print('closing entries: without them the 2025 result never reaches TK 421 and')
print('the Trial Balance for 2026 correctly refuses to balance.')
