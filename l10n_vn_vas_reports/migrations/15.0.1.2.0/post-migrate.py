# -*- coding: utf-8 -*-
"""Point the TT133 statements' "Thuyết minh" column at the notes (B09-DNN).

TT133 Điều 81 mục 2.5.2 c asks that every item on the statements lead to its
note. 15.0.1.2.0 ships the notes and fills the column on B01a-DNN, B01b-DNN
and B02-DNN with the number of the matching item (V.1, VI.3, …). The mapping
data is noupdate="1", so on a database that already has the lines this script
fills the column itself — only where it is still empty: a reference a company
typed in, for notes it numbers its own way, stays.

The notes template itself needs nothing here: its records are new, and new
records are created by the data files even in a noupdate block.
"""
import logging

_logger = logging.getLogger(__name__)

NOTE_REFS = {'l10n_vn_vas_reports.b01adnn_110': 'V.1',
 'l10n_vn_vas_reports.b01adnn_121': 'V.2',
 'l10n_vn_vas_reports.b01adnn_122': 'V.2',
 'l10n_vn_vas_reports.b01adnn_124': 'V.2',
 'l10n_vn_vas_reports.b01adnn_131': 'V.3',
 'l10n_vn_vas_reports.b01adnn_132': 'V.3',
 'l10n_vn_vas_reports.b01adnn_134': 'V.3',
 'l10n_vn_vas_reports.b01adnn_135': 'V.3',
 'l10n_vn_vas_reports.b01adnn_141': 'V.4',
 'l10n_vn_vas_reports.b01adnn_151': 'V.5',
 'l10n_vn_vas_reports.b01adnn_152': 'V.5',
 'l10n_vn_vas_reports.b01adnn_161': 'V.6',
 'l10n_vn_vas_reports.b01adnn_162': 'V.6',
 'l10n_vn_vas_reports.b01adnn_170': 'V.7',
 'l10n_vn_vas_reports.b01adnn_182': 'V.8',
 'l10n_vn_vas_reports.b01adnn_311': 'V.9',
 'l10n_vn_vas_reports.b01adnn_312': 'V.9',
 'l10n_vn_vas_reports.b01adnn_313': 'V.10',
 'l10n_vn_vas_reports.b01adnn_315': 'V.9',
 'l10n_vn_vas_reports.b01adnn_316': 'V.11',
 'l10n_vn_vas_reports.b01adnn_318': 'V.12',
 'l10n_vn_vas_reports.b01adnn_400': 'V.13',
 'l10n_vn_vas_reports.b01bdnn_110': 'V.1',
 'l10n_vn_vas_reports.b01bdnn_121': 'V.2',
 'l10n_vn_vas_reports.b01bdnn_122': 'V.2',
 'l10n_vn_vas_reports.b01bdnn_123': 'V.2',
 'l10n_vn_vas_reports.b01bdnn_131': 'V.3',
 'l10n_vn_vas_reports.b01bdnn_132': 'V.3',
 'l10n_vn_vas_reports.b01bdnn_133': 'V.3',
 'l10n_vn_vas_reports.b01bdnn_134': 'V.3',
 'l10n_vn_vas_reports.b01bdnn_141': 'V.4',
 'l10n_vn_vas_reports.b01bdnn_152': 'V.8',
 'l10n_vn_vas_reports.b01bdnn_211': 'V.3',
 'l10n_vn_vas_reports.b01bdnn_212': 'V.3',
 'l10n_vn_vas_reports.b01bdnn_214': 'V.3',
 'l10n_vn_vas_reports.b01bdnn_221': 'V.5',
 'l10n_vn_vas_reports.b01bdnn_222': 'V.5',
 'l10n_vn_vas_reports.b01bdnn_231': 'V.6',
 'l10n_vn_vas_reports.b01bdnn_232': 'V.6',
 'l10n_vn_vas_reports.b01bdnn_240': 'V.7',
 'l10n_vn_vas_reports.b01bdnn_252': 'V.2',
 'l10n_vn_vas_reports.b01bdnn_253': 'V.2',
 'l10n_vn_vas_reports.b01bdnn_260': 'V.8',
 'l10n_vn_vas_reports.b01bdnn_411': 'V.9',
 'l10n_vn_vas_reports.b01bdnn_412': 'V.9',
 'l10n_vn_vas_reports.b01bdnn_413': 'V.10',
 'l10n_vn_vas_reports.b01bdnn_415': 'V.9',
 'l10n_vn_vas_reports.b01bdnn_416': 'V.11',
 'l10n_vn_vas_reports.b01bdnn_417': 'V.12',
 'l10n_vn_vas_reports.b01bdnn_421': 'V.9',
 'l10n_vn_vas_reports.b01bdnn_422': 'V.9',
 'l10n_vn_vas_reports.b01bdnn_424': 'V.9',
 'l10n_vn_vas_reports.b01bdnn_425': 'V.11',
 'l10n_vn_vas_reports.b01bdnn_426': 'V.12',
 'l10n_vn_vas_reports.b01bdnn_500': 'V.13',
 'l10n_vn_vas_reports.b02dnn_01': 'VI.1',
 'l10n_vn_vas_reports.b02dnn_02': 'VI.2',
 'l10n_vn_vas_reports.b02dnn_11': 'VI.3',
 'l10n_vn_vas_reports.b02dnn_21': 'VI.4',
 'l10n_vn_vas_reports.b02dnn_22': 'VI.5',
 'l10n_vn_vas_reports.b02dnn_24': 'VI.6',
 'l10n_vn_vas_reports.b02dnn_31': 'VI.7',
 'l10n_vn_vas_reports.b02dnn_32': 'VI.8',
 'l10n_vn_vas_reports.b02dnn_51': 'VI.9'}


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
    _logger.info('Statement mappings: note references filled on %d lines, '
                 '%d already had one.', filled, kept)
