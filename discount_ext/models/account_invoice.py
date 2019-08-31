import json
from lxml import etree
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_compare
from odoo.tools.misc import formatLang

from odoo.exceptions import UserError, RedirectWarning, ValidationError

import odoo.addons.decimal_precision as dp
import logging

class AccountInvoiceDiscountInherited(models.Model):
    _inherit = 'account.invoice'

    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 
                 'currency_id', 'company_id', 'date_invoice', 'type', 'my_discount_amnt','discount')
    def _compute_amount(self):
        round_curr = self.currency_id.round
        self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        self.amount_tax = sum(round_curr(line.amount) for line in self.tax_line_ids)
        if self.discount > 0:
            amount_total = self.amount_untaxed + self.amount_tax - self.discount
            self.round_off_amount = self.env['rounding.off'].round_off_value_to_nearest(amount_total)
            self.amount_total = self.amount_untaxed + self.amount_tax - self.discount + self.round_off_amount
        elif self.my_discount_type == 'categ_amnt':
            self.amount_total = self.amount_untaxed + self.amount_tax 
        else:
            self.amount_total = self.amount_untaxed + self.amount_tax - self.my_discount_amnt
        amount_total_company_signed = self.amount_total
        amount_untaxed_signed = self.amount_untaxed
        if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
            currency_id = self.currency_id.with_context(date=self.date_invoice)
            amount_total_company_signed = currency_id.compute(self.amount_total, self.company_id.currency_id)
            amount_untaxed_signed = currency_id.compute(self.amount_untaxed, self.company_id.currency_id)
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_total_company_signed = amount_total_company_signed * sign
        self.amount_total_signed = self.amount_total * sign
        self.amount_untaxed_signed = amount_untaxed_signed * sign
    
    
    @api.onchange('mydiscount_id')
    def onchange_disc_id(self):
        '''Calculate discount amount, when discount is entered in terms of %'''
        if self.mydiscount_id:
            for order in self:
                for lines in order.invoice_line_ids:
                    tmp_id = lines.product_id.product_tmpl_id.id
                    tmp_obj = self.env['product.template'].search([('id','=',tmp_id)],limit=1)
                    cate_obj = self.env['product.category'].search([('id','=',tmp_obj.categ_id.id)],limit=1)
                    disc_obj = self.env['discount.setup'].search([('id','=',order.mydiscount_id.id)],limit=1)
                    for rec in disc_obj:
                        for line in rec.discount_per_ids:
                            if cate_obj.id == line.category_id.id:
                                lines.discount = line.discount_per
    # @api.depends('invoice_line_ids')
    # def onchange_invoice_lines(self):
    #     amount_total = self.amount_untaxed + self.amount_tax
    #     if self.discount_type == 'fixed':
    #         self.discount_percentage = (self.discount / amount_total) * 100
    #     elif self.discount_type == 'percentage':
    #         self.discount = amount_total * self.discount_percentage / 100
      

    # @api.onchange('my_discount_percentage','my_fxd_discount_amnt')
    # def onchange_discount_my_discount(self):
    #     amount_total = self.amount_untaxed + self.amount_tax
    #     if self.my_discount_type == 'fixed_amnt':
    #         self.my_discount_amnt = self.my_fxd_discount_amnt
    #     elif self.my_discount_type == 'percentage_amnt':
    #         self.my_discount_amnt = amount_total * (self.my_discount_percentage / 100)

    
    @api.one
    @api.depends('invoice_line_ids.discount_line_amount','my_discount_percentage','my_fxd_discount_amnt','my_discount_type')
    def _compute_my_disc_amount(self):

        if self.my_discount_type == 'none_amnt':
                self.mydiscount_id = False
        if self.my_discount_type == 'categ_amnt':
                self.my_discount_amnt =  sum(line.discount_line_amount for line in self.invoice_line_ids)
        amount_total = self.amount_untaxed + self.amount_tax
        if self.my_discount_type == 'fixed_amnt':
            self.mydiscount_id = False
            self.my_discount_amnt = self.my_fxd_discount_amnt
        elif self.my_discount_type == 'percentage_amnt':
            self.mydiscount_id = False
            self.my_discount_amnt = amount_total * ((self.my_discount_percentage or 0.0) / 100)


    mydiscount_id = fields.Many2one('discount.setup',string='Discount Category',readonly=True)
    my_discount_type = fields.Selection([('none_amnt', 'No Discount'),
                                      ('fixed_amnt', 'Fixed'),
                                      ('percentage_amnt', 'Percentage'),('categ_amnt', 'Category')],
                                     string="Discount Method",
                                     default='none_amnt',readonly=True)
    my_discount_amnt = fields.Monetary(string="Discount",compute='_compute_my_disc_amount',store=True,readonly=True)
    # discount_cate_amount = fields.Monetary(string="Discount Amount",compute='_compute_my_disc_amount',store=True)
    my_discount_percentage = fields.Float(string="Discount Percentage",readonly=True)
    my_fxd_discount_amnt = fields.Monetary(string="Discount Amount",readonly=True)
    # my_disc_acc_id = fields.Many2one('account.account',
    #                               string="Discount Account Head")
    def _get_refund_common_fields(self):
        return ['partner_id', 'payment_term_id', 'account_id', 'currency_id', 'journal_id','mydiscount_id','my_discount_type','my_discount_percentage','my_disc_acc_id','my_fxd_discount_amnt']

    @api.multi
    def action_move_create(self):
        #This method is overriden to pass the Discount Journal Entry.
        """ Creates invoice related analytics and financial move lines """
        account_move = self.env['account.move']

        for inv in self:
            if not inv.journal_id.sequence_id:
                raise UserError(_('Please define sequence on the journal related to this invoice.'))
            if not inv.invoice_line_ids:
                raise UserError(_('Please create some invoice lines.'))
            if inv.move_id:
                continue

            ctx = dict(self._context, lang=inv.partner_id.lang)

            if not inv.date_invoice:
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            company_currency = inv.company_id.currency_id

            # create move lines (one per invoice line + eventual taxes and analytic lines)
            iml = inv.invoice_line_move_line_get()
            iml += inv.tax_line_move_line_get()

            diff_currency = inv.currency_id != company_currency
            # create one move line for the total and possibly adjust the other lines amount
            total, total_currency, iml = inv.with_context(ctx).compute_invoice_totals(company_currency, iml)

            name = inv.name or '/'
            if inv.payment_term_id:
                totlines = inv.with_context(ctx).payment_term_id.with_context(currency_id=company_currency.id).compute(total, inv.date_invoice)[0]
                res_amount_currency = total_currency
                ctx['date'] = inv._get_currency_rate_date()
                for i, t in enumerate(totlines):
                    if inv.currency_id != company_currency:
                        amount_currency = company_currency.with_context(ctx).compute(t[1], inv.currency_id)
                    else:
                        amount_currency = False

                    # last line: add the diff
                    res_amount_currency -= amount_currency or 0
                    if i + 1 == len(totlines):
                        amount_currency += res_amount_currency

                    iml.append({
                        'type': 'dest',
                        'name': name,
                        'price': t[1],
                        'account_id': inv.account_id.id,
                        'date_maturity': t[0],
                        'amount_currency': diff_currency and amount_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'invoice_id': inv.id
                    })
            else:
                iml.append({
                    'type': 'dest',
                    'name': name,
                    'price': total,
                    'account_id': inv.account_id.id,
                    'date_maturity': inv.date_due,
                    'amount_currency': diff_currency and total_currency,
                    'currency_id': diff_currency and inv.currency_id.id,
                    'invoice_id': inv.id
                })
            part = self.env['res.partner']._find_accounting_partner(inv.partner_id)
            line = [(0, 0, self.line_get_convert(l, part.id)) for l in iml]
            line = inv.group_lines(iml, line)

            journal = inv.journal_id.with_context(ctx)
            line = inv.finalize_invoice_move_lines(line)
            
            date = inv.date or inv.date_invoice
            move_vals = {
                'ref': inv.reference,
                'line_ids': line,
                'journal_id': journal.id,
                'date': date,
                'narration': inv.comment,
            }
            ctx['company_id'] = inv.company_id.id
            ctx['invoice'] = inv
            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)
            #=============Customized code starts=========
            # if inv.my_discount_amnt and inv.type =='out_invoice':
            #     move_line = move.line_ids.filtered(lambda l:l.name=='/')
            #     move_line.debit -= inv.my_discount_amnt
            #     move_line_vals = {
            #     'name':'Discount',
            #     'company_id':move.company_id.id,
            #     'account_id':inv.my_disc_acc_id.id,
            #     'debit':inv.my_discount_amnt,
            #     'date_maturity':date,
            #     'currency_id': diff_currency and inv.currency_id.id,
            #     'invoice_id': inv.id,
            #     'partner_id':move_line.partner_id.id,
            #     'move_id':move.id,
            #     }
            #     self.env['account.move.line'].create(move_line_vals)
            # elif inv.my_discount_amnt and inv.type =='out_refund':
            #     move_line = move.line_ids.filtered(lambda l:l.name==inv.name)
            #     move_line.credit -= inv.my_discount_amnt
            #     move_line_vals = {
            #     'name':'Discount',
            #     'company_id':move.company_id.id,
            #     'account_id':inv.my_disc_acc_id.id,
            #     'credit':inv.my_discount_amnt,
            #     'date_maturity':date,
            #     'currency_id': diff_currency and inv.currency_id.id,
            #     'invoice_id': inv.id,
            #     'partner_id':move_line.partner_id.id,
            #     'move_id':move.id,
            #     }
            #     self.env['account.move.line'].create(move_line_vals)
            #===========Customized code ends=============
            # Pass invoice in context in method post: used if you want to get the same
            # account move reference when creating the same invoice after a cancelled one:
            move.post()
            # make the invoice point to that move
            vals = {
                'move_id': move.id,
                'date': date,
                'move_name': move.name,
            }
            inv.with_context(ctx).write(vals)
        return True


class AccountInvoiceLineDiscountInherited(models.Model):
    _inherit = 'account.invoice.line'

    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
        'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
        'invoice_id.date_invoice', 'invoice_id.date')
    def _compute_price(self):
        currency = self.invoice_id and self.invoice_id.currency_id or None
        price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        taxes = False
        if self.invoice_line_tax_ids:
            taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
        self.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else self.quantity * price
        if self.invoice_id.currency_id and self.invoice_id.company_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
            price_subtotal_signed = self.invoice_id.currency_id.with_context(date=self.invoice_id._get_currency_rate_date()).compute(price_subtotal_signed, self.invoice_id.company_id.currency_id)
        sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
        self.price_subtotal_signed = price_subtotal_signed * sign
        if self.discount:
            self.discount_line_amount = ((self.discount or 0.0 )/100) * self.quantity * self.price_unit

    
    @api.onchange('product_id')
    def _onchange_product_discount_id(self):
        # part = self.invoice_id.partner_id
        discount_mycateg_id = self.invoice_id.mydiscount_id
        if discount_mycateg_id:
            tmp_id = self.product_id.product_tmpl_id.id
            tmp_obj = self.env['product.template'].search([('id','=',tmp_id)],limit=1)
            cate_obj = self.env['product.category'].search([('id','=',tmp_obj.categ_id.id)],limit=1)
            disc_obj = self.env['discount.setup'].search([('id','=',self.invoice_id.mydiscount_id.id)],limit=1)
            for rec in disc_obj:
                for line in rec.discount_per_ids:
                    if cate_obj.id == line.category_id.id:
                        self.discount = line.discount_per
    discount_line_amount = fields.Monetary(string="Discount Per Line",compute='_compute_price',store=True)
     

