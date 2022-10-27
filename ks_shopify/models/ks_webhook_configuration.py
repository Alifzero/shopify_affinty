# -*- coding: utf-8 -*-

import base64

from odoo import api, models, fields
from odoo.exceptions import ValidationError
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class KsShopifyWebhooksConfiguration(models.Model):
    _name = 'ks.shopify.webhooks.configuration'
    _description = 'WebHook Configuration'
    _rec_name = 'name'

    name = fields.Char(string="Name", required=True)
    operations = fields.Selection([('orders/create', 'Order Create'),
                                   ('orders/updated', 'Order Update'),
                                   ('products/create', 'Product Create'),
                                   ('products/update', 'Product Update'),
                                   ('customers/create', 'Customer Create'),
                                   ('collections/create', 'Collections Create'),
                                   ('collections/update', 'Collections Update'),
                                   ('customers/update', 'Customer Update')],
                                  string="Operation", required=True, default=False)

    status = fields.Selection([('active', 'Active'),
                               ('delete', 'Delete'),
                               ('disabled', 'Disabled')], string="Hook Status", default='disabled',
                              readonly=True)

    base_url = fields.Char(string="Webhook Url", readonly=True, compute='_ks_compute_base_url')

    ks_instance_id = fields.Many2one("ks.shopify.connector.instance", string="Shopify Instance", readonly=True)
    ks_shopify_id = fields.Char(string="Shopify Id", readonly=True)

    @api.depends('operations')
    def _ks_compute_base_url(self):
        """
        Computes URL for controllers webhook to request data
        :return:
        """
        for rec in self:
            if rec.ks_instance_id.ks_instance_state in ['active', 'connected']:
                ks_base = rec.env['ir.config_parameter'].sudo().get_param('web.base.url')
                ks_base_updated = ks_base.split("//")
                if len(ks_base_updated)>1:
                    ks_base = 'https://'+ks_base_updated[1]
                if rec.operations:
                    selection_list = rec.operations.split('/')
                    rec.base_url = '%s/shopify_hook/%s/%s/%s/%s/%s' % (ks_base,
                                                                       base64.urlsafe_b64encode(
                                                                           self.env.cr.dbname.encode("utf-8")).decode(
                                                                           "utf-8"),
                                                                       str(self.env.user.id),
                                                                       rec.ks_instance_id.id,
                                                                       selection_list[0],
                                                                       selection_list[1])
                else:
                    rec.base_url = ''
            else:
                rec.base_url = ''
                _logger.info("Instance should be Active or Connected")

    def write(self, vals):
        """
        Updates data on both webhook and odoo
        :param vals: creation data
        :return: rec
        """
        rec = super(KsShopifyWebhooksConfiguration, self).write(vals)
        if self.env.context.get('webhook_delete'):
            return rec
        '''data in vals will be used for updation
            self will have shopify_id for which we want to update webhook
        '''
        instance_id = self.ks_instance_id
        if not instance_id:
            return rec
        webhook_id = self.ks_shopify_id if self.ks_shopify_id else vals.get('ks_shopify_id')
        if self.ks_shopify_id or vals.get('ks_shopify_id'):
            data = self.ks_shopify_webhook_data(vals)
            ks_response_data = self.ks_update_webhook(instance_id, webhook_id, data)
        else:
            data = {
                'webhook': {
                    'format': 'json',
                    'topic': self.operations,
                    'address': self.base_url
                }
            }
            response_data = self.ks_create_webhook(self.ks_instance_id, data)
            if response_data:
                self.update({'ks_shopify_id': response_data.get("id")})
            else:
                raise ValidationError("Fatal Error! While Syncing Webhook through Shopify")
        return rec

    def params_sync(self):
        """
        Syncs parameter of webhook and create on Shopify
        :return: None
        """
        data = self.ks_shopify_webhook_data(self.base_url)
        response_data = self.ks_create_webhook(self.ks_instance_id, data)
        if response_data:
            self.update({
                'ks_shopify_id': response_data.get('id'),
                'status': 'active'
            })

    def params_unsync(self):
        """
        Syncs parameter of webhook and create on Shopify
        :return: None
        """
        json_response = self.env['ks.api.handler'].ks_del_data(self.ks_instance_id, "webhooks", id=self.ks_shopify_id)
        if not json_response:
            self = self.with_context(webhook_delete=True)
            self.update({
                'ks_shopify_id': False,
                'status': 'delete'
            })

    def ks_shopify_webhook_data(self, base_url):
        """
        Create a dictionary data which is posted on the Shopify
        :param name: Name of the Webhook
        :param base_url: Base URL of the webhook
        :return: dictionary
        """
        return {
            'webhook': {
                'format': 'json',
                'topic': self.operations,
                'address': self.base_url
            }
        }

    def ks_create_webhook(self, instance, data):
        """
        :param instance: shopify connector instance
        :param data: json data for shopify
        :return: json response from the api
        """
        try:
            json_response = self.env['ks.api.handler'].ks_post_data(instance, "webhooks", data)
            if json_response:
                return json_response.get('webhook')
        except Exception as e:
            raise e

    def ks_update_webhook(self, instance, id, data):
        """
        :param instance: shopify connector instance
        :param id: id of the webhook
        :param data: json data for shopify
        :return: json response from the api
        """
        try:
            json_response = self.env['ks.api.handler'].ks_put_data(instance, "webhooks", data, id)
            if json_response:
                return json_response.get('webhook')
        except Exception as e:
            raise e
