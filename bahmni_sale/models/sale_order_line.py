# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import models, fields, api
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF, float_is_zero


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
            if line.discount:
                line.discount_line_amount = ((line.discount or 0.0 )/100) * line.product_uom_qty * line.price_unit
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })
    ################sagar edit
    @api.onchange('product_id')
    def _onchange_product_discount_id(self):
        # part = self.invoice_id.partner_id
        discount_mycateg_id = self.order_id.mydiscount_id
        if discount_mycateg_id:
            tmp_id = self.product_id.product_tmpl_id.id
            tmp_obj = self.env['product.template'].search([('id','=',tmp_id)],limit=1)
            cate_obj = self.env['product.category'].search([('id','=',tmp_obj.categ_id.id)],limit=1)
            disc_obj = self.env['discount.setup'].search([('id','=',self.order_id.mydiscount_id.id)],limit=1)
            for rec in disc_obj:
                for line in rec.discount_per_ids:
                    if cate_obj.id == line.category_id.id:
                        self.discount = line.discount_per

    external_id = fields.Char(string="External ID",
                              help="This field is used to store encounter ID of bahmni api call")
    external_order_id = fields.Char(string="External Order ID",
                                    help="This field stores the order ID got from api call.")
    order_uuid = fields.Char(string="Order UUID",
                             help="Field for generating a random unique ID.")
    dispensed = fields.Boolean(string="Dispensed",
                               help="Flag to identify whether drug order is dispensed or not.")
    lot_id = fields.Many2one('stock.production.lot', string="Batch No")
    expiry_date = fields.Datetime(string="Expiry date")
    doctor_id = fields.Many2one('doctor.setup',string='Doctor')
    discount_line_amount = fields.Monetary(string="Discount Per Line",compute='_compute_amount',store=True)

    @api.onchange('lot_id')
    def onchange_lot_id(self):
        if self.lot_id:
            self.expiry_date = self.lot_id.life_date

    @api.model
    def get_available_batch_details(self, product_id, sale_order):
        context = self._context.copy() or {}
        sale_order = self.env['sale.order'].browse(sale_order)
        context['location_id'] = sale_order.location_id and sale_order.location_id.id or False
        context['search_in_child'] = True
        stock_prod_lot = self.env['stock.production.lot']#.search([('product_id','=',product_id)])

        already_used_batch_ids = []
        for line in sale_order.order_line:
            if line.lot_id:
                id = line.lot_id.id
                already_used_batch_ids.append(id.__str__())

        query = ['&', ('product_id', '=', product_id), 
                 ('id', 'not in', already_used_batch_ids)]\
                 if len(already_used_batch_ids) > 0 else [('product_id','=',product_id)]
        for prodlot in stock_prod_lot.with_context(context).search(query):
            if(prodlot.life_date and datetime.strptime(prodlot.life_date, DTF) >= datetime.today() and prodlot.stock_forecast > 0):
                return prodlot
        return None
    
    @api.multi
    def invoice_line_create(self, invoice_id, qty):
        """
        Create an invoice line. The quantity to invoice can be positive (invoice) or negative
        (refund).
 
        :param invoice_id: integer
        :param qty: float quantity to invoice
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if not float_is_zero(qty, precision_digits=precision):
                vals = line._prepare_invoice_line(qty=qty)
                vals.update({'invoice_id': invoice_id, 
                             'sale_line_ids': [(6, 0, [line.id])],
                             'lot_id': line.lot_id.id,
                             'expiry_date': line.expiry_date,
                            'doctor_id': line.doctor_id.id})
                self.env['account.invoice.line'].create(vals)
