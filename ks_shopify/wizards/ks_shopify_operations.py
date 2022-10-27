# -*- coding: utf-8 -*-

import logging
from datetime import datetime

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from requests.exceptions import ConnectionError

_logger = logging.getLogger(__name__)


class KsShopifyInstanceOperation(models.TransientModel):
    _name = "ks.instance.operations"
    _description = "Shopify Instance Operations"

    @api.model
    def _get_default_ks_shopify_instances_ids(self):
        """
        :return: ks.shopify.connector.instance() All the active Shopify Instances
        """
        instance_ids = self.env['ks.shopify.connector.instance'].search([('ks_instance_state', '=', 'active')]).ids
        return [(6, 0, instance_ids)]

    ks_instances = fields.Many2many('ks.shopify.connector.instance', string="Instance", required=True,
                                    default=lambda self: self._get_default_ks_shopify_instances_ids(),
                                    help="Displays Shopify Instance Name")
    # domain="[('ks_instance_state', '=', 'active')]")
    ks_check_multi_operation = fields.Boolean(string="Perform Multiple Operation", required=True)
    ks_operation_flow = fields.Selection([('shopify_to_odoo', 'Shopify to Odoo'),
                                          ('odoo_to_shopify', 'Odoo to Shopify')], default="shopify_to_odoo",
                                         string="Operation Flow",
                                         help="Shows the flow of the operation either from Shopify to Odoo or Odoo to Shopify")
    ks_operation_odoo = fields.Selection([('import_collection', 'Import Collections'),
                                          ('import_discount', 'Import Discounts'),
                                          ('import_product', 'Import Product'),
                                          ('import_stock', 'Import Product Stock'),
                                          ('import_orders', 'Import Orders'),
                                          ('import_draft_orders', 'Import Draft Orders'),
                                          ('import_customers', 'Import Customers'),
                                          ('import_locations', 'Import Locations'),
                                          ], string="Import Operation",
                                         help="It include the list of operation that can be performed for Import Operation")
    ks_operation_shopify = fields.Selection([('export_collection', 'Export Collections'),
                                             ('export_discount', 'Export Discount'),
                                             ('export_product', 'Export Product'),
                                             ('export_customers', 'Export Customers'),
                                             ('export_orders', 'Export Orders'),
                                             ('export_stock', 'Export Stocks'),
                                             # ('active_product', 'Active Product'),
                                             # ('draft_product', 'Draft Product')
                                             ], string="Export Operation",
                                            help="It include the list of operation that can be performed for Export Operation")
    ks_want_all = fields.Boolean(string="Want to select all operations ?",
                                 help=" Checkbox allows you to select all the operation at one click`")
    ks_want_all_shopify = fields.Boolean(string="Want to select all operations ? ")
    ks_sync_products = fields.Boolean(string="Sync Products")
    ks_sync_taxes = fields.Boolean(string="Sync Taxes")
    ks_sync_collections = fields.Boolean(string="Sync Custom Collections")
    ks_sync_discount = fields.Boolean(string="Sync Discounts")
    ks_sync_attribute = fields.Boolean(string="Sync Attributes")
    ks_sync_tags = fields.Boolean(string="Sync Tags")
    ks_sync_category = fields.Boolean(string="Sync Category")
    ks_stock = fields.Boolean(string="Sync Stocks")
    ks_sync_customers = fields.Boolean(string="Sync Customers")
    ks_sync_orders = fields.Boolean(string="Import Orders")
    ks_sync_locations = fields.Boolean(string="Sync Locations")
    ks_sync_draft_orders = fields.Boolean(string="Import Draft Orders")
    ks_sync_coupons = fields.Boolean(string="Sync Coupons")
    ks_sync_payment_gateways = fields.Boolean(string="Sync Payment Gateways")
    ks_publish_products = fields.Boolean(string="Publish Product")
    ks_unpublish_products = fields.Boolean(string="Unpublish Product")
    ks_update_customers = fields.Boolean(string="Export/Update Customers")
    ks_update_products = fields.Boolean(string="Export/Update Products")
    ks_update_collections = fields.Boolean(string="Export Custom Collections")
    ks_update_discount = fields.Boolean(string="Export Discounts")
    ks_update_products_with_images = fields.Boolean(string="Export/Update Products with Images")
    ks_update_coupons = fields.Boolean(string="Export/Update Coupons")
    ks_update_attributes = fields.Boolean(string="Export/Update Attributes")
    ks_update_category = fields.Boolean(string="Export/Update Categories")
    ks_update_tags = fields.Boolean(string="Export/Update Tags")
    ks_update_order_status = fields.Boolean(string="Update Order status")
    ks_update_order = fields.Boolean(string="Export New Orders")
    ks_update_stock = fields.Boolean(string="Update Stock")
    ks_update_product_to_draft = fields.Boolean(string="Draft")
    ks_update_product_to_active = fields.Boolean(string="Active")
    ks_record_ids = fields.Char(string="Record ID", help="Enter shopify id for that particular records")
    ks_date_filter_before = fields.Datetime(string="Date Before", help="Displays the date before")
    ks_date_filter_after = fields.Datetime(string="Date After", help="Displays the date after")
    ks_value_example = fields.Char(
        default="For multiple record separate Shopify Id(s) using ','. For example: 111,222,333",
        readonly=True)
    ks_get_specific_import_type = fields.Selection([('import_all', "Import All "),
                                                    ('record_id', 'Specific Id Filter')],
                                                   default="import_all",
                                                   string="Import with",
                                                   help="It include the list of types of import functionalities.")

    def check_for_valid_record_id(self):
        if not self.ks_record_ids:
            return self.env['ks.message.wizard'].ks_pop_up_message(names='Info',
                                                                   message="Please provide Shopify Id of record for import.")
        if self.ks_record_ids:
            shopify_record_ids = self.ks_record_ids.split(',')
            for i in shopify_record_ids:
                try:
                    int(i)
                except Exception:
                    return self.env['ks.message.wizard'].ks_pop_up_message(names='Info',
                                                                           message="Please enter valid Shopify Id of record for import.")
        return False

    @api.onchange('ks_get_specific_import_type', 'ks_operation_odoo')
    def ks_check_api(self):
        if self.ks_get_specific_import_type == 'date_filter' and self.ks_operation_odoo in ['import_attributes',
                                                                                            'import_customers',
                                                                                            'import_categories',
                                                                                            'import_tags',
                                                                                            'import_payment_gateway',
                                                                                            'import_tax']:
            raise ValidationError("Selected Import Operation does not support Date Filter")
        if self.ks_get_specific_import_type == 'record_id' and self.ks_operation_odoo in ['import_attributes',
                                                                                          'import_payment_gateway',
                                                                                          'import_tax',
                                                                                          'import_discount']:
            raise ValidationError("Selected Import Operation does not support Specific Filter")

    @api.onchange('ks_want_all')
    def ks_check_all(self):
        if self.ks_want_all:
            self.ks_stock = self.ks_sync_products = self.ks_sync_tags = self.ks_sync_category = self.ks_sync_attribute \
                = self.ks_sync_coupons = self.ks_sync_orders = self.ks_sync_locations = self.ks_sync_draft_orders = self.ks_sync_discount = \
                self.ks_sync_payment_gateways = self.ks_sync_customers = self.ks_sync_collections = True
        elif not self.ks_want_all:
            self.ks_stock = self.ks_sync_products = self.ks_sync_tags = self.ks_sync_category = self.ks_sync_attribute \
                = self.ks_sync_coupons = self.ks_sync_orders = self.ks_sync_locations = self.ks_sync_draft_orders = self.ks_sync_discount = False

    @api.onchange('ks_want_all_shopify')
    def ks_check_all_shopify(self):
        if self.ks_want_all_shopify:
            self.ks_update_stock = self.ks_update_collections = self.ks_update_order = self.ks_update_discount = \
                self.ks_update_customers = self.ks_update_products = self.ks_update_products_with_images = \
                self.ks_update_product_to_draft = self.ks_update_product_to_active = True
        elif not self.ks_want_all_shopify:
            self.ks_update_stock = self.ks_update_collections = self.ks_update_order = self.ks_update_discount = \
                self.ks_update_customers = self.ks_update_products = self.ks_update_products_with_images = \
                self.ks_update_product_to_draft = self.ks_update_product_to_active = False

    def ks_execute_operation(self):
        if self.ks_operation_flow == 'odoo_to_shopify' and (not self.ks_operation_shopify and
                                                            not self.ks_update_order and not self.ks_update_customers and
                                                            not self.ks_update_products and not self.ks_sync_orders and not self.ks_sync_draft_orders and not self.ks_sync_customers and not
                                                            self.ks_stock and not self.ks_update_stock and
                                                            not self.ks_sync_products and not self.ks_sync_collections and not self.ks_sync_discount
                                                            and not self.ks_update_product_to_draft and not self.ks_update_product_to_active):
            raise ValidationError("Please select operation")
        if self.ks_operation_flow == 'shopify_to_odoo' and (not self.ks_operation_odoo
                                                            and not self.ks_sync_orders and not self.ks_sync_draft_orders and not self.ks_sync_customers and not
                                                            self.ks_stock and not self.ks_sync_collections and not self.ks_sync_discount and
                                                            not self.ks_sync_products and not self.ks_sync_locations and not self.ks_update_stock
                                                            and not self.ks_update_order and not self.ks_update_customers and not self.ks_update_collections and
                                                            not self.ks_update_products and not self.ks_update_discount
                                                            and not self.ks_update_product_to_draft and not self.ks_update_product_to_active):
            raise ValidationError("Please select operation")
        if not self.ks_operation_flow:
            raise ValidationError("Please select operation flow")
        # if self.ks_get_specific_import_type == 'date_filter' and self.ks_operation_odoo in ['import_customers']:
        #     raise ValidationError("Cannot Execute! Selected Import Operation does not support Date Filter")
        # if self.ks_get_specific_import_type == 'record_id' and self.ks_operation_odoo in ['import_attributes']:
        #     raise ValidationError("Cannot Execute! Selected Import Operation does not support Specific Record Filter")
        for instance in self.ks_instances:
            if instance.ks_instance_state == 'active':
                try:
                    if not self.ks_check_multi_operation and self.ks_operation_flow == 'shopify_to_odoo' and \
                            self.ks_get_specific_import_type == 'record_id':
                        if_not_valid = self.check_for_valid_record_id()
                        if if_not_valid:
                            return if_not_valid
                        if self.ks_operation_odoo == 'import_collection':
                            _logger.info('Collection Entry on Queue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            collection_json_records = self.env['ks.api.handler'].ks_get_all_data(instance=instance,
                                                                                                 domain="collections",
                                                                                                 ids=self.ks_record_ids)
                            if collection_json_records:
                                self.env['ks.shopify.queue.jobs'].ks_create_collections_record_in_queue(
                                    instance=instance,
                                    data=collection_json_records)
                                _logger.info("Collections fetched from Shopify with %s records." % str(
                                    len(collection_json_records)))
                        if self.ks_operation_odoo == 'import_locations':
                            _logger.info('Locations Entry on Queue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            location_json_records = self.env['ks.api.handler'].ks_get_all_data(instance=instance,
                                                                                                 domain="locations",
                                                                                                 ids=self.ks_record_ids)
                            if location_json_records:
                                self.env['ks.shopify.queue.jobs'].ks_create_locations_record_in_queue(
                                    instance=instance,
                                    data=location_json_records)
                                _logger.info("Locations fetched from Shopify with %s records." % str(
                                    len(location_json_records)))
                        # if self.ks_operation_odoo == 'import_tax':
                        #     _logger.info('Tax Entry on Queue start For Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     taxes_json_records = self.env['account.tax'].ks_shopify_get_all_account_tax(
                        #         instance=instance,
                        #         include=self.ks_record_ids)
                        #     if taxes_json_records:
                        #         self.env['ks.shopify.queue.jobs'].ks_create_taxes_record_in_queue(instance=instance,
                        #                                                                          data=taxes_json_records)
                        #     else:
                        #         self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                        #                                                       ks_type='tax',
                        #                                                       ks_shopify_instance=instance,
                        #                                                       ks_record_id=0,
                        #                                                       ks_message="Tax Sync operation to queue jobs failed",
                        #                                                       ks_shopify_id=0,
                        #                                                       ks_operation_flow='shopify_to_odoo',
                        #                                                       ks_status="failed")
                        if self.ks_operation_odoo == 'import_customers':
                            _logger.info('Customer Entry on Queue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            customer_json_records = self.env['ks.shopify.partner'].ks_shopify_get_all_customers(
                                instance=instance,
                                include=self.ks_record_ids)
                            if customer_json_records:
                                _logger.info("Customers fetched from Shopify with %s records." % str(
                                    len(customer_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_customer_record_in_queue(instance=instance,
                                                                                                     data=customer_json_records)
                            else:
                                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                                                                                  ks_type='customer',
                                                                                  ks_shopify_instance=instance,
                                                                                  ks_record_id=0,
                                                                                  ks_message="Customer Sync operation to queue jobs failed",
                                                                                  ks_shopify_id=0,
                                                                                  ks_operation_flow='shopify_to_odoo',
                                                                                  ks_status="failed")

                        # elif self.ks_operation_odoo == 'import_categories':
                        #     _logger.info("Categories Entry on Queue start for Shopify Instance [%s -(%s)]",
                        #                  instance.ks_instance_name, instance.id)
                        #     category_json_records = self.env['ks.shopify.product.category'].ks_shopify_get_all_product_category(
                        #         instance=instance, include=self.ks_record_ids)
                        #     if category_json_records:
                        #         self.env['ks.shopify.queue.jobs'].ks_create_category_record_in_queue(instance=instance,
                        #                                                                          data=category_json_records)
                        #     else:
                        #         self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                        #                                                       ks_type='category',
                        #                                                       ks_shopify_instance=instance,
                        #                                                       ks_record_id=0,
                        #                                                       ks_message='Category Sync operation to queue jobs failed',
                        #                                                       ks_shopify_id=0,
                        #                                                       ks_operation_flow='shopify_to_odoo',
                        #                                                       ks_status="failed")

                        elif self.ks_operation_odoo == 'import_product':
                            _logger.info('Product enqueue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            product_json_records = self.env['ks.shopify.product.template'].ks_shopify_get_all_products(
                                instance=instance, include=self.ks_record_ids)
                            if product_json_records:
                                _logger.info("Products fetched from Shopify with %s records." % str(
                                    len(product_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(instance=instance,
                                                                                                    data=product_json_records)

                        elif self.ks_operation_odoo == 'import_discount':
                            _logger.info('Discount Entry on Queue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            ids = len(self.ks_record_ids.split(",")) > 1
                            if ids:
                                raise ValidationError("Multiple records not accepted in case of Discounts")
                            else:
                                discount_json_records = self.env['ks.api.handler'].ks_get_all_data(instance=instance,
                                                                                                   domain="price_rules",
                                                                                                   ids=self.ks_record_ids)
                                if discount_json_records:
                                    _logger.info("Discounts fetched from Shopify with %s records." % str(
                                        len(discount_json_records)))
                                    self.env['ks.shopify.queue.jobs'].ks_create_discount_record_in_queue(
                                        instance=instance,
                                        data=discount_json_records)

                        elif self.ks_operation_odoo == 'import_stock':
                            _logger.info("Stock importing start for shopify instance [%s -(%s)]",
                                         instance.ks_instance_name, instance.id)
                            product_json_records = self.env['ks.shopify.product.template'].ks_shopify_get_all_products(
                                instance=instance, include=self.ks_record_ids)
                            if product_json_records:
                                _logger.info("Stocks fetched from Shopify with %s records." % str(
                                    len(product_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_import_stock_shopify_in_queue(instance=instance,
                                                                                                   data=product_json_records)
                            else:
                                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='import',
                                                                                  ks_type='stock',
                                                                                  ks_shopify_instance=instance,
                                                                                  ks_record_id=0,
                                                                                  ks_message='Stock sync failed',
                                                                                  ks_shopify_id=0,
                                                                                  ks_operation_flow='shopify_to_odoo',
                                                                                  ks_status="failed")
                        # elif self.ks_operation_odoo == 'import_tags':
                        #     _logger.info("Product Tags enqueue start for shopify instance [%s -(%s)]",
                        #                  instance.ks_instance_name, instance.id)
                        #     tags_json_records = self.env['ks.shopify.product.tag'].ks_shopify_get_all_product_tag(
                        #         instance=instance, include=self.ks_record_ids)
                        #     if tags_json_records:
                        #         self.env['ks.shopify.queue.jobs'].ks_create_tag_record_in_queue(instance=instance,
                        #                                                                     data=tags_json_records)
                        #     else:
                        #         self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                        #                                                       ks_type='tags',
                        #                                                       ks_shopify_instance=instance,
                        #                                                       ks_record_id=0,
                        #                                                       ks_message='Tags Sync operation to queue jobs failed',
                        #                                                       ks_shopify_id=0,
                        #                                                       ks_operation_flow='shopify_to_odoo',
                        #                                                       ks_status="failed")
                        # elif self.ks_operation_odoo == 'import_coupons':
                        #     _logger.info('Coupons enqueue start For Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     coupons_json_records = self.env['ks.shopify.coupons'].ks_shopify_get_all_coupon(
                        #         instance=instance, include=self.ks_record_ids)
                        #     if coupons_json_records:
                        #         self.env['ks.shopify.queue.jobs'].ks_create_coupon_record_in_queue(instance=instance,
                        #                                                                        data=coupons_json_records)
                        #     else:
                        #         self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                        #                                                       ks_type='coupon',
                        #                                                       ks_shopify_instance=instance,
                        #                                                       ks_record_id=0,
                        #                                                       ks_message='Coupons Sync operation to queue jobs failed',
                        #                                                       ks_shopify_id=0,
                        #                                                       ks_operation_flow='shopify_to_odoo',
                        #                                                       ks_status="failed")
                        elif self.ks_operation_odoo == 'import_orders':
                            _logger.info('Orders enqueue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            # filter the order status selected on instance to be synced
                            order_status = ','.join(instance.ks_order_status.mapped('status'))
                            orders_json_records = self.env['sale.order'].ks_get_all_shopify_orders(
                                instance=instance, status=order_status, include=self.ks_record_ids)
                            if orders_json_records:
                                _logger.info("Orders fetched from Shopify with %s records." % str(
                                    len(orders_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_order_record_in_queue(instance=instance,
                                                                                                  data=orders_json_records)
                            else:
                                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                                                                                  ks_type='order',
                                                                                  ks_shopify_instance=instance,
                                                                                  ks_record_id=0,
                                                                                  ks_message='Orders Sync operation to queue jobs failed',
                                                                                  ks_shopify_id=0,
                                                                                  ks_operation_flow='shopify_to_odoo',
                                                                                  ks_status="failed")
                        elif self.ks_operation_odoo == 'import_draft_orders':
                            _logger.info('Orders enqueue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            # filter the order status selected on instance to be synced
                            order_status = ','.join(instance.ks_order_status.mapped('status'))
                            orders_json_records = self.env['sale.order'].ks_get_all_shopify_draft_orders(
                                instance=instance, include=self.ks_record_ids)
                            if orders_json_records:
                                _logger.info("Draft Orders fetched from Shopify with %s records." % str(
                                    len(orders_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_order_record_in_queue(instance=instance,
                                                                                                  data=orders_json_records,
                                                                                                  order_type="draft")
                            else:
                                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                                                                                  ks_type='order',
                                                                                  ks_shopify_instance=instance,
                                                                                  ks_record_id=0,
                                                                                  ks_message='Orders Sync operation to queue jobs failed',
                                                                                  ks_shopify_id=0,
                                                                                  ks_operation_flow='shopify_to_odoo',
                                                                                  ks_status="failed")
                    if not self.ks_check_multi_operation and self.ks_operation_flow == 'shopify_to_odoo' and \
                            self.ks_get_specific_import_type == 'date_filter':
                        '''Note all the other domains does not supports date 
                        filter and we have handled it above in line 81-88'''
                        if self.ks_operation_odoo == 'import_product':
                            _logger.info('Product enqueue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            product_json_records = self.env['ks.shopify.product.template'].ks_shopify_get_all_products(
                                instance=instance, date_after=self.ks_date_filter_after,
                                date_before=self.ks_date_filter_before)
                            if product_json_records:
                                _logger.info("Products fetched from Shopify with %s records." % str(
                                    len(product_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(instance=instance,
                                                                                                    data=product_json_records)
                        # elif self.ks_operation_odoo == 'import_coupons':
                        #     _logger.info('Coupons enqueue start For Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     coupons_json_records = self.env['ks.shopify.coupons'].ks_shopify_get_all_coupon(
                        #         instance=instance, date_after=self.ks_date_filter_after,
                        #         date_before=self.ks_date_filter_before)
                        #     if coupons_json_records:
                        #         self.env['ks.shopify.queue.jobs'].ks_create_coupon_record_in_queue(instance=instance,
                        #                                                                        data=coupons_json_records)
                        #     else:
                        #         self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                        #                                                       ks_type='coupon',
                        #                                                       ks_shopify_instance=instance,
                        #                                                       ks_record_id=0,
                        #                                                       ks_message='Coupons Sync operation to queue jobs failed',
                        #                                                       ks_shopify_id=0,
                        #                                                       ks_operation_flow='shopify_to_odoo',
                        #                                                       ks_status="failed")
                        elif self.ks_operation_odoo == 'import_orders':
                            _logger.info('Orders enqueue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            # filter the order status selected on instance to be synced
                            order_status = ','.join(instance.ks_order_status.mapped('status'))
                            orders_json_records = self.env['sale.order'].ks_get_all_shopify_orders(
                                instance=instance, status=order_status, date_after=self.ks_date_filter_after,
                                date_before=self.ks_date_filter_before)
                            if orders_json_records:
                                _logger.info("Orders fetched from Shopify with %s records." % str(
                                    len(orders_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_order_record_in_queue(instance=instance,
                                                                                                  data=orders_json_records)
                            else:
                                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                                                                                  ks_type='order',
                                                                                  ks_shopify_instance=instance,
                                                                                  ks_record_id=0,
                                                                                  ks_message='Orders Sync operation to queue jobs failed',
                                                                                  ks_shopify_id=0,
                                                                                  ks_operation_flow='shopify_to_odoo',
                                                                                  ks_status="failed")
                        elif self.ks_operation_odoo == 'import_stock':
                            _logger.info("Stock importing start for shopify instance [%s -(%s)]",
                                         instance.ks_instance_name, instance.id)
                            product_json_records = self.env['ks.shopify.product.template'].ks_shopify_get_all_products(
                                instance=instance, date_after=self.ks_date_filter_after,
                                date_before=self.ks_date_filter_before)
                            if product_json_records:
                                _logger.info("Stocks fetched from Shopify with %s records." % str(
                                    len(product_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_import_stock_shopify_in_queue(instance=instance,
                                                                                                   data=product_json_records)
                            else:
                                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='import',
                                                                                  ks_type='stock',
                                                                                  ks_shopify_instance=instance,
                                                                                  ks_record_id=0,
                                                                                  ks_message='Stock sync failed',
                                                                                  ks_shopify_id=0,
                                                                                  ks_operation_flow='shopify_to_odoo',
                                                                                  ks_status="failed")
                    if not self.ks_check_multi_operation and self.ks_operation_flow == 'shopify_to_odoo' and \
                            self.ks_get_specific_import_type == 'import_all':
                        if self.ks_operation_odoo == 'import_locations':
                            _logger.info('Locations Entry on Queue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            location_json_records = self.env['ks.api.handler'].ks_get_all_data(instance=instance,
                                                                                                 domain="locations",
                                                                                                 ids=self.ks_record_ids)
                            if location_json_records:
                                self.env['ks.shopify.queue.jobs'].ks_create_locations_record_in_queue(
                                    instance=instance,
                                    data=location_json_records)
                                _logger.info("Locations fetched from Shopify with %s records." % str(
                                    len(location_json_records)))
                        if self.ks_operation_odoo == 'import_discount':
                            _logger.info('Discount Entry on Queue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            discount_json_records = self.env['ks.api.handler'].ks_get_all_data(instance=instance,
                                                                                               domain="price_rules",
                                                                                               ids=self.ks_record_ids)
                            if discount_json_records:
                                _logger.info("Discounts fetched from Shopify with %s records." % str(
                                    len(discount_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_discount_record_in_queue(
                                    instance=instance,
                                    data=discount_json_records)
                        if self.ks_operation_odoo == 'import_collection':
                            _logger.info('Collection Entry on Queue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            collection_json_records = self.env['ks.api.handler'].ks_get_all_data(instance=instance,
                                                                                                 domain="custom_collections")
                            if collection_json_records:
                                _logger.info("Collections fetched from Shopify with %s records." % str(
                                    len(collection_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_collections_record_in_queue(
                                    instance=instance,
                                    data=collection_json_records)

                        # if self.ks_operation_odoo == "import_attributes":
                        #     _logger.info('Attribute enqueue start For Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     attribute_json_records = self.env['ks.shopify.product.attribute'].ks_shopify_get_all_attributes(
                        #         instance_id=instance)
                        #     if attribute_json_records:
                        #         self.env['ks.shopify.queue.jobs'].ks_create_attribute_record_in_queue(instance=instance,
                        #                                                                           data=attribute_json_records)
                        # if self.ks_operation_odoo == 'import_tax':
                        #     _logger.info('Tax Entry on Queue start For Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     taxes_json_records = self.env['account.tax'].ks_shopify_get_all_account_tax(
                        #         instance=instance,
                        #         include=self.ks_record_ids)
                        #     if taxes_json_records:
                        #         self.env['ks.shopify.queue.jobs'].ks_create_taxes_record_in_queue(instance=instance,
                        #                                                                          data=taxes_json_records)
                        #     else:
                        #         self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                        #                                                       ks_type='tax',
                        #                                                       ks_shopify_instance=instance,
                        #                                                       ks_record_id=0,
                        #                                                       ks_message="Tax Sync operation to queue jobs failed",
                        #                                                       ks_shopify_id=0,
                        #                                                       ks_operation_flow='shopify_to_odoo',
                        #                                                       ks_status="failed")
                        # if self.ks_operation_odoo == "import_tags":
                        #     _logger.info('Tags enqueue start For Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     tags_json_records = self.env['ks.shopify.product.tag'].ks_shopify_get_all_product_tag(
                        #         instance=instance)
                        #     if tags_json_records:
                        #         self.env['ks.shopify.queue.jobs'].ks_create_tag_record_in_queue(instance=instance,
                        #                                                                     data=tags_json_records)
                        #     else:
                        #         self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                        #                                                       ks_type='tags',
                        #                                                       ks_shopify_instance=instance,
                        #                                                       ks_record_id=0,
                        #                                                       ks_message='Tags Sync operation to queue jobs failed',
                        #                                                       ks_shopify_id=0,
                        #                                                       ks_operation_flow='shopify_to_odoo',
                        #                                                       ks_status="failed")
                        # if self.ks_operation_odoo == "import_categories":
                        #     _logger.info("Categories Entry on Queue start for Shopify Instance [%s -(%s)]",
                        #                  instance.ks_instance_name, instance.id)
                        #     category_json_records = self.env['ks.shopify.product.category'].ks_shopify_get_all_product_category(
                        #         instance=instance)
                        #     if category_json_records:
                        #         self.env['ks.shopify.queue.jobs'].ks_create_category_record_in_queue(instance=instance,
                        #                                                                          data=category_json_records)
                        #     else:
                        #         self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                        #                                                       ks_type='category',
                        #                                                       ks_shopify_instance=instance,
                        #                                                       ks_record_id=0,
                        #                                                       ks_message='Category Sync operation to queue jobs failed',
                        #                                                       ks_shopify_id=0,
                        #                                                       ks_operation_flow='shopify_to_odoo',
                        #                                                       ks_status="failed")
                        # if self.ks_operation_odoo == "import_payment_gateway":
                        #     # Sync Payment Gateways
                        #     _logger.info("Payment Gateways enqueue starts for Shopify Instance [%s -(%s)]",
                        #                  instance.ks_instance_name, instance.id)
                        #     pg_json_records = self.env['ks.shopify.payment.gateway'].ks_shopify_get_all_payment_gateway(
                        #         instance=instance)
                        #     if pg_json_records:
                        #         self.env['ks.shopify.queue.jobs'].ks_create_pg_record_in_queue(instance=instance,
                        #                                                                    data=pg_json_records)
                        #     else:
                        #         self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                        #                                                       ks_type='payment_gateway',
                        #                                                       ks_shopify_instance=instance,
                        #                                                       ks_record_id=0,
                        #                                                       ks_message='Payment Gateway Sync operation to queue jobs failed',
                        #                                                       ks_shopify_id=0,
                        #                                                       ks_operation_flow='shopify_to_odoo',
                        #                                                       ks_status="failed")
                        if self.ks_operation_odoo == "import_customers":
                            # Sync Customers
                            _logger.info('Customer enqueue For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            customer_json_records = self.env['ks.shopify.partner'].ks_shopify_get_all_customers(
                                instance=instance)
                            if customer_json_records:
                                _logger.info("Customers fetched from Shopify with %s records." % str(
                                    len(customer_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_customer_record_in_queue(instance=instance,
                                                                                                     data=customer_json_records)
                            else:
                                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                                                                                  ks_type='customer',
                                                                                  ks_shopify_instance=instance,
                                                                                  ks_record_id=0,
                                                                                  ks_message="Customer Sync operation to queue jobs failed",
                                                                                  ks_shopify_id=0,
                                                                                  ks_operation_flow='shopify_to_odoo',
                                                                                  ks_status="failed")
                        if self.ks_operation_odoo == 'import_product':
                            _logger.info('Product enqueue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            product_json_records = self.env['ks.shopify.product.template'].ks_shopify_get_all_products(
                                instance=instance)
                            if product_json_records:
                                _logger.info("Products fetched from Shopify with %s records." % str(
                                    len(product_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(instance=instance,
                                                                                                    data=product_json_records)
                        if self.ks_operation_odoo == 'import_stock':
                            _logger.info("Stock importing start for Shopify instance [%s -(%s)]",
                                         instance.ks_instance_name, instance.id)
                            product_json_records = self.env['ks.shopify.product.template'].ks_shopify_get_all_products(
                                instance=instance)
                            if product_json_records:
                                _logger.info("Stocks fetched from Shopify with %s records." % str(
                                    len(product_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_import_stock_shopify_in_queue(instance=instance,
                                                                                                   data=product_json_records)
                            else:
                                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='import',
                                                                                  ks_type='stock',
                                                                                  ks_shopify_instance=instance,
                                                                                  ks_record_id=0,
                                                                                  ks_message='Stock sync failed',
                                                                                  ks_shopify_id=0,
                                                                                  ks_operation_flow='shopify_to_odoo',
                                                                                  ks_status="failed")
                        # if self.ks_operation_odoo == "import_coupons":
                        #     _logger.info('Coupons enqueue start For Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     coupons_json_records = self.env['ks.shopify.coupons'].ks_shopify_get_all_coupon(
                        #         instance=instance)
                        #     if coupons_json_records:
                        #         self.env['ks.shopify.queue.jobs'].ks_create_coupon_record_in_queue(instance=instance,
                        #                                                                        data=coupons_json_records)
                        #     else:
                        #         self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                        #                                                       ks_type='coupon',
                        #                                                       ks_shopify_instance=instance,
                        #                                                       ks_record_id=0,
                        #                                                       ks_message='Coupons Sync operation to queue jobs failed',
                        #                                                       ks_shopify_id=0,
                        #                                                       ks_operation_flow='shopify_to_odoo',
                        #                                                       ks_status="failed")
                        elif self.ks_operation_odoo == 'import_orders':
                            _logger.info('Orders enqueue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            # filter the order status selected on instance to be synced
                            order_status = ','.join(instance.ks_order_status.mapped('status'))
                            orders_json_records = self.env['sale.order'].ks_get_all_shopify_orders(
                                instance=instance, status=order_status)
                            if orders_json_records:
                                _logger.info("Orders fetched from Shopify with %s records." % str(
                                    len(orders_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_order_record_in_queue(instance=instance,
                                                                                                  data=orders_json_records,
                                                                                                  order_type="draft")
                        elif self.ks_operation_odoo == 'import_draft_orders':
                            _logger.info('Orders enqueue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            # filter the order status selected on instance to be synced
                            order_status = ','.join(instance.ks_order_status.mapped('status'))
                            orders_json_records = self.env['sale.order'].ks_get_all_shopify_draft_orders(
                                instance=instance, status=order_status)
                            if orders_json_records:
                                _logger.info("Draft Orders fetched from Shopify with %s records." % str(
                                    len(orders_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_order_record_in_queue(instance=instance,
                                                                                                  data=orders_json_records)
                            else:
                                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                                                                                  ks_type='order',
                                                                                  ks_shopify_instance=instance,
                                                                                  ks_record_id=0,
                                                                                  ks_message='Orders Sync operation to queue jobs failed',
                                                                                  ks_shopify_id=0,
                                                                                  ks_operation_flow='shopify_to_odoo',
                                                                                  ks_status="failed")
                    if not self.ks_check_multi_operation and self.ks_operation_flow == 'odoo_to_shopify':
                        # if self.ks_operation_shopify == 'export_attributes':
                        #     _logger.info('Attribute entry enqueue for shopifyCommerce Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     attribute_records = self.env['ks.shopify.product.attribute'].search(
                        #         [('ks_shopify_instance.id', '=', instance.id)])
                        #     self.env['ks.shopify.queue.jobs'].ks_create_attribute_record_in_queue(instance,
                        #                                                                       records=attribute_records)
                        if self.ks_operation_shopify == 'export_discount':
                            _logger.info("Discount Records Enqueue for Shopify Instance [%s -(%s)]",
                                         instance.ks_instance_name, instance.id)
                            discount_records = self.env['ks.shopify.discounts'].search([(
                                'ks_shopify_instance.id', '=', instance.id)])
                            _logger.info("Discounts being exported to Shopify with %s records." % str(
                                len(discount_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_discount_record_in_queue(instance,
                                                                                                 records=discount_records)
                        if self.ks_operation_shopify == 'export_stock':
                            _logger.info("Stock Records Enqueue for Shopify Instance [%s -(%s)]",
                                         instance.ks_instance_name, instance.id)
                            stock_records = self.env['ks.shopify.product.template'].search([(
                                'ks_shopify_instance.id', '=', instance.id)])
                            _logger.info("Stock being exported to Shopify with %s records." % str(
                                len(stock_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_stock_record_in_queue(instance,
                                                                                                 records=stock_records)
                        elif self.ks_operation_shopify == 'export_collection':
                            _logger.info("Collection Records Enqueue for Shopify Instance [%s -(%s)]",
                                         instance.ks_instance_name, instance.id)
                            collection_records = self.env['ks.shopify.custom.collections'].search([(
                                'ks_shopify_instance.id', '=', instance.id)])
                            _logger.info("Collections being exported to Shopify with %s records." % str(
                                len(collection_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_collections_record_in_queue(instance,
                                                                                                    records=collection_records)
                        # elif self.ks_operation_shopify == 'export_categories':
                        #     _logger.info("Category Records Enqueue for Shopify Instance [%s -(%s)]",
                        #                  instance.ks_instance_name, instance.id)
                        #     category_records = self.env['ks.shopify.product.category'].search([
                        #         ('ks_shopify_instance.id', '=', instance.id)])
                        #     self.env['ks.shopify.queue.jobs'].ks_create_category_record_in_queue(instance,
                        #                                                                      records=category_records)
                        # elif self.ks_operation_shopify == 'export_tags':
                        #     _logger.info('Tags entry enqueue for Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     tag_records = self.env['ks.shopify.product.tag'].search([
                        #         ('ks_shopify_instance', '=', instance.id)
                        #     ])
                        #     self.env['ks.shopify.queue.jobs'].ks_create_tag_record_in_queue(instance,
                        #                                                                 records=tag_records)
                        elif self.ks_operation_shopify == 'export_product':
                            _logger.info('Product entry enqueue for Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            product_records = self.env['ks.shopify.product.template'].search([
                                ('ks_shopify_instance', '=', instance.id)
                            ])
                            _logger.info("Products being exported to Shopify with %s records." % str(
                                len(product_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(instance,
                                                                                                records=product_records)
                        elif self.ks_operation_shopify == 'export_customers':
                            _logger.info('Customer enqueue for Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            customer_records = self.env['ks.shopify.partner'].search(
                                [('ks_shopify_instance.id', '=', instance.id), ('ks_type', '=', 'customer')])
                            _logger.info("Customers being exported to Shopify with %s records." % str(
                                len(customer_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_customer_record_in_queue(instance,
                                                                                                 records=customer_records)
                        # elif self.ks_operation_shopify == 'export_coupons':
                        #     _logger.info('Coupons enqueue start For Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     coupon_records = self.env['ks.shopify.coupons'].search(
                        #         [('ks_shopify_instance.id', '=', instance.id)])
                        #     self.env['ks.shopify.queue.jobs'].ks_create_coupon_record_in_queue(instance=instance,
                        #                                                                    records=coupon_records)
                        elif self.ks_operation_shopify == 'export_orders':
                            _logger.info('Orders enqueue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            order_records = self.env['sale.order'].search(
                                [('ks_shopify_instance', '=', instance.id),
                                 ('ks_shopify_order_id', '=', 0)])
                            _logger.info("Orders being exported to Shopify with %s records." % str(
                                len(order_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_order_record_in_queue(instance=instance,
                                                                                              records=order_records)
                        # elif self.ks_operation_shopify == 'export_coupons':
                        #     _logger.info('Coupons enqueue start For Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     coupon_records = self.env['ks.shopify.coupons'].search(
                        #         [('ks_shopify_instance.id', '=', instance.id)])
                        #     self.env['ks.shopify.queue.jobs'].ks_create_coupon_record_in_queue(instance=instance,
                        #                                                                    records=coupon_records)

                    if self.ks_check_multi_operation:
                        # if self.ks_update_attributes:
                        #     _logger.info('Attribute entry enqueue for Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     attribute_records = self.env['ks.shopify.product.attribute'].search(
                        #         [('ks_shopify_instance.id', '=', instance.id)])
                        #     self.env['ks.shopify.queue.jobs'].ks_create_attribute_record_in_queue(instance,
                        #                                                                       records=attribute_records)
                        if self.ks_update_order:
                            _logger.info('Order entry enqueue for Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            order_records = self.env['sale.order'].search(
                                [('ks_shopify_instance', '=', instance.id),
                                 ('ks_shopify_order_id', '=', 0)])
                            _logger.info("Orders being exported to Shopify with %s records." % str(
                                len(order_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_order_record_in_queue(instance=instance,
                                                                                              records=order_records)
                        if self.ks_sync_locations:
                            _logger.info('Locations Entry on Queue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            location_json_records = self.env['ks.api.handler'].ks_get_all_data(instance=instance,
                                                                                                 domain="locations",
                                                                                                 ids=self.ks_record_ids)
                            if location_json_records:
                                self.env['ks.shopify.queue.jobs'].ks_create_locations_record_in_queue(
                                    instance=instance,
                                    data=location_json_records)
                                _logger.info("Locations fetched from Shopify with %s records." % str(
                                    len(location_json_records)))
                        if self.ks_sync_discount:
                            _logger.info('Discount Entry on Queue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            discount_json_records = self.env['ks.api.handler'].ks_get_all_data(instance=instance,
                                                                                               domain="price_rules",
                                                                                               ids=self.ks_record_ids)
                            if discount_json_records:
                                _logger.info("Discounts fetched from Shopify with %s records." % str(
                                    len(discount_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_discount_record_in_queue(
                                    instance=instance,
                                    data=discount_json_records)
                        if self.ks_sync_collections:
                            _logger.info('Collection Entry on Queue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            collection_json_records = self.env['ks.api.handler'].ks_get_all_data(instance=instance,
                                                                                                 domain="custom_collections",
                                                                                                 ids=self.ks_record_ids)
                            if collection_json_records:
                                _logger.info("Collections fetched from Shopify with %s records." % str(
                                    len(collection_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_collections_record_in_queue(
                                    instance=instance,
                                    data=collection_json_records)
                        # if self.ks_sync_taxes:
                        #     _logger.info('Tax Entry on Queue start For Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     taxes_json_records = self.env['account.tax'].ks_shopify_get_all_account_tax(
                        #         instance=instance,
                        #         include=self.ks_record_ids)
                        #     if taxes_json_records:
                        #         self.env['ks.shopify.queue.jobs'].ks_create_taxes_record_in_queue(instance=instance,
                        #                                                                          data=taxes_json_records)
                        #     else:
                        #         self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                        #                                                       ks_type='Tax',
                        #                                                       ks_shopify_instance=instance,
                        #                                                       ks_record_id=0,
                        #                                                       ks_message="Tax Sync operation to queue jobs failed",
                        #                                                       ks_shopify_id=0,
                        #                                                       ks_operation_flow='shopify_to_odoo',
                        #                                                       ks_status="failed")
                        # if self.ks_update_order_status:
                        #     _logger.info('Order entry enqueue for Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     order_records = self.env['sale.order'].search(
                        #         [('ks_shopify_instance', '=', instance.id),
                        #          ('ks_shopify_order_id', '!=', 0)])
                        #     self.env['ks.shopify.queue.jobs'].ks_create_order_record_in_queue(instance=instance,
                        #                                                                   records=order_records)

                        # if self.ks_update_category:
                        #     _logger.info('Category entry enqueue for Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     category_records = self.env['ks.shopify.product.category'].search([
                        #         ('ks_shopify_instance.id', '=', instance.id)])
                        #     self.env['ks.shopify.queue.jobs'].ks_create_category_record_in_queue(instance,
                        #                                                                      records=category_records)
                        # if self.ks_update_tags:
                        #     _logger.info('Tags entry enqueue for Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     tag_records = self.env['ks.shopify.product.tag'].search([
                        #         ('ks_shopify_instance', '=', instance.id)
                        #     ])
                        #     self.env['ks.shopify.queue.jobs'].ks_create_tag_record_in_queue(instance,
                        #                                                                 records=tag_records)
                        if self.ks_update_stock:
                            _logger.info("Stock Records Enqueue for Shopify Instance [%s -(%s)]",
                                         instance.ks_instance_name, instance.id)
                            stock_records = self.env['ks.shopify.product.template'].search([(
                                'ks_shopify_instance.id', '=', instance.id)])
                            _logger.info("Stock being exported to Shopify with %s records." % str(
                                len(stock_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_stock_record_in_queue(instance,
                                                                                                 records=stock_records)
                        if self.ks_update_products:
                            _logger.info('Product entry enqueue for Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            product_records = self.env['ks.shopify.product.template'].search([
                                ('ks_shopify_instance', '=', instance.id)
                            ])
                            _logger.info("Products being exported to Shopify with %s records." % str(
                                len(product_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(instance,
                                                                                                records=product_records)
                        if self.ks_update_product_to_draft:
                            _logger.info('Product entry enqueue for Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            product_records = self.env['ks.shopify.product.template'].search([
                                ('ks_shopify_instance', '=', instance.id)
                            ])
                            _logger.info("Products being exported to Shopify with %s records." % str(
                                len(product_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_product_status_record_in_queue(instance,
                                                                                                       records=product_records,
                                                                                                       domain='draft')
                        if self.ks_update_product_to_active:
                            _logger.info('Product entry enqueue for Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            product_records = self.env['ks.shopify.product.template'].search([
                                ('ks_shopify_instance', '=', instance.id)
                            ])
                            _logger.info("Products being exported to Shopify with %s records." % str(
                                len(product_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_product_status_record_in_queue(instance,
                                                                                                       records=product_records,
                                                                                                       domain='active')
                        # if self.ks_update_coupons:
                        #     _logger.info('Coupons enqueue start For Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     coupon_records = self.env['ks.shopify.coupons'].search(
                        #         [('ks_shopify_instance.id', '=', instance.id)])
                        #     self.env['ks.shopify.queue.jobs'].ks_create_coupon_record_in_queue(instance=instance,
                        #                                                                    records=coupon_records)
                        # if self.ks_operation_shopify == 'export_collection':
                        #     _logger.info("Collection Records Enqueue for Shopify Instance [%s -(%s)]",
                        #                  instance.ks_instance_name, instance.id)
                        #     collection_records = self.env['ks.shopify.custom.collections'].search([(
                        #         'ks_shopify_instance.id', '=', instance.id)])
                        #     self.env['ks.shopify.queue.jobs'].ks_create_collections_record_in_queue(instance,
                        #                                                                             records=collection_records)
                        if self.ks_update_customers:
                            # Update Customers on shopify
                            _logger.info('Customer entry enqueue for Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            customer_records = self.env['ks.shopify.partner'].search(
                                [('ks_shopify_instance.id', '=', instance.id), ('ks_type', '=', 'customer')])
                            _logger.info("Customers being exported to Shopify with %s records." % str(
                                len(customer_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_customer_record_in_queue(instance,
                                                                                                 records=customer_records)
                        if self.ks_update_collections:
                            _logger.info("Collection Records Enqueue for Shopify Instance [%s -(%s)]",
                                         instance.ks_instance_name, instance.id)
                            collection_records = self.env['ks.shopify.custom.collections'].search([(
                                'ks_shopify_instance.id', '=', instance.id)])
                            _logger.info("Collections being exported to Shopify with %s records." % str(
                                len(collection_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_collections_record_in_queue(instance,
                                                                                                    records=collection_records)
                        if self.ks_update_discount:
                            _logger.info("Discount Records Enqueue for Shopify Instance [%s -(%s)]",
                                         instance.ks_instance_name, instance.id)
                            discount_records = self.env['ks.shopify.discounts'].search([(
                                'ks_shopify_instance.id', '=', instance.id)])
                            _logger.info("Discounts being exported to Shopify with %s records." % str(
                                len(discount_records)))
                            self.env['ks.shopify.queue.jobs'].ks_create_discount_record_in_queue(instance,
                                                                                                 records=discount_records)
                        if self.ks_sync_orders:
                            _logger.info('Orders enqueue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            # filter the order status selected on instance to be synced
                            order_status = ','.join(instance.ks_order_status.mapped('status'))
                            orders_json_records = self.env['sale.order'].ks_get_all_shopify_orders(
                                instance=instance, status=order_status)
                            if orders_json_records:
                                _logger.info("Orders fetched from Shopify with %s records." % str(
                                    len(orders_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_order_record_in_queue(instance=instance,
                                                                                                  data=orders_json_records)
                            else:
                                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                                                                                  ks_type='order',
                                                                                  ks_shopify_instance=instance,
                                                                                  ks_record_id=0,
                                                                                  ks_message='Orders Sync operation to queue jobs failed',
                                                                                  ks_shopify_id=0,
                                                                                  ks_operation_flow='shopify_to_odoo',
                                                                                  ks_status="failed")
                        if self.ks_sync_draft_orders:
                            _logger.info('Orders enqueue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            # filter the order status selected on instance to be synced
                            order_status = ','.join(instance.ks_order_status.mapped('status'))
                            orders_json_records = self.env['sale.order'].ks_get_all_shopify_draft_orders(
                                instance=instance)
                            if orders_json_records:
                                _logger.info("Orders fetched from Shopify with %s records." % str(
                                    len(orders_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_order_record_in_queue(instance=instance,
                                                                                                  data=orders_json_records,
                                                                                                  order_type="draft")
                            else:
                                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                                                                                  ks_type='order',
                                                                                  ks_shopify_instance=instance,
                                                                                  ks_record_id=0,
                                                                                  ks_message='Orders Sync operation to queue jobs failed',
                                                                                  ks_shopify_id=0,
                                                                                  ks_operation_flow='shopify_to_odoo',
                                                                                  ks_status="failed")
                        if self.ks_sync_customers:
                            # Sync Customers
                            _logger.info('Customer enqueue For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            customer_json_records = self.env['ks.shopify.partner'].ks_shopify_get_all_customers(
                                instance=instance)
                            if customer_json_records:
                                _logger.info("Customers fetched from Shopify with %s records." % str(
                                    len(customer_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_customer_record_in_queue(instance=instance,
                                                                                                     data=customer_json_records)
                            else:
                                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                                                                                  ks_type='customer',
                                                                                  ks_shopify_instance=instance,
                                                                                  ks_record_id=0,
                                                                                  ks_message="Customer Sync operation to queue jobs failed",
                                                                                  ks_shopify_id=0,
                                                                                  ks_operation_flow='shopify_to_odoo',
                                                                                  ks_status="failed")
                        # if self.ks_sync_coupons:
                        #     _logger.info('Coupons enqueue start For Shopify Instance [%s -(%s)]'
                        #                  , instance.ks_instance_name, instance.id)
                        #     coupons_json_records = self.env['ks.shopify.coupons'].ks_shopify_get_all_coupon(
                        #         instance=instance)
                        #     if coupons_json_records:
                        #         self.env['ks.shopify.queue.jobs'].ks_create_coupon_record_in_queue(instance=instance,
                        #                                                                        data=coupons_json_records)
                        #     else:
                        #         self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                        #                                                       ks_type='coupon',
                        #                                                       ks_shopify_instance=instance,
                        #                                                       ks_record_id=0,
                        #                                                       ks_message='Coupons Sync operation to queue jobs failed',
                        #                                                       ks_shopify_id=0,
                        #                                                       ks_operation_flow='shopify_to_odoo',
                        #                                                       ks_status="failed")
                        if self.ks_stock:
                            _logger.info("Stock importing start for Shopify instance [%s -(%s)]",
                                         instance.ks_instance_name, instance.id)
                            product_json_records = self.env['ks.shopify.product.template'].ks_shopify_get_all_products(
                                instance=instance)
                            if product_json_records:
                                _logger.info("Stocks fetched from Shopify with %s records." % str(
                                    len(product_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_import_stock_shopify_in_queue(
                                    instance=instance,
                                    data=product_json_records)
                            else:
                                self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='import',
                                                                                  ks_type='stock',
                                                                                  ks_shopify_instance=instance,
                                                                                  ks_record_id=0,
                                                                                  ks_message='Stock sync failed',
                                                                                  ks_shopify_id=0,
                                                                                  ks_operation_flow='shopify_to_odoo',
                                                                                  ks_status="failed")
                        if self.ks_sync_products:
                            _logger.info('Product enqueue start For Shopify Instance [%s -(%s)]'
                                         , instance.ks_instance_name, instance.id)
                            product_json_records = self.env['ks.shopify.product.template'].ks_shopify_get_all_products(
                                instance=instance)
                            if product_json_records:
                                _logger.info("Products fetched from Shopify with %s records." % str(
                                    len(product_json_records)))
                                self.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(instance=instance,
                                                                                                    data=product_json_records)

                except ConnectionError:
                    self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                                                                      ks_type='system_status',
                                                                      ks_shopify_instance=instance,
                                                                      ks_record_id=0,
                                                                      ks_message="Sync operation to queue jobs failed due to ",
                                                                      ks_shopify_id=0,
                                                                      ks_status="failed",
                                                                      ks_operation_flow='shopify_to_odoo',
                                                                      ks_error=ConnectionError)
                except Exception as e:
                    self.env['ks.shopify.logger'].ks_create_log_param(ks_operation_performed='create',
                                                                      ks_type='system_status',
                                                                      ks_shopify_instance=instance,
                                                                      ks_record_id=0,
                                                                      ks_message="Sync operation to queue jobs failed due to",
                                                                      ks_shopify_id=0,
                                                                      ks_operation_flow='shopify_to_odoo',
                                                                      ks_status="failed",
                                                                      ks_error=e)
            else:
                raise ValidationError("Instance is not Connected or Activated")
        cron_record = self.env.ref('ks_shopify.ks_ir_cron_job_process')
        if cron_record:
            next_exc_time = datetime.now()
            cron_record.sudo().write({'nextcall': next_exc_time, 'active': True})
        return self.env['ks.message.wizard'].ks_pop_up_message(names='Info', message="Shopify Operations has "
                                                                                     "been performed, Please refer "
                                                                                     "logs for further details.")
