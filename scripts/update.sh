#!/usr/bin/env bash
#
# Update every module of this repository, in one command.
#
# Why this exists: the TT200 mapping data lives in l10n_vn_vas_reports but writes to
# fields declared on models in vn_core. That split is deliberate — the framework
# owns the model, the localisation owns the data — but it means the two must be
# updated together. Updating only the downstream module leaves the column
# missing and the load fails with:
#
#     psycopg2.errors.UndefinedColumn: column "cash_expression"
#     of relation "vn_report_mapping" does not exist
#
# The module list is discovered from the manifests at the repository root
# (the layout Odoo Apps expects) rather than typed, so a module added
# later is picked up without anyone remembering to edit a command.
#
# Usage:
#     scripts/update.sh DATABASE [extra odoo-bin arguments...]
#
# Environment:
#     ODOO_BIN    path to odoo-bin      (default: odoo-bin on PATH)
#     ODOO_CONF   configuration file    (default: scripts/odoo.conf)

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: scripts/update.sh DATABASE [extra odoo-bin arguments...]" >&2
    exit 2
fi

DB="$1"
shift

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ODOO_BIN="${ODOO_BIN:-odoo-bin}"
CONF="${ODOO_CONF:-$ROOT/scripts/odoo.conf}"

if [ ! -f "$CONF" ]; then
    echo "Missing $CONF — copy scripts/odoo.conf.example and edit the paths." >&2
    exit 1
fi

# Dependency order does not need to be worked out here: Odoo sorts the graph
# itself. What matters is that nothing is left out.
MODULES="$(cd "$ROOT" && ls -d */__manifest__.py 2>/dev/null | xargs -n1 dirname | tr '\n' ',' | sed 's/,$//')"

echo "Updating $MODULES on database $DB"
exec "$ODOO_BIN" -c "$CONF" -d "$DB" -u "$MODULES" \
    --i18n-overwrite --stop-after-init "$@"
