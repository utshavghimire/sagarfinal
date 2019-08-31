import json
from lxml import etree
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _


from odoo.exceptions import UserError, RedirectWarning, ValidationError

import logging

class DiscountSetup(models.Model):
    _name = 'discount.setup'

    name = fields.Char(string='Discount Name',required=True)
    code = fields.Char(string='Discount Code',required=True)
    discount_per_ids = fields.One2many('discount.setup.lines','discount_per_id',string='discount lines')

class DiscountSetupLines(models.Model):
    _name = 'discount.setup.lines'

    # name = fields.Char(string='Discount Name',required=True)
    category_id = fields.Many2one('product.category',string='Product Category',required=True)
    discount_per = fields.Float(string='Discount Percentage',required=True)
    discount_per_id = fields.Many2one('discount.setup',string='disc_id')