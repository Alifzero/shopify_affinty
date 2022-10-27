import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date

_logger = logging.getLogger(__name__)


class KsSalesPrintReportWizard(models.TransientModel):
    _name = "ks.sale.print.report.wizard"
    _description = "Sales Print Report"
    _rec_name = 'ks_shopify_instance'

    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Instance id", required=True,
                                          domain=[('ks_instance_state', '=', 'active')])

    def action_sales_report_generate(self):
        return self.env.ref('ks_shopify.ks_shopify_inst_sales_report_id').report_action(self)

    def get_today_date(self):
        return str(date.today())

    def get_order_count_per_instance(self, instance_id):
        """
        Counts orders
        :param instance_id: shopify instance
        :return: counts of orders per instance
        """
        return self.env['sale.order'].search_count([('ks_shopify_instance', '=', instance_id),
                                                    ('state', '=', 'sale')])

    def get_total_orders(self):
        """
        Get total orders for an instance
        :return: count
        """
        count = 0
        for rec in self.ks_shopify_instance:
            count += self.env['sale.order'].search_count([('ks_shopify_instance', '=', rec.id)])
        return count

    def get_quotations_count_per_instance(self, instance_id):
        return self.env['sale.order'].search_count([('ks_shopify_instance', '=', instance_id),
                                                    ('state', '=', 'draft')])


    def get_order_lines(self, instance_id):
        """
        fetched order lines
        :param instance_id: shopify instance
        :return: order lines
        """
        domain = [('state', 'not in', ['cancel', 'draft']),
                  ('ks_shopify_instance', '=', instance_id)]
        return self.env['sale.order'].search(domain)


