from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class KsShopifyPaymentGateway(models.Model):
    _name = 'ks.shopify.payment.gateway'
    _description = 'Payment Gateway'
    _rec_name = 'ks_name'
    _order = 'create_date desc'

    ks_name = fields.Char(string="Payment Gateway Name")
    ks_code = fields.Char(string="Payment Gateway Code")
    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Instance",
                                          help=_("Shopify Connector Instance reference"),
                                          ondelete='cascade')
    ks_company_id = fields.Many2one("res.company", string="Company", compute="_compute_company", store=True,
                                    help="Displays Company Name")

    @api.depends('ks_shopify_instance')
    def _compute_company(self):
        """
        Computes company for the Shopify Auto Product Syncing Configuration
        :return:
        """
        for rec in self:
            if rec.ks_shopify_instance.ks_company_id:
                rec.ks_company_id = rec.ks_shopify_instance.ks_company_id.id
            else:
                rec.ks_company_id = self._context.get('company_id', self.env.company.id)

    def ks_manage_shopify_payment_gateway_import(self, instance, order_data):
        """
        :param instance: shopify instance
        :param order_data: order json data from the api
        :return: ks.shopify.payment.gateway() record
        """
        try:
            if order_data and instance:
                payment_data = order_data.get('payment_gateway_names', False)
                if payment_data and len(payment_data):
                    payment_gateway = self.search([('ks_name', 'in', payment_data),
                                                   ('ks_shopify_instance', '=', instance.id)])
                    if payment_gateway:
                        # Run update command here
                        data = self.ks_map_payment_gateway_data_for_odoo(instance, payment_data)
                        payment_gateway.write(data)
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='update',
                                                                               ks_status='success',
                                                                               ks_operation_flow='shopify_to_odoo',
                                                                               ks_type='payment_gateway',
                                                                               ks_shopify_instance=instance,
                                                                               ks_shopify_id='',
                                                                               ks_record_id=payment_gateway.id,
                                                                               ks_message="Shopify Import Update successful",
                                                                               ks_model='ks.shopify.payment.gateway')
                        return payment_gateway
                    else:
                        data = self.ks_map_payment_gateway_data_for_odoo(instance, payment_data)
                        payment_gateway = self.create(data)
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create',
                                                                               ks_status='success',
                                                                               ks_operation_flow='shopify_to_odoo',
                                                                               ks_type='payment_gateway',
                                                                               ks_shopify_instance=instance,
                                                                               ks_shopify_id='',
                                                                               ks_record_id=payment_gateway.id,
                                                                               ks_message="Shopify Import Create successful",
                                                                               ks_model='ks.shopify.payment.gateway')
                        return payment_gateway
                else:
                    return False
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='import',
                                                                   ks_status='failed',
                                                                   ks_operation_flow='shopify_to_odoo',
                                                                   ks_type='payment_gateway',
                                                                   ks_shopify_instance=instance,
                                                                   ks_shopify_id='',
                                                                   ks_record_id=0,
                                                                   ks_message="Shopify Import failed because :- %s" % str(
                                                                       e),
                                                                   ks_model='ks.shopify.payment.gateway')

    def ks_map_payment_gateway_data_for_odoo(self, instance, json_data):
        """
        :param instance: shopify instance
        :param json_data: order json data
        :return: odoo compatible data
        """
        try:
            data = {
                'ks_name' : json_data[0],
                'ks_code' : '-'.join(json_data[0].upper().split(" ")),
                'ks_shopify_instance' : instance.id
            }
            return data

        except Exception as e:
            raise e
