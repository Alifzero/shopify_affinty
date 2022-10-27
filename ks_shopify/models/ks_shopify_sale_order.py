# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
from bs4 import BeautifulSoup


_logger = logging.getLogger(__name__)


class KsSaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    def ks_domain_set(self):
        return [('ks_shopify_instance', '=', self.ks_shopify_instance.id)]

    ks_order_name = fields.Char("Shopify Order Name")
    ks_shopify_order_id = fields.Char('Shopify Id', readonly=True, default=0, copy=False, help="Displays Shopify ID")
    ks_shopify_draft_order_id = fields.Char('Shopify Draft Id', readonly=True, default=0, copy=False,
                                            help="Displays Shopify Draft ID")
    ks_is_draft = fields.Boolean("Is Draft Order?")
    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Instance", readonly=False,
                                          help=_("Shopify Connector Instance reference"))
    ks_shopify_status = fields.Selection([('open', 'Open'), ('pending', 'Pending'), ('paid', 'Paid'),
                                          ('cancelled', 'Cancelled'), ('refunded', 'Refunded'),
                                          ('completed', 'Completed'), ('partially_paid', 'Partially Paid')],
                                         string="Shopify Status", default='pending', copy=False,
                                         help="Displays Shopify Order Status")
    ks_shopify_coupons = fields.Many2one('ks.shopify.discounts', string="Shopify Coupons", copy=False,
                                         domain=ks_domain_set, compute="_ks_change_domain", readonly=False,
                                         help="Displays Shopify Order Coupons")
    ks_shopify_payment_gateway = fields.Many2one('ks.shopify.payment.gateway', string="Shopify Payment Gateway",
                                                 readonly=True,
                                                 copy=False, help="Displays Shopify Order Payment Gateway")
    ks_date_created = fields.Datetime('Created On', copy=False,
                                      readonly=True,
                                      help="Created On: Date on which the Shopify Sale Order has been created")
    ks_date_updated = fields.Datetime('Updated On', copy=False,
                                      readonly=True,
                                      help="Updated On: Date on which the Shopify Sale Order has been last updated")
    ks_customer_ip_address = fields.Char(string='Customer IP', readonly=True, copy=False,
                                         help="Customer IP: Shopify Customer's IP address")
    ks_shopify_transaction_id = fields.Char(string='Transaction Id', readonly=True, copy=False,
                                            help="Transaction Id: Unique transaction ID of Shopify Sale Order")
    ks_shopify_checkout_id = fields.Char(string='Checkout Id', readonly=True, copy=False,
                                         help="Checkout Id: Unique checkout ID of Shopify Sale Order")
    ks_sync_states = fields.Boolean(string="Sync Status",
                                    compute='compute_sync_status', readonly=True)

    @api.onchange('ks_shopify_instance')
    def _ks_change_domain(self):
        return {'domain': {'ks_shopify_coupons': [('ks_shopify_instance', 'in', self.ks_shopify_instance.ids)]}}

    @api.onchange('ks_shopify_coupons')
    def ks_onchange_shopify_coupons(self):
        for rec in self:
            if rec.ks_shopify_coupons:
                if rec.ks_shopify_coupons.ks_shopify_price_rule_id and (
                        rec.ks_shopify_coupons.ks_date_ends >= datetime.now() if rec.ks_shopify_coupons.ks_date_ends else True) and rec.ks_shopify_coupons.ks_prereq_subtotal <= self.amount_untaxed:
                    if rec.ks_shopify_coupons.ks_value_type == 'fixed_amount':
                        coupons_price = (
                                -1 * rec.ks_shopify_coupons.ks_value) if rec.ks_shopify_coupons.ks_value < 0 else rec.ks_shopify_coupons.ks_value
                        coupons_price = coupons_price / len(rec.order_line)
                        for data in rec.order_line:
                            discount_amount = (coupons_price / (data.price_unit * data.product_uom_qty)) * 100
                            total_discount = (discount_amount * (data.price_unit * data.product_uom_qty)) / 100
                            data.ks_discount_amount = total_discount
                    else:
                        for data in rec.order_line:
                            coupons_price = (
                                    -1 * rec.ks_shopify_coupons.ks_value) if rec.ks_shopify_coupons.ks_value < 0 else rec.ks_shopify_coupons.ks_value
                            total_discount = (coupons_price * (data.price_unit * data.product_uom_qty)) / 100
                            data.ks_discount_amount = total_discount
                else:
                    raise ValidationError(
                        "Coupon would not be Synced or Minimum amount is not matched or coupon has expired")

    def compute_sync_status(self):
        if self:
            for rec in self:
                if not rec.ks_date_created and not rec.ks_date_updated:
                    rec.ks_sync_states = False

                elif rec.ks_date_created and rec.ks_date_updated:
                    rec.ks_sync_states = True

                else:
                    rec.ks_sync_states = False

    @api.model
    def create(self, vals):
        if vals.get('ks_shopify_instance') and vals.get('ks_shopify_order_id'):
            shopify_instance = self.env['ks.shopify.connector.instance'].search(
                [('id', '=', vals.get('ks_shopify_instance'))])
            if shopify_instance and not shopify_instance.ks_default_order_prefix:
                shopify_prefix = shopify_instance.ks_custom_order_prefix.upper()
                vals['name'] = shopify_prefix + ' #' + str(vals.get('ks_shopify_order_id'))
        return super(KsSaleOrderInherit, self).create(vals)

    def ks_cancel_sale_order_in_shopify(self):
        self.ensure_one()
        order = self
        if self.ks_shopify_instance and self.ks_shopify_instance.ks_instance_state == 'active':
            try:
                if order.ks_shopify_order_id:
                    shopify_order_record = self.env['ks.api.handler'].ks_post_data(order.ks_shopify_instance,
                                                                                   'cancel',
                                                                                   False,
                                                                                   order.ks_shopify_order_id)
                    if shopify_order_record:
                        shopify_order_record = shopify_order_record.get('order')
                        order.ks_shopify_status = 'cancelled'
                    else:
                        raise ValidationError("There is an error in cancelling please check logs")
                    self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(
                        shopify_order_record,
                        order,
                        'ks_shopify_order_id')
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                           ks_model='sale.order',
                                                                           ks_layer_model='sale.order',
                                                                           ks_message='''Order export success''',
                                                                           ks_status="success",
                                                                           ks_type="order",
                                                                           ks_record_id=self.id,
                                                                           ks_operation_flow="odoo_to_shopify",
                                                                           ks_shopify_id=shopify_order_record.get(
                                                                               "id") if shopify_order_record else False,
                                                                           ks_shopify_instance=self.ks_shopify_instance)
                else:
                    # if queue_record:
                    #     queue_record.ks_update_failed_state()
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                           ks_model='sale.order',
                                                                           ks_layer_model='sale.order',
                                                                           ks_message='''Order export failed, 
                                                                                               make sure all you products/customers are synced''',
                                                                           ks_status="failed",
                                                                           ks_type="order",
                                                                           ks_record_id=self.id,
                                                                           ks_operation_flow="odoo_to_shopify",
                                                                           ks_shopify_id=0,
                                                                           ks_shopify_instance=self.ks_shopify_instance)


            except Exception as e:
                # if queue_record:
                #     queue_record.ks_update_failed_state()
                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                       ks_model='sale.order',
                                                                       ks_layer_model='sale.order',
                                                                       ks_message=str(e),
                                                                       ks_status="failed",
                                                                       ks_type="order",
                                                                       ks_record_id=self.id,
                                                                       ks_operation_flow="odoo_to_shopify",
                                                                       ks_shopify_id=0,
                                                                       ks_shopify_instance=self.ks_shopify_instance)

    def ks_shopify_import_status_check(self, fin_status, ful_status, instance, status=False):
        """
        :param fin_status: financial status
        :param ful_status: fulfillment status
        :param instance: shopify instance
        :return: True/False
        """
        ks_status = status if status else ''
        if fin_status == 'open':
            ks_status = "open"
        elif fin_status == 'pending':
            ks_status = 'pending'
        elif fin_status in ['paid', 'partially_paid'] and ful_status != 'fulfilled':
            ks_status = 'paid'
        elif fin_status == 'paid' and ful_status == 'fulfilled':
            ks_status = 'completed'
        status_present = instance.ks_order_status.filtered(lambda x: x.status == ks_status)
        if status_present:
            return True
        else:
            return False

    def ks_shopify_import_order_create(self, order_data, instance, queue_record=False):
        try:
            financial_status = order_data.get("financial_status")
            fulfillment_status = order_data.get("fulfillment_status")
            if self.ks_shopify_import_status_check(financial_status, fulfillment_status,
                                                   instance,
                                                   status=order_data.get('status')) or not instance.ks_order_status:
                transaction_id = False
                order_id = order_data.get('id')
                transaction_data = self.env['ks.api.handler'].ks_get_all_data(instance, 'transactions', order_id)
                if transaction_data:
                    for rec in transaction_data:
                        if not rec.get('parent_id'):
                            transaction_id = rec.get('id')
                order_json = self.ks_shopify_prepare_import_json_data(order_data, instance)
                order_json.update({
                    'ks_shopify_transaction_id': transaction_id
                })
                if order_json:
                    order_record = self.create(order_json)
                    self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(order_data, order_record,
                                                                                             'ks_shopify_order_id')
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                           ks_model='sale.order',
                                                                           ks_layer_model='sale.order',
                                                                           ks_message="Sale order import create success",
                                                                           ks_status="success",
                                                                           ks_type="order",
                                                                           ks_record_id=order_record.id,
                                                                           ks_operation_flow="shopify_to_odoo",
                                                                           ks_shopify_id=order_data.get(
                                                                               "id", 0),
                                                                           ks_shopify_instance=instance)
                    return order_record
            else:
                _logger.error("Order status not under instance configurations")
                raise ValidationError("Order status not under instance configurations")
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                   ks_model='sale.order',
                                                                   ks_layer_model='sale.order',
                                                                   ks_message=str(e),
                                                                   ks_status="failed",
                                                                   ks_type="order",
                                                                   ks_record_id=0,
                                                                   ks_operation_flow="shopify_to_odoo",
                                                                   ks_shopify_id=order_data.get(
                                                                       "id", 0),
                                                                   ks_shopify_instance=instance)
            if queue_record:
                queue_record.ks_update_failed_state()

    def ks_shopify_import_order_update(self, order_data, queue_record=False):
        try:
            if self.state in ["draft", "sent", "cancel"]:
                financial_status = order_data.get("financial_status")
                fulfillment_status = order_data.get("fulfillment_status")
                if self.ks_shopify_import_status_check(financial_status, fulfillment_status,
                                                       self.ks_shopify_instance, status=order_data.get(
                            'status')) or not self.ks_shopify_instance.ks_order_status:
                    transaction_id = False
                    order_id = order_data.get('id')
                    transaction_data = self.env['ks.api.handler'].ks_get_all_data(self.ks_shopify_instance,
                                                                                  'transactions',
                                                                                  order_id)
                    if transaction_data:
                        for rec in transaction_data:
                            if not rec.get('parent_id'):
                                transaction_id = rec.get('id')
                    order_json = self.ks_shopify_prepare_import_json_data(order_data, self.ks_shopify_instance)
                    if order_json:
                        order_json.update({
                            'ks_shopify_transaction_id': transaction_id
                        })
                        self.write(order_json)
                        self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(order_data, self,
                                                                                                 'ks_shopify_order_id')
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                               ks_model='sale.order',
                                                                               ks_layer_model='sale.order',
                                                                               ks_message="Sale order import update success",
                                                                               ks_status="success",
                                                                               ks_type="order",
                                                                               ks_record_id=self.id,
                                                                               ks_operation_flow="shopify_to_odoo",
                                                                               ks_shopify_id=order_data.get(
                                                                                   "id", 0),
                                                                               ks_shopify_instance=self.ks_shopify_instance)
                        return self
                else:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                           ks_model='sale.order',
                                                                           ks_layer_model='sale.order',
                                                                           ks_message="Order already processed, So we cant update it",
                                                                           ks_status="success",
                                                                           ks_type="order",
                                                                           ks_record_id=self.id,
                                                                           ks_operation_flow="shopify_to_odoo",
                                                                           ks_shopify_id=order_data.get(
                                                                               "id", 0),
                                                                           ks_shopify_instance=self.ks_shopify_instance)
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                   ks_model='sale.order',
                                                                   ks_layer_model='sale.order',
                                                                   ks_message=str(e),
                                                                   ks_status="failed",
                                                                   ks_type="order",
                                                                   ks_record_id=self.id,
                                                                   ks_operation_flow="shopify_to_odoo",
                                                                   ks_shopify_id=order_data.get(
                                                                       "id", 0),
                                                                   ks_shopify_instance=self.ks_shopify_instance)

            if queue_record:
                queue_record.ks_update_failed_state()

    def ks_get_all_shopify_orders(self, instance, include=False, date_before=False, date_after=False, status=False):
        """
           :param shopify_api: The Shopify API instance
           :instance_id: Id of instance whose order have to be retrieved
           :return: List of Dictionary of get Shopify Products
           :rtype: List
        """
        all_retrieved_data = []
        try:
            if include:
                all_retrieved_data = self.env['ks.api.handler'].ks_get_all_data(instance, 'orders', include)
            else:
                all_retrieved_data = self.env['ks.api.handler'].ks_get_all_data(instance, 'orders')
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                   status="failed",
                                                                   type="order",
                                                                   instance=instance,
                                                                   operation_flow="shopify_to_odoo",
                                                                   shopify_id=0,
                                                                   message=str(e))
        else:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                   status="success",
                                                                   type="order",
                                                                   operation_flow="shopify_to_odoo",
                                                                   instance=instance,
                                                                   shopify_id=0,
                                                                   message="Fetch of Orders successful")
        return all_retrieved_data

    def ks_get_all_shopify_draft_orders(self, instance, include=False):
        """
           :param shopify_api: The Shopify API instance
           :instance_id: Id of instance whose order have to be retrieved
           :return: List of Dictionary of get Shopify Products
           :rtype: List
        """
        all_retrieved_data = []
        try:
            if include:
                all_retrieved_data = self.env['ks.api.handler'].ks_get_all_data(instance, 'draft_orders', include)
            else:
                all_retrieved_data = self.env['ks.api.handler'].ks_get_all_data(instance, 'draft_orders')
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                   status="failed",
                                                                   type="order",
                                                                   instance=instance,
                                                                   operation_flow="shopify_to_odoo",
                                                                   shopify_id=0,
                                                                   message=str(e))
        else:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                   status="success",
                                                                   type="order",
                                                                   operation_flow="shopify_to_odoo",
                                                                   instance=instance,
                                                                   shopify_id=0,
                                                                   message="Fetch of Orders successful")
        return all_retrieved_data

    def ks_export_order_to_shopify(self, queue_record=False):
        for order in self:
            if order.ks_shopify_instance and order.ks_shopify_instance.ks_instance_state == 'active' and order.ks_shopify_status != 'open':
                try:
                    # shopifyapi = order.ks_shopify_instance.ks_shopify_api_authentication()
                    shopify_order_record = None
                    # if shopifyapi.get("").status_code:
                    if not int(order.ks_shopify_order_id):
                        json_data = order.ks_shopify_prepare_export_json_data()
                        if json_data:
                            shopify_order_record = self.env['ks.api.handler'].ks_post_data(order.ks_shopify_instance,
                                                                                           'orders',
                                                                                           {'order': json_data})
                            if shopify_order_record:
                                shopify_order_record = shopify_order_record.get('order')
                            self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(
                                shopify_order_record,
                                order,
                                'ks_shopify_order_id')
                            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                                   ks_model='sale.order',
                                                                                   ks_layer_model='sale.order',
                                                                                   ks_message='''Order export success''',
                                                                                   ks_status="success",
                                                                                   ks_type="order",
                                                                                   ks_record_id=self.id,
                                                                                   ks_operation_flow="odoo_to_shopify",
                                                                                   ks_shopify_id=shopify_order_record.get(
                                                                                       "id") if shopify_order_record else False,
                                                                                   ks_shopify_instance=self.ks_shopify_instance)
                        else:
                            if queue_record:
                                queue_record.ks_update_failed_state()
                            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                                   ks_model='sale.order',
                                                                                   ks_layer_model='sale.order',
                                                                                   ks_message='''Order export failed, 
                                                                               make sure all you products/customers are synced''',
                                                                                   ks_status="failed",
                                                                                   ks_type="order",
                                                                                   ks_record_id=self.id,
                                                                                   ks_operation_flow="odoo_to_shopify",
                                                                                   ks_shopify_id=0,
                                                                                   ks_shopify_instance=self.ks_shopify_instance)

                except Exception as e:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                           ks_model='sale.order',
                                                                           ks_layer_model='sale.order',
                                                                           ks_message=str(e),
                                                                           ks_status="failed",
                                                                           ks_type="order",
                                                                           ks_record_id=self.id,
                                                                           ks_operation_flow="odoo_to_shopify",
                                                                           ks_shopify_id=0,
                                                                           ks_shopify_instance=self.ks_shopify_instance)
                    if queue_record:
                        queue_record.ks_update_failed_state()

            elif order.ks_shopify_status == 'open':
                raise ValidationError("You Can Not Export Open Orders to Shopify")

    def ks_get_shopify_orders(self, order_id, instance):
        """
           :param order_id:
           :param instance:
           :param shopify_api: The Shopify API instance
           :instance_id: Id of instance whose order have to be get
           :category_id: Id of order specific whose order details has to be get
           :return: Dictionary of get Shopify order
           :rtype: dict
        """
        try:
            order_response_record = None
            shopify_api = instance.ks_shopify_api_authentication()
            order_response = shopify_api.get("orders/%s" % order_id)
            if order_response.status_code in [200, 201]:
                order_response_record = order_response.json()
                self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                       status="success",
                                                                       type="order",
                                                                       operation_flow="shopify_to_odoo",
                                                                       instance=instance,
                                                                       shopify_id=order_response_record.get("id", 0),
                                                                       message="Fetch of Orders successful")
            else:
                self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                       status="failed",
                                                                       type="order",
                                                                       operation_flow="shopify_to_odoo",
                                                                       instance=instance,
                                                                       shopify_id=0,
                                                                       message=str(order_response.text))
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                   status="failed",
                                                                   type="order",
                                                                   instance=instance,
                                                                   operation_flow="shopify_to_odoo",
                                                                   shopify_id=0,
                                                                   message=str(e))
        else:
            return order_response_record

    def ks_get_product_ids(self, instance, json_data):
        product_id = json_data.get("product_id")
        variation_id = json_data.get("variant_id")
        shopify_product_json = self.env['ks.shopify.product.template'].ks_shopify_get_product(product_id, instance)
        if shopify_product_json:
            odoo_product = self.env['ks.shopify.product.template'].ks_manage_shopify_product_template_import(instance,
                                                                                                             shopify_product_json[
                                                                                                                 0])
            if odoo_product:
                if odoo_product.ks_shopify_product_type == "simple":
                    return odoo_product.ks_product_product
                else:
                    product_exist = self.env['ks.shopify.product.template'].search(
                        [('ks_shopify_product_id', '=', json_data.get('product_id')),
                         ('ks_shopify_instance', '=', instance.id)])
                    return product_exist.ks_shopify_product_template.product_variant_ids.ks_shopify_product_variant.search(
                        [('ks_shopify_instance', '=', instance.id),
                         ('ks_shopify_variant_id', '=', variation_id)]).ks_shopify_product_variant

            else:
                return odoo_product

    def ks_get_customer_id(self, shopify_cust_id, instance_id, invoice_address=False, shipping_address=False):
        json_data = {"billing": invoice_address,
                     "shipping": shipping_address}
        mapped_billing_customer = False
        mapped_shipping_customer = False
        if not shopify_cust_id or shopify_cust_id.get('id') == 0:
            shopify_customer_exist = self.env.ref('ks_shopify.ks_shopify_guest_customers')
            billing_data = self.env['ks.shopify.partner'].ks_convert_shopify_odoo_compatible_data(json_data['billing'],
                                                                                                  "billing",
                                                                                                  customer=shopify_cust_id)
            shipping_data = self.env['ks.shopify.partner'].ks_convert_shopify_odoo_compatible_data(
                json_data['shipping'], "shipping", customer=shopify_cust_id)
            if billing_data:
                mapped_odoo_customer, mapped_billing_customer = self.env[
                    'res.partner'].ks_shopify_handle_customer_address(
                    shopify_customer_exist,
                    billing_data, 'invoice')
                shopify_customer_exist = mapped_odoo_customer
            if shipping_data:
                mapped_odoo_customer, mapped_shipping_customer = self.env[
                    'res.partner'].ks_shopify_handle_customer_address(
                    shopify_customer_exist,
                    shipping_data, 'delivery')
                shopify_customer_exist = mapped_odoo_customer
        else:
            customer_data = self.env['ks.shopify.partner'].ks_shopify_get_customer(shopify_cust_id.get('id'),
                                                                                   instance_id)
            # customer_data = shopify_cust_id
            if customer_data:
                odoo_customer = self.env['ks.shopify.partner'].ks_manage_shopify_customer_import(instance_id,
                                                                                                 customer_data)
                mapped_odoo_customer = odoo_customer
                billing_data = self.env['ks.shopify.partner'].ks_convert_shopify_odoo_compatible_data(
                    json_data['billing'],
                    "billing",
                    customer=shopify_cust_id)
                shipping_data = self.env['ks.shopify.partner'].ks_convert_shopify_odoo_compatible_data(
                    json_data['shipping'], "shipping", customer=shopify_cust_id)
                if billing_data:
                    mapped_odoo_customer, mapped_billing_customer = self.env[
                        'res.partner'].ks_shopify_handle_customer_address(
                        odoo_customer,
                        billing_data, 'invoice')
                if shipping_data:
                    mapped_odoo_customer, mapped_shipping_customer = self.env[
                        'res.partner'].ks_shopify_handle_customer_address(
                        odoo_customer,
                        shipping_data, 'delivery')
                shopify_customer_exist = mapped_odoo_customer
            else:
                shopify_customer_exist = self.env.ref('ks_shopify.ks_shopify_guest_customers')
        return shopify_customer_exist.id, mapped_billing_customer, mapped_shipping_customer if shopify_customer_exist else False

    def _get_payment_gateway(self, each_record, instance):
        if each_record.get('payment_method') and each_record.get('payment_method_title'):
            payment_gateway = self.env['ks.shopify.payment.gateway'].search([
                ('ks_shopify_pg_id', '=', each_record.get('payment_method')),
                ('ks_shopify_instance', '=', instance.id)],
                limit=1)
            if not payment_gateway:
                payment_gateway = self.env['ks.shopify.payment.gateway'].create({
                    'ks_shopify_pg_id': each_record.get('payment_method') or '',
                    'ks_shopify_instance': instance.id,
                    'ks_title': each_record.get('payment_method_title') or ''
                })
            return payment_gateway.id

    def _get_shopify_discounts(self, shopify_coupon_lines, instance):
        coupon_id = False
        if shopify_coupon_lines:
            for each_coupon in [shopify_coupon_lines]:
                if each_coupon.get('code'):
                    coupon_exist_in_odoo = self.env['ks.shopify.discounts'].search(
                        [('ks_title', '=', each_coupon.get('code')),
                         ('ks_shopify_instance', '=', instance.id)],
                        limit=1)
                    if coupon_exist_in_odoo:
                        coupon_id = coupon_exist_in_odoo.id
                    else:
                        coupon_id = self.env['ks.shopify.discounts'].create({
                            "ks_title": shopify_coupon_lines.get('code'),
                            "ks_shopify_instance": instance.id,
                            "ks_target_selection": shopify_coupon_lines.get("target_selection", False),
                            "ks_target_type": shopify_coupon_lines.get("target_type", False),
                            "ks_value": shopify_coupon_lines.get("value", 0.0),
                            'ks_customer_selection': shopify_coupon_lines.get(
                                'customer_selection') if shopify_coupon_lines.get('customer_selection') else 'all',
                            'ks_allocation_method': shopify_coupon_lines.get('allocation_method'),
                            "ks_value_type": shopify_coupon_lines.get("value_type", False),
                            "ks_date_starts": datetime.now(),
                        }).id
        return coupon_id

    def get_shopify_tax_ids(self, order_line_tax, instance):
        # if tax:
        taxes = []
        for ol_tax in order_line_tax:
            # for each_record in tax:
            tax_exist = self.env['account.tax'].search([('name', '=', ol_tax.get('title')),
                                                        ('type_tax_use', '=', 'sale')], limit=1)
            try:
                tax_value = self.env['ir.config_parameter'].sudo().get_param(
                    'account.show_line_subtotals_tax_selection')
                if tax_value == 'tax_excluded':
                    price_include = False
                elif tax_value == 'tax_included':
                    price_include = True
                else:
                    price_include = False
                shopify_tax_data = {
                    'name': ol_tax.get('title'),
                    # 'ks_shopify_id': shopify_tax_record.get('id'),
                    'ks_shopify_instance': instance.id,
                    'amount': float(ol_tax.get('rate') * 100 or 0),
                    'amount_type': 'percent',
                    'company_id': instance.ks_company_id.id,
                    'type_tax_use': 'sale',
                    'active': True,
                    'price_include': price_include,
                }
                if tax_exist:
                    tax_exist.write(shopify_tax_data)
                else:
                    tax_exist = self.env['account.tax'].create(shopify_tax_data)
                current_tax_total = float(ol_tax.get('price') or 0)
                if current_tax_total:
                    taxes.append(tax_exist.id)
            except Exception as e:
                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                                                                  ks_shopify_instance=instance,
                                                                  ks_record_id=0,
                                                                  ks_message='Create/Fetch of Taxes Failed',
                                                                  ks_shopify_id=0,
                                                                  ks_operation_flow='shopify_to_odoo',
                                                                  ks_status="failed",
                                                                  ks_type="system_status",
                                                                  ks_error=e)

            return taxes if taxes else []
        else:
            return []

    def ks_get_order_lines(self, order_json_data, instance):
        order_lines = []
        for each_record in order_json_data.get('line_items'):
            sale_order_exist = self.search(['|', ('ks_shopify_draft_order_id', '=', order_json_data.get('id')),
                                            ('ks_shopify_order_id', '=', order_json_data.get('id')),
                                            ('ks_shopify_instance', '=', instance.id)], limit=1)
            ks_product_layer = self.env['ks.shopify.product.template'].search(
                ['|', ('ks_shopify_product_id', '=', each_record.get('product_id')),
                 ('ks_shopify_product_variant_id', '=', each_record.get('product_id')),
                 ('ks_shopify_instance', '=', instance.id)], limit=1)
            if ks_product_layer.ks_shopify_product_type == 'variable':
                ks_product_product = ks_product_layer.ks_shopify_variant_ids.filtered(lambda x: x.ks_shopify_variant_id == str(each_record.get('variant_id'))).ks_shopify_product_variant
            else:
                ks_product_product = ks_product_layer.ks_product_product if ks_product_layer.ks_product_product else False
            ks_product_template = ks_product_layer.ks_shopify_product_template if ks_product_layer.ks_shopify_product_template else False
            sale_order_line_exist = False
            if ks_product_product:
                sale_order_line_exist = self.env['sale.order.line'].search(
                    [('product_id', '=', ks_product_product.id),
                     ('order_id', '=', sale_order_exist.id), ('ks_shopify_order_line_id','=', each_record.get('id'))])
            elif ks_product_template:
                sale_order_line_exist = self.env['sale.order.line'].search(
                    [('product_template_id', '=', ks_product_template.id),
                     ('order_id', '=', sale_order_exist.id), ('ks_shopify_order_line_id','=', each_record.get('id'))])
            product = self.ks_get_product_ids(instance, each_record) if not ks_product_product else ks_product_product
            if product:
                # ks_price_unit = float((float(each_record.get('price') or 0)/int(each_record.get('quantity') or 1)) or 0)
                line_items_data = {
                    'ks_shopify_order_line_id': each_record.get('id'),
                    'name': each_record.get('title'),
                    'product_id': product.id,
                    'product_uom_qty': each_record.get('quantity'),
                    'price_unit': float(each_record.get('price') or 0),
                    'product_uom': product.uom_id.id,
                    'tax_id': [(6, 0, self.get_shopify_tax_ids(order_json_data.get('tax_lines'),
                                                               instance))],
                    # 'ks_discount_amount': float((float(each_record.get('price') or 0) - float(each_record.get('total') or 0)) or 0)
                }
                ks_sum_amount = 0.00
                if each_record.get('discount_allocations'):
                    for discount in each_record.get('discount_allocations'):
                        ks_sum_amount = ks_sum_amount + float(discount.get('amount'))
                line_items_data.update({
                    'ks_discount_amount': float(ks_sum_amount or 0)
                })

                if not line_items_data.get("tax_id") and each_record.get('tax_lines'):
                    line_items_data.update({
                        "price_tax": each_record.get('tax_lines')[0].get('price')
                    })
                if sale_order_line_exist:
                    order_lines.append((1, sale_order_line_exist.id, line_items_data))
                else:
                    order_lines.append((0, 0, line_items_data))
            else:
                if product == None or each_record.get('product_id') == None:
                    raise TypeError(
                        "Product Does not exist on shopify with shopify ID : %s" % each_record.get("product_id"))
                if product == False:
                    raise TypeError(
                        "Product(%s) creation failed due to some missing/duplicate parameters." % each_record.get("product_id"))

        if order_json_data.get('fee_lines'):
            for each_rec in order_json_data.get('fee_lines'):
                sale_order_exist = self.search([('ks_shopify_order_id', '=', order_json_data.get('id')),
                                                ('ks_shopify_instance', '=', instance.id)], limit=1)
                sale_order_line_exist = self.env['sale.order.line'].search(
                    [('ks_shopify_order_line_id', '=', each_rec.get('id')),
                     ('order_id', '=', sale_order_exist.id)],
                    limit=1)

                fee_lines_data = {
                    'ks_shopify_order_line_id': each_rec.get('id'),
                    'name': each_rec.get('name'),
                    'product_id': self.env.ref('ks_shopify.ks_shopify_fees').id,
                    'product_uom': self.env.ref('ks_shopify.ks_shopify_fees').uom_id.id,
                    'product_uom_qty': 1,
                    'price_unit': float(each_rec.get('amount') or each_rec.get('total') or 0),
                    #     'tax_id': [(6, 0, self.get_tax_ids(order_json_data.get('tax_lines'),
                    #                                        instance))]
                }

                if sale_order_line_exist:
                    order_lines.append((1, sale_order_line_exist.id, fee_lines_data))
                else:
                    order_lines.append((0, 0, fee_lines_data))

        if order_json_data.get('shipping_lines'):
            for each_rec in order_json_data.get('shipping_lines'):
                sale_order_exist = self.search([('ks_shopify_order_id', '=', order_json_data.get('id')),
                                                ('ks_shopify_instance', '=', instance.id)], limit=1)
                sale_order_line_exist = self.env['sale.order.line'].search(
                    [('ks_shopify_order_line_id', '=', each_rec.get('id')),
                     ('order_id', '=', sale_order_exist.id)],
                    limit=1)
                shipping_lines_data = {
                    'ks_shopify_order_line_id': each_rec.get('id'),
                    'name': each_rec.get('title'),  # "[shopify]"
                    'product_id': self.env.ref('ks_shopify.ks_shopify_shipping_fees').id,
                    'product_uom': self.env.ref('ks_shopify.ks_shopify_shipping_fees').uom_id.id,
                    'product_uom_qty': 1,
                    'price_unit': float(each_rec.get('price') or 0),
                    # 'tax_id': [(6, 0, self.get_tax_ids(order_json_data.get('tax_lines'),
                    #                                    instance))]
                }

                if sale_order_line_exist:
                    order_lines.append((1, sale_order_line_exist.id, shipping_lines_data))
                else:
                    order_lines.append((0, 0, shipping_lines_data))
        return order_lines

    def _get_order_shopify_lines(self, order_line_data):
        line_data = []
        total_tax = False
        for order_line in order_line_data:
            values = {
                # "id": order_line.ks_shopify_order_line_id,
                "name": order_line.name,
                "title": order_line.name,
                "quantity": int(order_line.product_uom_qty),
                "price": float(order_line.price_unit),
                # "total": str(order_line.price_reduce_taxexcl * order_line.product_uom_qty),
                # "sku": order_line.product_id.default_code if order_line.product_id.default_code else '',
            }
            tax_data = []
            if order_line.tax_id:
                tax_lines = {}
                for tax in order_line.tax_id:
                    tax_lines = {
                        "channel_liable": False,
                        'title': tax.name,
                        'rate': (tax.amount / 100),
                        'price': (float(((
                                                 order_line.price_unit * order_line.product_uom_qty) - order_line.ks_discount_amount) * tax.amount) / 100),
                    }
                    tax_data.append(tax_lines)
                    total_tax += tax_lines.get('price')
                values.update({'tax_lines': tax_data})
            if order_line.product_id:
                template = order_line.product_id.product_tmpl_id
                shopify_template = self.env["ks.shopify.product.template"].search(
                    [("ks_shopify_product_template", "=", template.id),
                     ("ks_shopify_instance", "=", self.ks_shopify_instance.id)])
                if shopify_template and shopify_template.ks_shopify_product_id:
                    if shopify_template.ks_shopify_product_type == "simple":
                        values.update({
                            # "product_id": shopify_template.ks_shopify_product_id,
                            "variant_id": shopify_template.ks_shopify_product_variant_id or 0,
                        })
                    else:
                        product_id = self.env["ks.shopify.product.variant"].search(
                            [("ks_shopify_product_variant", "=", order_line.product_id.id),
                             ("ks_shopify_instance", "=", self.ks_shopify_instance.id)])
                        if product_id and product_id.ks_shopify_variant_id:
                            values.update({
                                # "product_id": shopify_template.ks_shopify_product_id,
                                "variant_id": product_id.ks_shopify_variant_id,
                            })
                        else:
                            return False
                    line_data.append(values)
                elif shopify_template and not shopify_template.ks_shopify_product_id:
                    product_template = self.env[
                        "ks.shopify.product.template"].ks_manage_shopify_product_template_export(
                        self.ks_shopify_instance)
                    template = order_line.product_id.product_tmpl_id
                    shopify_template = self.env["ks.shopify.product.template"].search(
                        [("ks_shopify_product_template", "=", template.id),
                         ("ks_shopify_instance", "=", self.ks_shopify_instance.id)])
                    if shopify_template and shopify_template.ks_shopify_product_id:
                        if shopify_template.ks_shopify_product_type == "simple":
                            values.update({
                                # "product_id": shopify_template.ks_shopify_product_id,
                                "variant_id": shopify_template.ks_shopify_product_variant_id or 0,
                            })
                        else:
                            product_id = self.env["ks.shopify.product.variant"].search(
                                [("ks_shopify_product_variant", "=", order_line.product_id.id),
                                 ("ks_shopify_instance", "=", self.ks_shopify_instance.id)])
                            if product_id and product_id.ks_shopify_variant_id:
                                values.update({
                                    # "product_id": shopify_template.ks_shopify_product_id,
                                    "variant_id": product_id.ks_shopify_variant_id,
                                })
                            else:
                                return False
                    else:
                        return False
                    line_data.append(values)
                    # return False
        return line_data, total_tax

    def ks_auto_import_shopify_order(self, cron_id=False):
        try:
            if not cron_id:
                if self._context.get('params'):
                    cron_id = self.env["ir.cron"].browse(self._context.get('params').get('id'))
            else:
                cron_id = self.env["ir.cron"].browse(cron_id)
            instance_id = cron_id.ks_shopify_instance
            if instance_id and instance_id.ks_instance_state == 'active':
                order_status = ','.join(instance_id.ks_order_status.mapped('status'))
                orders_json_records = self.env['sale.order'].ks_get_all_shopify_orders(
                    instance=instance_id, status=order_status)
                for order_data in orders_json_records:
                    order_record_exist = self.env['sale.order'].search(
                        [('ks_shopify_instance', '=', instance_id.id),
                         ('ks_shopify_order_id', '=', order_data.get("id"))])
                    if order_record_exist:
                        order_record_exist.ks_shopify_import_order_update(order_data)
                    else:
                        if not order_data.get('cancelled_at'):
                            order_record_exist.ks_shopify_import_order_create(
                                order_data, instance_id)
        except Exception as e:
            _logger.info(str(e))

    def ks_shopify_prepare_import_json_data(self, order_json_data, instance):
        currency_id = instance.ks_shopify_currency
        partner_data, partner_invoice_id, partner_shipping_id = self.ks_get_customer_id(order_json_data.get('customer'),
                                                                                        instance,
                                                                                        order_json_data.get(
                                                                                            'billing_address', {}),
                                                                                        order_json_data.get(
                                                                                            'shipping_address', {}))
        data = {
            'ks_order_name': order_json_data.get('name'),
            'ks_shopify_instance': instance.id,
            'ks_shopify_status': (order_json_data.get('financial_status') if not order_json_data.get(
                'fulfillment_status') else 'completed') if (
                    order_json_data.get('financial_status') or order_json_data.get('fulfillment_status')) else 'open',
            'ks_customer_ip_address': order_json_data.get('browser_ip') or "",
            'ks_shopify_checkout_id': order_json_data.get('checkout_id') or "",
            'note': order_json_data.get('note') or '',
            'currency_id': currency_id.id,
            'partner_id': partner_data,
            'order_line': self.ks_get_order_lines(order_json_data, instance),
            'warehouse_id': instance.ks_warehouse.id,
            'company_id': instance.ks_company_id.id,
            'team_id': instance.ks_sales_team.id,
            'user_id': instance.ks_sales_person.id,
            'payment_term_id': instance.ks_payment_term_id.id,
        }
        if order_json_data.get('order_id'):
            data.update({
                'ks_shopify_order_id': order_json_data.get("order_id") or '',
                'ks_shopify_draft_order_id': order_json_data.get('id') or '',
            })
        else:
            data.update({
                'ks_shopify_order_id': order_json_data.get("id") or '',
            })
        if order_json_data.get('order_type') == 'draft':
            data.update({
                'ks_is_draft': True,
            })
        else:
            data.update({
                'ks_is_draft': False,
            })
        if partner_invoice_id:
            data.update({
                'partner_invoice_id': partner_invoice_id.id if partner_invoice_id else False,
            })
        if partner_shipping_id:
            data.update({
                'partner_shipping_id': partner_shipping_id.id if partner_shipping_id else False,
            })
        payment_data = self.env['ks.shopify.payment.gateway'].ks_manage_shopify_payment_gateway_import(instance,
                                                                                                       order_json_data)
        if payment_data:
            data.update({
                'ks_shopify_payment_gateway': payment_data.id
            })
        if order_json_data.get('discount_applications'):
            coupon_ids = self._get_shopify_discounts(order_json_data.get('discount_applications')[0], instance)
            data.update({
                'ks_shopify_coupons': coupon_ids,
            })
        if data:
            # False --> data.get("ks_shopify_payment_gateway")
            auto_workflow = self.get_auto_worflow(False, data.get("ks_shopify_status"),
                                                  instance)
            if not auto_workflow:
                auto_workflow = self.env.ref('ks_base_connector.ks_automatic_validation')
            data.update({
                "ks_auto_workflow_id": auto_workflow.id
            })
        if instance.ks_meta_fields_map:
            meta_data = self.env['ks.shopify.meta.mapping'].get_meta_fields_data(instance=instance,
                                                                                             model='orders',
                                                                                             ids=order_json_data.get('id'),
                                                                                             ks_model='sale.order')
            data.update(meta_data)
        return data

    def get_auto_worflow(self, payment_gateway_id, order_status, instance):
        auto_workflow = False
        if instance.ks_order_import_type == "status":
            auto_workflow = self.env['ks.auto.sale.workflow.configuration'].search([
                ("ks_shopify_instance", "=", instance.id),
                ("ks_shopify_order_status.status", "=", order_status)
            ], limit=1)
            auto_workflow = auto_workflow.ks_sale_workflow_id
        elif instance.ks_order_import_type == "payment_gateway":
            auto_workflow = self.env['ks.auto.sale.workflow.configuration'].search([
                ("ks_shopify_instance", "=", instance.id),
                ("ks_shopify_payment_id", "=", payment_gateway_id)
            ], limit=1)
            auto_workflow = auto_workflow.ks_sale_workflow_id
        return auto_workflow

    def ks_shopify_prepare_export_json_data(self):
        if self.ks_shopify_status == 'completed':
            status = {
                'financial_status': 'paid',
                'fulfillment_status': 'fulfilled',
            }
        else:
            status = {
                'financial_status': self.ks_shopify_status,
            }
        total_discount = 0
        for rec in self.order_line:
            if rec.ks_discount_amount and not self.ks_shopify_coupons:
                total_discount += rec.ks_discount_amount
        soup = BeautifulSoup(self.note)
        text = soup.getText()
        data = {
            'note': text,
        }
        if total_discount:
            data.update({
                'total_discounts': total_discount
            })
        if self.ks_shopify_coupons:
            discount_codes = {
                "code": self.ks_shopify_coupons.ks_title,
                "amount": ((
                                   -1 * self.ks_shopify_coupons.ks_value) if self.ks_shopify_coupons.ks_value < 0 else self.ks_shopify_coupons.ks_value),
                "type": self.ks_shopify_coupons.ks_value_type
            }
            data.update({'discount_codes': [discount_codes]})
        data.update(status)
        order_lines = self._get_order_shopify_lines(self.order_line)
        if order_lines[1]:
            # total_tax = sum([i.get('tax_lines')[0].get('price') for i in order_lines])
            data.update({
                'total_tax': order_lines[1]
            })
        if order_lines[0]:
            data.update({
                'line_items': order_lines[0]
            })
        else:
            return False
        if self.partner_id:
            customer_data = self._ks_shopify_manage_customer(self.partner_id)
            if customer_data:
                data.update(customer_data)
            else:
                pass
        return data

    def _ks_shopify_manage_customer(self, customer):
        shopify_customer = self.env["ks.shopify.partner"].search([("ks_res_partner", "=", customer.id),
                                                                  ("ks_shopify_instance", "=",
                                                                   self.ks_shopify_instance.id)])
        guest_customer = self.env.ref("ks_shopify.ks_shopify_guest_customers")
        if shopify_customer.ks_shopify_partner_id:
            json_data = {
                'customer': {'id': shopify_customer.ks_shopify_partner_id, }
            }
        if customer != guest_customer:
            # data = self.ks_shopify_prepare_export_json_data()
            data = shopify_customer.ks_prepare_export_json_data(customer)
            json_data = {}
            if data.get('first_name') or data.get('last_name') or data.get('email'):
                customer_data = {
                    'first_name': data.get('first_name'),
                    'last_name': data.get('last_name'),
                    'email': data.get('email'),
                }
                json_data.update({'customer': customer_data})
            json_data.update({
                'billing_address': data['billing'] if data.get('billing') else '',
                'shipping_address': data['shipping'] if data.get('shipping') else '',
            })

        elif customer == guest_customer:
            return False
        else:
            return False
        return json_data

    def _prepare_invoice(self):
        invoice_vals = super(KsSaleOrderInherit, self)._prepare_invoice()
        if invoice_vals and int(self.ks_shopify_order_id):
            invoice_vals.update({
                "ks_shopify_order_id": self.id
            })
        return invoice_vals


class KsSaleOrderLineInherit(models.Model):
    _inherit = 'sale.order.line'

    ks_shopify_order_line_id = fields.Char('Shopify Id', readonly=True, copy=False)
    ks_discount_amount = fields.Float(string='Discount Amount', digits=(16, 4))

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'ks_discount_amount')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        super(KsSaleOrderLineInherit, self)._compute_amount()
        for line in self:
            if line.ks_discount_amount:
                price = line.price_unit - (
                    line.ks_discount_amount / line.product_uom_qty if line.ks_discount_amount else 0)
                taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty,
                                                product=line.product_id, partner=line.order_id.partner_shipping_id)
                line.update({
                    'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                    'price_total': taxes['total_included'],
                    'price_subtotal': taxes['total_excluded'],
                })
            if line.product_id.name == "Shipping Fees":
                price = line.price_unit
                taxes = line.tax_id.with_context({'shopify_shipping': True}).compute_all(price,
                                                                                         line.order_id.currency_id,
                                                                                         line.product_uom_qty,
                                                                                         product=line.product_id,
                                                                                         partner=line.order_id.partner_shipping_id,
                                                                                         handle_price_include=False)
                line.update({
                    'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                    'price_total': taxes['total_included'],
                    'price_subtotal': taxes['total_excluded'],
                })

    def _prepare_invoice_line(self, **optional_values):
        # Updating discount amount (in float) on invoice line
        res = super(KsSaleOrderLineInherit, self)._prepare_invoice_line(**optional_values)
        if self.ks_discount_amount and (self.qty_to_invoice * self.price_unit):
            discount = (self.ks_discount_amount / (self.qty_to_invoice * self.price_unit) if (
                                                                                                     self.qty_to_invoice * self.price_unit) > 0 else 1) * 100
            res.update({'discount': discount, 'ks_discount_amount_value': self.ks_discount_amount})
        return res


class KsAccountTax(models.Model):
    _inherit = "account.tax"

    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Instance", readonly=True,
                                          help=_("Shopify Connector Instance reference"),
                                          ondelete='cascade')
