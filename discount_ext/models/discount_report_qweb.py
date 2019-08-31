# -*- coding: utf-8 -*-

import time
from odoo import api, models
from dateutil.parser import parse
from odoo.exceptions import UserError
from datetime import  timedelta,date,time
import datetime

class ReportDiscount(models.AbstractModel):
    _name = 'report.discount_ext.report_discount'
    
    @api.model
    def render_html(self, docids, data=None):
        self.model = self.env.context.get('active_model')
        docs = self.env[self.model].browse(self.env.context.get('active_id'))
        dt1 = datetime.datetime.strptime(docs.date_from, "%Y-%m-%d").date()
        dt2 = datetime.datetime.strptime(docs.date_to, "%Y-%m-%d").date()
        tm = datetime.time(23, 59, 59)
        m_date_from = datetime.datetime.combine(dt1, datetime.datetime.min.time())
        m_date_to = datetime.datetime.combine(dt2, tm)
        if docs.salesperson_id:
                domain = [('date_invoice','>=',m_date_from),('date_invoice','<=',m_date_to),('state','in',('open','paid')),('user_id','=',docs.salesperson_id.id),('type','in',('out_invoice','out_refund'))]
                inv_objs = self.env['account.invoice'].search(domain)
                result_dict = {}
                result = []
                s1 = s2 =s3 =s4 = 0.00
                for invoice in inv_objs:
                        if invoice.type == 'out_invoice' and invoice.state == 'open':
                                s1 = s1 + invoice.amount_total
                        elif invoice.type == 'out_invoice' and invoice.state == 'paid':
                                s2 = s2 + invoice.amount_total
                        if invoice.type == 'out_refund' and invoice.state == 'open':
                                s3 = s3 + invoice.amount_total
                        elif invoice.type == 'out_refund' and invoice.state == 'paid':
                                s4 = s4 + invoice.amount_total
                result_dict['login'] = docs.salesperson_id.login  
                result_dict['open_sum'] = s1 - s3
                result_dict['paid_sum'] = s2 - s4
                result.append(result_dict)
        else:
                domain = [('date_invoice','>=',m_date_from),('date_invoice','<=',m_date_to),('state','in',('open','paid')),('type','in',('out_invoice','out_refund'))]
        
                inv_objs = self.env['account.invoice'].search(domain)
                result_dict = {}
                result = []
                s1 = s2 =s3 =s4 = 0.00
                for invoice in inv_objs:
                        if invoice.type == 'out_invoice' and invoice.state == 'open':
                                s1 = s1 + invoice.amount_total
                        elif invoice.type == 'out_invoice' and invoice.state == 'paid':
                                s2 = s2 + invoice.amount_total
                        if invoice.type == 'out_refund' and invoice.state == 'open':
                                s3 = s3 + invoice.amount_total
                        elif invoice.type == 'out_refund' and invoice.state == 'paid':
                                s4 = s4 + invoice.amount_total
                result_dict['login'] = docs.salesperson_id.login  
                result_dict['open_sum'] = s1 - s3
                result_dict['paid_sum'] = s2 - s4
                result.append(result_dict)
        # self._cr.execute("""select ru.login,ai.state,sum(amount_total) from res_users ru left join account_invoice ai on ai.user_id = ru.id 
        #  where ai.state in ('open','paid') and ai.type in ('out_invoice','out_refund)' and ai.date_invoice>=%s and ai.date_invoice<=%s and ru.id = %s group by ru.login,ai.state""", (m_date_from,m_date_to,docs.salesperson_id.id))
        # result =  self._cr.dictfetchall()
        # inv_records = []
        # orders = self.env['account.invoice.line'].search([('user_id', '=', docs.salesperson_id.id)])
        # if docs.date_from and docs.date_to:
        #     for order in orders:
        #         if parse(docs.date_from) <= parse(order.date_order) and parse(docs.date_to) >= parse(order.date_order):
        #             sales_records.append(order);

        # else:
        #     raise UserError("Please enter duration")
        
        docargs = {
            'doc_ids': self.ids,
            'doc_model': self.model,
            'docs': docs,
            'time': time,
            'orders': result
        }
        return self.env['report'].render('discount_ext.report_discount', docargs)
