# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Base report wizard (Part 12 §5).

A wizard has exactly four jobs: collect input, validate it superficially, build
the FilterDTO, and hand off to a Service. It never queries accounting data and
never computes anything.
"""

import base64
import re
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

from odoo.addons.vn_core.core.enums import TargetMove
from odoo.addons.vn_core.dto.filters import LedgerFilter

from ..report.xlsx_layouts import LAYOUTS as XLSX_LAYOUTS
from ..report.xlsx_writer import VnXlsxWriter


def _default_date_from(record):
    today = fields.Date.context_today(record)
    return today.replace(month=1, day=1)


class VnReportWizardMixin(models.AbstractModel):
    _name = 'vn.report.wizard.mixin'
    _description = 'Vietnam Report Wizard Mixin'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    date_from = fields.Date(
        string='From', required=True, default=_default_date_from)
    date_to = fields.Date(
        string='To', required=True,
        default=lambda self: fields.Date.context_today(self))
    target_move = fields.Selection(
        [('posted', 'Posted entries only'), ('all', 'All entries')],
        string='Entries', default='posted', required=True)
    journal_ids = fields.Many2many(
        'account.journal', string='Journals',
        help='Leave empty to include every journal.')

    # ------------------------------------------------------------------
    # Validation (Part 12 §11 — surface checks only)
    # ------------------------------------------------------------------
    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to \
                    and wizard.date_from > wizard.date_to:
                raise UserError(_('The start date must precede the end date.'))

    # ------------------------------------------------------------------
    # Filter DTO
    # ------------------------------------------------------------------
    def _ledger_filter(self, **overrides):
        """Build the immutable filter the Domain expects."""
        self.ensure_one()
        values = dict(
            date_from=self.date_from,
            date_to=self.date_to,
            company_ids=(self.company_id.id,),
            target_move=(TargetMove.POSTED if self.target_move == 'posted'
                         else TargetMove.ALL),
            journal_ids=tuple(self.journal_ids.ids),
        )
        values.update(overrides)
        return LedgerFilter(**values)

    # ------------------------------------------------------------------
    # Hooks for concrete wizards
    # ------------------------------------------------------------------
    def _service(self):
        raise NotImplementedError

    def _report_title(self):
        raise NotImplementedError

    def _screen_template(self):
        raise NotImplementedError

    def _pdf_report_xmlid(self):
        raise NotImplementedError

    def _report_form_code(self):
        """Statutory form number printed top-right, e.g. "S03b-DN"."""
        return ''

    def _report_form_title(self):
        """The Vietnamese heading printed on the statutory form.

        Kept separate from ``_report_title()``: the on-screen title follows the
        user's language, whereas the printed book carries the name fixed by
        TT200 and must not be translated away.
        """
        return self._report_title()

    def _build_report(self):
        """Run the service and unwrap the ResultDTO."""
        self.ensure_one()
        result = self._service().generate(self._ledger_filter())
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data

    # ------------------------------------------------------------------
    # Excel export
    # ------------------------------------------------------------------
    xlsx_file = fields.Binary(readonly=True, attachment=False)
    xlsx_filename = fields.Char(readonly=True)

    def _xlsx_layout(self):
        """Which sheet layout renders this report.

        Named after the **shape of the data**, not after the report: sixteen
        reports share seven shapes, so a new report usually names an existing
        layout and needs no export code of its own.
        """
        return 'statement'

    def _xlsx_doc_values(self):
        """Provenance lines for the top of the sheet.

        A workbook outlives the screen it came from and gets mailed around, so
        it carries the same company, period and filters the printed header does.
        Without them it is a grid of numbers nobody can check.
        """
        self.ensure_one()
        period = ''
        if self.date_from:
            period = 'Từ ngày %s đến ngày %s' % (
                format_date(self.env, self.date_from),
                format_date(self.env, self.date_to))
        elif self.date_to:
            period = 'Tại ngày %s' % format_date(self.env, self.date_to)
        return {
            'company': self.company_id.display_name,
            'period': period,
            'currency': self.company_id.currency_id.name,
            'title': self._sheet_name(),
            'form_title': self._report_form_title(),
        }

    def _sheet_name(self):
        """A tab name Excel accepts: ASCII, no punctuation, 31 characters."""
        self.ensure_one()
        text = unicodedata.normalize('NFD', self._report_title() or 'Report')
        text = ''.join(char for char in text
                       if unicodedata.category(char) != 'Mn')
        text = re.sub(r'[^A-Za-z0-9 ]+', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()[:31] or 'Report'

    def action_export_xlsx(self):
        self.ensure_one()
        report = self._build_report()
        layout = XLSX_LAYOUTS.get(self._xlsx_layout())
        if layout is None:
            raise UserError(_("No spreadsheet layout named %s.")
                            % self._xlsx_layout())

        sheets = layout(report, self._xlsx_doc_values(), self._filter_summary())
        writer = VnXlsxWriter(
            decimal_places=self.company_id.currency_id.decimal_places)
        self.write({
            'xlsx_file': base64.b64encode(writer.build(sheets)),
            'xlsx_filename': '%s-%s.xlsx' % (
                self._sheet_name().replace(' ', '-'), self.date_to),
        })
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': ('/web/content/?model=%s&id=%s&field=xlsx_file'
                    '&filename_field=xlsx_filename&download=true'
                    % (self._name, self.id)),
        }

    # ------------------------------------------------------------------
    # Drill down
    # ------------------------------------------------------------------
    def _drill_target_model(self):
        """Where an item opens into. The General Ledger, not a raw list view.

        Landing on ``account.move.line`` would answer "which rows" but lose the
        opening balance, the running balance and the counterpart column — the
        things that let an accountant recognise what they are looking at. The
        ledger is already a VAS book, and it drills onward to the journal entry
        and from there to the source document through Odoo's own links.
        """
        return 'vn.general.ledger.wizard'

    def _drill_date_from(self):
        """Period the ledger opens on. Statements that are as-at override this."""
        return self.date_from

    def _drill_values(self, account_ids):
        self.ensure_one()
        return {
            'company_id': self.company_id.id,
            'date_from': self._drill_date_from(),
            'date_to': self.date_to,
            'target_move': self.target_move,
            'account_ids': [(6, 0, list(account_ids))],
        }

    def action_drill_down(self, line_code):
        """Open the ledger behind one item of a statement.

        Only offered where the ledger adds back to the figure that was clicked.
        A drill-down landing on a total that disagrees with the line above it is
        worse than none, because it teaches the reader to distrust both.
        """
        self.ensure_one()
        report = self._build_report()
        line = next((row for row in getattr(report, 'lines', ())
                     if row.code == line_code), None)
        if line is None:
            raise UserError(_("No item %s on this report.") % line_code)
        if not line.account_ids:
            raise UserError(_(
                "Item %s is a heading or a figure the ledger cannot explain, "
                "so there is nothing to open.") % line_code)

        ledger = self.env[self._drill_target_model()].create(
            self._drill_values(line.account_ids))
        return ledger.action_view()

    # ------------------------------------------------------------------
    # Filter summary
    # ------------------------------------------------------------------
    #: How many names to spell out before summarising the rest.
    _FILTER_NAME_LIMIT = 6

    def _filter_summary_fields(self):
        """Fields shown as applied conditions, in the order they are printed.

        Each wizard declares its own: a stock report filters by product, a
        ledger by account, and listing a field the wizard does not have would
        print a meaningless row.
        """
        return ('target_move',)

    def _filter_summary(self):
        """-> ``[(label, value)]`` describing what was actually filtered.

        A printed report that does not say which accounts it covers cannot be
        audited: the page looks identical whether it is the whole ledger or
        three hand-picked accounts. Anything left unfiltered prints as "All" so
        the absence of a restriction is stated rather than merely implied.
        """
        self.ensure_one()
        rows = []
        for name in self._filter_summary_fields():
            field = self._fields.get(name)
            if field is None:
                continue
            rows.append((field.string, self._format_filter(name, field)))
        return rows

    def _format_filter(self, name, field):
        value = self[name]
        if field.type in ('many2many', 'one2many'):
            if not value:
                return _('All')
            names = value.mapped('display_name')
            if len(names) > self._FILTER_NAME_LIMIT:
                # Odoo 14's _() takes the source string only; interpolate after.
                return _('%s and %s more') % (
                    ', '.join(names[:self._FILTER_NAME_LIMIT]),
                    len(names) - self._FILTER_NAME_LIMIT)
            return ', '.join(names)
        if field.type == 'many2one':
            return value.display_name if value else _('All')
        if field.type == 'selection':
            return dict(field._description_selection(self.env)).get(value, '')
        if field.type == 'boolean':
            return _('Yes') if value else _('No')
        return value or _('All')

    def _template_values(self, report):
        """Values handed to QWeb. Rendering only — nothing is computed here."""
        self.ensure_one()
        return {
            'doc': self,
            'report': report,
            'company': self.company_id,
            # A real currency record, purely so the monetary widget can format
            # per the user's language. No business value is read from it.
            'currency': self.company_id.currency_id,
            'title': self._report_title(),
            'form_title': self._report_form_title(),
            'form_code': self._report_form_code(),
            'filter_summary': self._filter_summary(),
            'interactive': False,
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_view(self):
        """Open the interactive on-screen viewer."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'vn_report_viewer',
            'name': self._report_title(),
            'context': {
                'vn_report_model': self._name,
                'vn_report_wizard_id': self.id,
            },
        }

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(self._pdf_report_xmlid()).report_action(self)

    def get_report_html(self):
        """Called over RPC by the viewer widget.

        Returns rendered HTML rather than raw data: the QWeb template is the
        single definition of the form layout, shared by screen and PDF, so the
        two can never drift apart.
        """
        self.ensure_one()
        report = self._build_report()
        values = self._template_values(report)
        values['interactive'] = True
        html = self.env['ir.ui.view']._render_template(
            self._screen_template(), values)
        # _render_template returns bytes on some 14.0 builds and Markup on
        # others; JSON-RPC can only carry text, so normalise here.
        if isinstance(html, bytes):
            html = html.decode('utf-8')
        return str(html)
