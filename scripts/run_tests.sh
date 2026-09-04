#!/usr/bin/env bash
#
# Full test run: needs Odoo 14 and PostgreSQL.
# For the Domain tests alone — which need neither — use:
#     python3 scripts/run_domain_tests.py
#
set -euo pipefail

DB="${1:-vn_test}"
ODOO_BIN="${ODOO_BIN:-odoo}"
CONF="${ODOO_CONF:-scripts/odoo.conf}"
MODULES="${MODULES:-vn_core,l10n_vn_vas_reports}"

# Structural checks run first: they are fast, they need neither Odoo nor a
# database, and they catch whole classes of failure that produce no error at
# runtime — invalid UTF-8, Odoo imports leaking into the Domain, a README
# claiming a form the code does not implement.
python3 "$(dirname "$0")/check_repo.py"

if [ ! -f "$CONF" ]; then
    echo "Missing $CONF — copy scripts/odoo.conf.example and edit the paths." >&2
    exit 1
fi

echo "Installing and testing $MODULES on database $DB"

# workers=0 keeps tests in-process so tracebacks are readable.
"$ODOO_BIN" \
    --config "$CONF" \
    --database "$DB" \
    --init "$MODULES" \
    --test-enable \
    --stop-after-init \
    --log-level=test \
    --workers=0

echo
echo "To rerun only one class:"
echo "  $ODOO_BIN -c $CONF -d $DB -u $MODULES --test-enable --stop-after-init \\"
echo "      --test-tags /vn_core:TestOdooLedgerRepository"
