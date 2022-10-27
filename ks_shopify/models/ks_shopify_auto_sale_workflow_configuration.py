# -*- coding: utf-8 -*-

from odoo import fields, models, api


class KsBaseSaleWorkFlowConfiguration(models.Model):
    _name = 'ks.auto.sale.workflow.configuration'
    _description = 'Shopify Auto Sale WorkFlow Configuration'

    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Shopify Instance", ondelete='cascade')
    ks_sale_workflow_id = fields.Many2one("ks.sale.workflow.configuration", string="Sale Workflow", ondelete='cascade')
    ks_shopify_payment_id = fields.Many2one("ks.shopify.payment.gateway", string="Payment Gateway", ondelete='cascade',
                                        domain="[('ks_shopify_instance', '=', ks_shopify_instance)]")
    ks_shopify_order_status = fields.Many2many("ks.order.status", string="Order Status")
    ks_order_import_type = fields.Selection(related='ks_shopify_instance.ks_order_import_type',
                                            string="Import Orders through")

    @api.onchange('ks_sale_workflow_id')
    def ks_onchange_order_status(self):
        """
        Return the domain for ks_sale_workflow_id in terms of order status
        :return: domain
        """
        instance = False
        for rec in self:
            if self.env.context.get('instance'):
                instance = self.env['ks.shopify.connector.instance'].browse(self.env.context.get('instance'))
            else:
                instance = rec.ks_shopify_instance if type(
                    rec.ks_shopify_instance.id) == int else rec.ks_shopify_instance._origin
            return {'domain': {'ks_shopify_order_status': [('id', 'in', rec.ks_shopify_instance.ks_order_status.ids)],
                               'ks_shopify_payment_id': [('id', 'in', self.env['ks.shopify.payment.gateway'].search(
                                   [('ks_shopify_instance', '=', instance.id)]).ids)]}}


class KsShopifyOrderStatus(models.Model):
    _name = "ks.order.status"
    _description = "Handles Order Status"
    _rec_name = "name"

    status = fields.Selection([('open', "Open"),
                               ('paid', "Paid"),
                               ("completed", "Completed"),
                               ("pending", "Pending")], string="Status")
    name = fields.Char(string="Status Name")
