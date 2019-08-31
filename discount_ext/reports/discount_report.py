from odoo import api, fields, models, _

from datetime import  timedelta,date,time
import datetime
class DiscountReportWizard(models.TransientModel):
    _name = "discount.wizard"
    _description = "Discont Wizard"

    
    date_from = fields.Date(string='Start Date', required=True,default=date.today())
    date_to = fields.Date(string='End Date', required=True,default=date.today())
    salesperson_id = fields.Many2one('res.users',string='Salesperson', required=True)
    @api.multi
    def check_report(self):
        data = {}
        data['form'] = self.read(['date_from','salesperson_id' ,'date_to'])[0]
        return self._print_report(data)

    def _print_report(self, data):
        data['form'].update(self.read(['date_from', 'date_to'])[0])
        return self.env['report'].get_action(self, 'discount_ext.report_discount', data=data)