# -*- coding: utf-8 -*-
# Target: Odoo 20.0 Community Edition
from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    vn_vat_exempt = fields.Boolean(
        string='VAT exempt',
        help="Không chịu thuế GTGT. Sales with this tax are declared on item "
             "26 of form 01/GTGT instead of the 0% item 29.")
