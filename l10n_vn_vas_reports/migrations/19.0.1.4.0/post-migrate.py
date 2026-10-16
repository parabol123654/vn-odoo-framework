# -*- coding: utf-8 -*-
"""Point the TT200 statements' "Thuyết minh" column at the notes (B09-DN).

TT200 Điều 115 khoản 2 điểm d asks that every item on the statements lead
to its note. 19.0.1.4.0 ships the B09-DN notes form of TT200 and fills the
column on its B01-DN and B02-DN with the number of the matching item (VI.1,
VII.3, …). The mapping data is noupdate="1", so on a database that already
has the lines this script fills the column itself — only where it is still
empty: a reference a company typed in stays.

The notes template itself needs nothing here: its records are new, and new
records are created by the data files even in a noupdate block.
"""
import logging

_logger = logging.getLogger(__name__)

NOTE_REFS = {'l10n_vn_vas_reports.b01dn_110': 'VI.1',
 'l10n_vn_vas_reports.b01dn_111': 'VI.1',
 'l10n_vn_vas_reports.b01dn_112': 'VI.1',
 'l10n_vn_vas_reports.b01dn_121': 'VI.2a',
 'l10n_vn_vas_reports.b01dn_122': 'VI.2a',
 'l10n_vn_vas_reports.b01dn_123': 'VI.2b',
 'l10n_vn_vas_reports.b01dn_131': 'VI.3',
 'l10n_vn_vas_reports.b01dn_136': 'VI.4',
 'l10n_vn_vas_reports.b01dn_137': 'VI.3',
 'l10n_vn_vas_reports.b01dn_139': 'VI.5',
 'l10n_vn_vas_reports.b01dn_141': 'VI.7',
 'l10n_vn_vas_reports.b01dn_149': 'VI.7',
 'l10n_vn_vas_reports.b01dn_153': 'VI.17',
 'l10n_vn_vas_reports.b01dn_222': 'VI.9',
 'l10n_vn_vas_reports.b01dn_223': 'VI.9',
 'l10n_vn_vas_reports.b01dn_225': 'VI.11',
 'l10n_vn_vas_reports.b01dn_226': 'VI.11',
 'l10n_vn_vas_reports.b01dn_228': 'VI.10',
 'l10n_vn_vas_reports.b01dn_229': 'VI.10',
 'l10n_vn_vas_reports.b01dn_231': 'VI.12',
 'l10n_vn_vas_reports.b01dn_232': 'VI.12',
 'l10n_vn_vas_reports.b01dn_242': 'VI.8',
 'l10n_vn_vas_reports.b01dn_261': 'VI.13',
 'l10n_vn_vas_reports.b01dn_262': 'VI.24a',
 'l10n_vn_vas_reports.b01dn_311': 'VI.16',
 'l10n_vn_vas_reports.b01dn_313': 'VI.17',
 'l10n_vn_vas_reports.b01dn_315': 'VI.18',
 'l10n_vn_vas_reports.b01dn_318': 'VI.20',
 'l10n_vn_vas_reports.b01dn_319': 'VI.19',
 'l10n_vn_vas_reports.b01dn_320': 'VI.15',
 'l10n_vn_vas_reports.b01dn_338': 'VI.15',
 'l10n_vn_vas_reports.b01dn_341': 'VI.24b',
 'l10n_vn_vas_reports.b01dn_342': 'VI.23',
 'l10n_vn_vas_reports.b01dn_400': 'VI.25a',
 'l10n_vn_vas_reports.b01dn_411': 'VI.25a',
 'l10n_vn_vas_reports.b01dn_412': 'VI.25a',
 'l10n_vn_vas_reports.b02dn_01': 'VII.1',
 'l10n_vn_vas_reports.b02dn_02': 'VII.2',
 'l10n_vn_vas_reports.b02dn_11': 'VII.3',
 'l10n_vn_vas_reports.b02dn_21': 'VII.4',
 'l10n_vn_vas_reports.b02dn_22': 'VII.5',
 'l10n_vn_vas_reports.b02dn_23': 'VII.5',
 'l10n_vn_vas_reports.b02dn_25': 'VII.8',
 'l10n_vn_vas_reports.b02dn_26': 'VII.8',
 'l10n_vn_vas_reports.b02dn_31': 'VII.6',
 'l10n_vn_vas_reports.b02dn_32': 'VII.7',
 'l10n_vn_vas_reports.b02dn_51': 'VII.10',
 'l10n_vn_vas_reports.b02dn_52': 'VII.11'}


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    filled, kept = 0, 0
    for xmlid, reference in NOTE_REFS.items():
        line = env.ref(xmlid, raise_if_not_found=False)
        if not line:
            continue
        if line.note_ref:
            kept += 1
            continue
        line.note_ref = reference
        filled += 1
    _logger.info('TT200 statement mappings: note references filled on %d '
                 'lines, %d already had one.', filled, kept)
