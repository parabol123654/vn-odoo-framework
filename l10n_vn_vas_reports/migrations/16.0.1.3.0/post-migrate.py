# -*- coding: utf-8 -*-
"""Point the TT99 statements' "Thuyết minh" column at the notes (B09-DN).

TT99 Phụ lục IV Mục 2 phần E mục 2d asks that every item on the statements
lead to its note. 16.0.1.3.0 ships the B09-DN notes form and fills the
column on B01-DN and B02-DN of TT99 with the number of the matching item
(V.1, VII.3, …). The mapping data is noupdate="1", so on a database that
already has the lines this script fills the column itself — only where it
is still empty: a reference a company typed in stays.

The notes template itself needs nothing here: its records are new, and new
records are created by the data files even in a noupdate block.
"""
import logging

_logger = logging.getLogger(__name__)

NOTE_REFS = {'l10n_vn_vas_reports.b01dn99_110': 'V.1',
 'l10n_vn_vas_reports.b01dn99_111': 'V.1',
 'l10n_vn_vas_reports.b01dn99_112': 'V.1',
 'l10n_vn_vas_reports.b01dn99_121': 'V.2a',
 'l10n_vn_vas_reports.b01dn99_122': 'V.2a',
 'l10n_vn_vas_reports.b01dn99_123': 'V.2b',
 'l10n_vn_vas_reports.b01dn99_124': 'V.2b',
 'l10n_vn_vas_reports.b01dn99_125': 'V.2c',
 'l10n_vn_vas_reports.b01dn99_131': 'V.3',
 'l10n_vn_vas_reports.b01dn99_135': 'V.4',
 'l10n_vn_vas_reports.b01dn99_136': 'V.3',
 'l10n_vn_vas_reports.b01dn99_137': 'V.5',
 'l10n_vn_vas_reports.b01dn99_141': 'V.7',
 'l10n_vn_vas_reports.b01dn99_142': 'V.7',
 'l10n_vn_vas_reports.b01dn99_151': 'V.12.1',
 'l10n_vn_vas_reports.b01dn99_152': 'V.12.1',
 'l10n_vn_vas_reports.b01dn99_161': 'V.14',
 'l10n_vn_vas_reports.b01dn99_163': 'V.19',
 'l10n_vn_vas_reports.b01dn99_165': 'V.15',
 'l10n_vn_vas_reports.b01dn99_211': 'V.3',
 'l10n_vn_vas_reports.b01dn99_215': 'V.4',
 'l10n_vn_vas_reports.b01dn99_216': 'V.3',
 'l10n_vn_vas_reports.b01dn99_222': 'V.9',
 'l10n_vn_vas_reports.b01dn99_223': 'V.9',
 'l10n_vn_vas_reports.b01dn99_225': 'V.11',
 'l10n_vn_vas_reports.b01dn99_226': 'V.11',
 'l10n_vn_vas_reports.b01dn99_228': 'V.10',
 'l10n_vn_vas_reports.b01dn99_229': 'V.10',
 'l10n_vn_vas_reports.b01dn99_232': 'V.12.1',
 'l10n_vn_vas_reports.b01dn99_234': 'V.12.2',
 'l10n_vn_vas_reports.b01dn99_235': 'V.12.2',
 'l10n_vn_vas_reports.b01dn99_236': 'V.12.1',
 'l10n_vn_vas_reports.b01dn99_237': 'V.12.1',
 'l10n_vn_vas_reports.b01dn99_241': 'V.13',
 'l10n_vn_vas_reports.b01dn99_242': 'V.13',
 'l10n_vn_vas_reports.b01dn99_251': 'V.8',
 'l10n_vn_vas_reports.b01dn99_252': 'V.8',
 'l10n_vn_vas_reports.b01dn99_261': 'V.2c',
 'l10n_vn_vas_reports.b01dn99_262': 'V.2c',
 'l10n_vn_vas_reports.b01dn99_263': 'V.2c',
 'l10n_vn_vas_reports.b01dn99_264': 'V.2c',
 'l10n_vn_vas_reports.b01dn99_265': 'V.2b',
 'l10n_vn_vas_reports.b01dn99_266': 'V.2b',
 'l10n_vn_vas_reports.b01dn99_271': 'V.14',
 'l10n_vn_vas_reports.b01dn99_272': 'V.26a',
 'l10n_vn_vas_reports.b01dn99_274': 'V.15',
 'l10n_vn_vas_reports.b01dn99_311': 'V.17',
 'l10n_vn_vas_reports.b01dn99_313': 'V.18',
 'l10n_vn_vas_reports.b01dn99_314': 'V.19',
 'l10n_vn_vas_reports.b01dn99_316': 'V.20',
 'l10n_vn_vas_reports.b01dn99_319': 'V.22',
 'l10n_vn_vas_reports.b01dn99_320': 'V.21',
 'l10n_vn_vas_reports.b01dn99_321': 'V.16',
 'l10n_vn_vas_reports.b01dn99_322': 'V.25',
 'l10n_vn_vas_reports.b01dn99_331': 'V.17',
 'l10n_vn_vas_reports.b01dn99_333': 'V.19',
 'l10n_vn_vas_reports.b01dn99_334': 'V.20',
 'l10n_vn_vas_reports.b01dn99_337': 'V.22',
 'l10n_vn_vas_reports.b01dn99_338': 'V.21',
 'l10n_vn_vas_reports.b01dn99_339': 'V.16',
 'l10n_vn_vas_reports.b01dn99_340': 'V.23.2',
 'l10n_vn_vas_reports.b01dn99_341': 'V.24',
 'l10n_vn_vas_reports.b01dn99_342': 'V.26b',
 'l10n_vn_vas_reports.b01dn99_343': 'V.25',
 'l10n_vn_vas_reports.b01dn99_400': 'V.27a',
 'l10n_vn_vas_reports.b01dn99_411': 'V.27a',
 'l10n_vn_vas_reports.b01dn99_412': 'V.27a',
 'l10n_vn_vas_reports.b01dn99_413': 'V.27a',
 'l10n_vn_vas_reports.b01dn99_414': 'V.27a',
 'l10n_vn_vas_reports.b01dn99_415': 'V.27a',
 'l10n_vn_vas_reports.b01dn99_416': 'V.28',
 'l10n_vn_vas_reports.b01dn99_417': 'V.29',
 'l10n_vn_vas_reports.b02dn99_01': 'VII.1',
 'l10n_vn_vas_reports.b02dn99_02': 'VII.2',
 'l10n_vn_vas_reports.b02dn99_11': 'VII.3',
 'l10n_vn_vas_reports.b02dn99_21': 'VII.4',
 'l10n_vn_vas_reports.b02dn99_22': 'VII.5',
 'l10n_vn_vas_reports.b02dn99_23': 'VII.6',
 'l10n_vn_vas_reports.b02dn99_24': 'VII.6',
 'l10n_vn_vas_reports.b02dn99_25': 'VII.9',
 'l10n_vn_vas_reports.b02dn99_26': 'VII.9',
 'l10n_vn_vas_reports.b02dn99_31': 'VII.7',
 'l10n_vn_vas_reports.b02dn99_32': 'VII.8',
 'l10n_vn_vas_reports.b02dn99_50': 'VII.11',
 'l10n_vn_vas_reports.b02dn99_51': 'VII.11',
 'l10n_vn_vas_reports.b02dn99_52': 'VII.11'}


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
    _logger.info('TT99 statement mappings: note references filled on %d '
                 'lines, %d already had one.', filled, kept)
