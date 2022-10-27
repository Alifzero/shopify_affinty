# -*- coding: utf-8 -*-

import json
import logging
from odoo.tools import date_utils

from odoo import models, fields,api,_

_logger = logging.getLogger(__name__)


class KsQueueManager(models.TransientModel):
    _name = 'ks.shopify.queue.jobs'
    _description = 'Sync all operation in Queue'
    _rec_name = 'ks_name'
    _order = 'id desc'

    ks_model = fields.Selection([('product_template', 'Product Template'), ('product_product', 'Product Variants'),
                                 ('sale_order', 'Sale Order'), ('customer', 'Customer'), ('discount', 'Discounts'),
                                 ('attribute', 'Attributes'), ('tag', 'Tags'), ('category', 'Category'),
                                 ('delivery', 'Delivery'), ('invoice', 'Invoices'), ('refund', 'Refunds'),
                                 ("stock", "stock"), ("tax", "Tax"), ('collection', 'Collections'), ('locations', 'Location'),
                                 ('attribute_value', 'Attribute Value'), ('payment_gateway', 'Payment Gateway'),
                                 ('product_template_draft', 'Draft Product'), ('product_template_active', 'Active Product')],
                                string='Domain')
    ks_odoo_model = fields.Many2one("ir.model", string="Base Model")
    ks_layer_model = fields.Char(string="Layer Model")
    ks_name = fields.Char('Name')
    ks_operation = fields.Selection([('shopify_to_odoo', 'Shopify To Odoo'),
                                     ('odoo_to_shopify', 'Odoo to Shopify'),
                                     ('shopify_to_wl', 'Shopify to Shopify Layer'),
                                     ('wl_to_shopify', 'Shopify Layer to Shopify'),
                                     ('odoo_to_wl', 'Odoo to Shopify Layer'),
                                     ('wl_to_odoo', 'Shopify Layer to Odoo')],
                                    string="Operation Flow")
    ks_operation_type = fields.Selection([('create', 'Create'), ('update', 'Update')], "Operation Performed")
    ks_type = fields.Selection([('import', 'Import'), ('export', 'Export'), ('prepare', 'Prepare')],
                               string="Operation Type")
    state = fields.Selection([('new', 'New'), ('progress', 'In Progress'), ('done', 'Done'), ('failed', 'Failed')],
                             string='State', default='new')
    ks_shopify_id = fields.Char('Shopify ID')
    ks_record_id = fields.Integer('Odoo ID')
    ks_shopify_instance = fields.Many2one('ks.shopify.connector.instance', 'Shopify Instance')
    ks_data = fields.Text('Shopify Data')
    ks_images_with_products = fields.Boolean()
    ks_direct_export = fields.Boolean()
    ks_direct_update = fields.Boolean()
    ks_product_config = fields.Text()
    # ks_company_id = fields.Many2one("res.company", string="Company", compute="_compute_company", store=True,
    #                                 help="Displays Company Name")
    #
    # @api.depends('ks_shopify_instance')
    # def _compute_company(self):
    #     """
    #     Computes company for the Shopify operation in Queue
    #     :return:
    #     """
    #     for rec in self:
    #         if rec.ks_shopify_instance.ks_company_id:
    #             rec.ks_company_id = rec.ks_shopify_instance.ks_company_id.id
    #         else:
    #             rec.ks_company_id = self._context.get('company_id', self.env.company.id)

    def ks_process_queue_jobs(self):
        if not self.id:
            self = self.search([('state', 'in', ['new', 'failed', 'progress'])])
        for record in self:
            if record.ks_type == 'prepare':
                record.ks_update_progress_state()
                current_record = self.env[record.ks_odoo_model.model].search([('id', '=', record.ks_record_id)])
                if record.ks_operation_type == 'create':
                    try:
                        self.env[record.ks_layer_model].create_shopify_record(record.ks_shopify_instance,
                                                                              current_record, record.ks_direct_export,
                                                                              queue_record=record)
                        if record.state == 'progress':
                            record.ks_update_done_state()
                        self.env['ir.cron'].cron_initiate()
                        continue
                    except Exception as e:
                        self.env.cr.commit()
                        _logger.info(str(e))
                    self.env['ir.cron'].cron_initiate()

                if record.ks_operation_type == 'update':
                    try:
                        is_already_exported = self.env[record.ks_layer_model].check_if_already_prepared(
                            record.ks_shopify_instance, current_record)
                        if is_already_exported:
                            self.env[record.ks_layer_model].update_shopify_record(record.ks_shopify_instance,
                                                                                  current_record,
                                                                                  record.ks_direct_update,
                                                                                  queue_record=record)
                            if record.state == 'progress':
                                record.ks_update_done_state()
                            self.env['ir.cron'].cron_initiate()
                            continue
                        else:
                            self.env['ks.shopify.logger'].ks_create_prepare_log_params(
                                operation_performed="prepare_update",
                                status="failed",
                                instance=record.ks_shopify_instance,
                                id=record.id,
                                message="Error in Prepare Update")

                    except Exception as e:
                        self.env.cr.commit()
                        _logger.info(str(e))
                    self.env['ir.cron'].cron_initiate()

            if record.ks_model == 'discount':
                record.ks_update_progress_state()
                try:
                    if record.ks_operation == 'shopify_to_wl':
                        _logger.info("Discounts syncing from Shopify to odoo starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        discount_data = json.loads(record.ks_data)
                        discount_record_exist = self.env['ks.shopify.discounts'].ks_manage_shopify_discounts_import(
                            record.ks_shopify_instance,
                            discount_data,
                            queue_record=record
                        )
                        if discount_record_exist:
                            record.ks_record_id = discount_record_exist.id
                    elif record.ks_operation == 'wl_to_shopify':
                        _logger.info("Discounts export from odoo to Shopify starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        discount_record = self.env['ks.shopify.discounts'].browse(record.ks_record_id)
                        discount_response = discount_record.ks_manage_shopify_discounts_export(
                            queue_record=record)
                        if discount_response and discount_response.get("id"):
                            record.ks_shopify_id = discount_response.get("id")
                except Exception as e:
                    record.ks_update_failed_state()
                    _logger.info(str(e))
                    self.env.cr.commit()
                if record.state == 'progress':
                    record.ks_update_done_state()
                self.env['ir.cron'].cron_initiate()
            if record.ks_model == 'locations':
                record.ks_update_progress_state()
                try:
                    if record.ks_operation == 'shopify_to_wl':
                        _logger.info("Locations syncing from Shopify to odoo starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        locations_data = json.loads(record.ks_data)
                        location_record_exist = self.env['ks.shopify.locations'].ks_manage_shopify_locations_import(
                            record.ks_shopify_instance,
                            locations_data,
                            queue_record=record
                        )
                except Exception as e:
                    record.ks_update_failed_state()
                    _logger.info(str(e))
                    self.env.cr.commit()
                if record.state == 'progress':
                    record.ks_update_done_state()
                self.env['ir.cron'].cron_initiate()

            if record.ks_model == 'collection':
                record.ks_update_progress_state()
                try:
                    if record.ks_operation == 'shopify_to_wl':
                        _logger.info("Collections syncing from Shopify to odoo starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        collection_data = json.loads(record.ks_data)
                        collection_record_exist = self.env[
                            'ks.shopify.custom.collections'].ks_manage_shopify_collections_import(
                            record.ks_shopify_instance,
                            collection_data,
                            queue_record=record)
                        if collection_record_exist:
                            record.ks_record_id = collection_record_exist.id
                    elif record.ks_operation == 'wl_to_shopify':
                        _logger.info("Collections export from odoo to Shopify starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        collection_record = self.env['ks.shopify.custom.collections'].browse(record.ks_record_id)
                        shopify_customer_response = collection_record.ks_manage_shopify_collection_export(
                            queue_record=record)
                        if shopify_customer_response.get("id"):
                            record.ks_shopify_id = shopify_customer_response.get("id")

                except Exception as e:
                    record.ks_update_failed_state()
                    _logger.info(str(e))
                    self.env.cr.commit()
                if record.state == 'progress':
                    record.ks_update_done_state()
                self.env['ir.cron'].cron_initiate()
            if record.ks_model == 'customer':
                record.ks_update_progress_state()
                try:
                    if record.ks_operation == 'shopify_to_wl':
                        _logger.info("Customer syncing from Shopify to odoo starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        customer_data = json.loads(record.ks_data)
                        customer_record_exist = self.env['ks.shopify.partner'].ks_manage_shopify_customer_import(
                            record.ks_shopify_instance,
                            customer_data,
                            queue_record=record)
                        if customer_record_exist:
                            record.ks_record_id = customer_record_exist.id
                    elif record.ks_operation == 'wl_to_shopify':
                        _logger.info("Customer export from odoo to Shopify starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        customer_record = self.env['ks.shopify.partner'].browse(record.ks_record_id)
                        shopify_customer_response = customer_record.ks_manage_shopify_customer_export(
                            queue_record=record)
                        if shopify_customer_response and shopify_customer_response.get("id"):
                            record.ks_shopify_id = shopify_customer_response.get("id")
                except Exception as e:
                    record.ks_update_failed_state()
                    _logger.info(str(e))
                    self.env.cr.commit()
                if record.state == 'progress':
                    record.ks_update_done_state()
                self.env['ir.cron'].cron_initiate()
            if record.ks_model == 'product_template':
                record.ks_update_progress_state()
                try:
                    if record.ks_operation == 'shopify_to_wl':
                        _logger.info("Product syncing from Shopify to odoo starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        product_data = json.loads(record.ks_data)
                        shopify_product = self.env[
                            'ks.shopify.product.template'].ks_manage_shopify_product_template_import(
                            record.ks_shopify_instance,
                            product_data,
                            queue_record=record)
                        if shopify_product:
                            record.ks_record_id = shopify_product.id
                        else:
                            record.ks_update_failed_state()
                            self.env.cr.commit()
                    elif record.ks_operation == 'wl_to_shopify':
                        _logger.info("Product export from odoo to Shopify starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        product_record = self.env['ks.shopify.product.template'].browse(record.ks_record_id)
                        product_config_data = False
                        if record.ks_product_config and product_record.ks_shopify_product_type == 'simple':
                            data = json.loads(record.ks_product_config)[0]
                            product_config_data = [{
                                'ks_domain': data.get('ks_domain'),
                                'ks_id': data.get('id'),
                                'ks_multi_record': data.get('ks_multi_record'),
                                'ks_inventory_policy': data.get('ks_inventory_policy') if data.get('ks_push_additional_data') else False,
                                'ks_update_image': data.get('ks_update_image'),
                                'ks_update_price': data.get('ks_update_price'),
                                'ks_update_stock': data.get('ks_update_stock'),
                                'ks_barcode': data.get('ks_barcode'),
                                'ks_update_website_status': data.get('ks_update_website_status'),
                                'ks_shopify_description': data.get('ks_shopify_description'),
                                'ks_shopify_tags': data.get('ks_shopify_tags'),
                                'ks_shopify_type_product': data.get('ks_shopify_type_product'),
                                'ks_shopify_vendor': data.get('ks_shopify_vendor'),
                                'ks_price': data.get('ks_price'),
                                'ks_compare_at_price': data.get('ks_compare_at_price'),
                                'ks_product_product': data.get('ks_product_product'),
                            }]
                        else:
                            if record and record.ks_record_id:
                                data = json.loads(record.ks_product_config)[0] if record.ks_product_config else False
                                records = record.ks_record_id
                                product_config_data = [{
                                    'ks_domain': 'product.template',
                                    'ks_id': records,
                                    'ks_inventory_policy': False,
                                    'ks_multi_record': data.get('ks_multi_record') if data else False,
                                    'ks_update_image': data.get('ks_update_image') if data else False,
                                    'ks_update_price': True,
                                    'ks_update_stock': data.get('ks_update_stock') if data else True,
                                    'ks_shopify_description': product_record.ks_shopify_description,
                                    'ks_barcode': product_record.ks_barcode,
                                    'ks_shopify_tags': product_record.ks_shopify_tags,
                                    'ks_shopify_type_product': product_record.ks_shopify_type_product,
                                    'ks_shopify_vendor': product_record.ks_shopify_vendor,
                                    'ks_update_website_status': "published" if product_record.ks_published else "draft",
                                    'ks_price': product_record.ks_shopify_rp_pricelist.fixed_price or product_record.ks_shopify_rp_pricelist.search([('product_id', '=', product_record.ks_shopify_product_template.product_variant_id.id), ('pricelist_id', '=', product_record.ks_shopify_instance.ks_shopify_regular_pricelist.id)], limit=1).fixed_price,
                                    'ks_compare_at_price': product_record.ks_shopify_cp_pricelist.fixed_price or product_record.ks_shopify_cp_pricelist.search([('product_id', '=', product_record.ks_shopify_product_template.product_variant_id.id), ('pricelist_id', '=', product_record.ks_shopify_instance.ks_shopify_compare_pricelist.id)], limit=1).fixed_price,
                                    'ks_product_product': True if len(
                                        product_record.ks_shopify_variant_ids) > 1 else False,
                                }]
                            # product_config_data = json.dumps(raw_data, default=date_utils.json_default)
                        product_config = product_config_data if product_config_data else False
                        product_record.ks_manage_shopify_product_template_export(record.ks_shopify_instance,
                                                                                 queue_record=record,
                                                                                 product_config=product_config)
                        if product_record.ks_shopify_product_id:
                            record.ks_shopify_id = product_record.ks_shopify_product_id
                    if record.state == 'progress':
                        record.ks_update_done_state()
                    self.env['ir.cron'].cron_initiate()
                except Exception as e:
                    record.ks_update_failed_state()
                    self.env.cr.commit()
                    _logger.info(str(e))
                self.env['ir.cron'].cron_initiate()
            if record.ks_model == 'product_template_draft':
                record.ks_update_progress_state()
                try:
                    if record.ks_operation == 'wl_to_shopify':
                        _logger.info("Product status syncing from Shopify to odoo starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        # product_data = json.loads(record.ks_data)
                        product_record = self.env['ks.shopify.product.template'].browse(record.ks_record_id)
                        product_record.ks_update_product_status_to_shopify(record.ks_shopify_instance, domain='draft')
                        if record.state == 'progress':
                            self.env['ks.shopify.logger'].ks_create_odoo_log_param(
                                ks_operation_performed="create",
                                ks_model='product.template',
                                ks_layer_model='product.template',
                                ks_message="Product status update Successful",
                                ks_status="success",
                                ks_type="product_status",
                                ks_record_id=record.id,
                                ks_operation_flow="odoo_to_shopify",
                                ks_shopify_id=0,
                                ks_shopify_instance=record.ks_shopify_instance)
                            record.ks_update_done_state()
                        self.env['ir.cron'].cron_initiate()
                except Exception as e:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(
                        ks_operation_performed="create",
                        ks_model='product.template',
                        ks_layer_model='product.template',
                        ks_message="Product status update Successful",
                        ks_status="failed",
                        ks_type="product_status",
                        ks_record_id=record.id,
                        ks_operation_flow="odoo_to_shopify",
                        ks_shopify_id=0,
                        ks_shopify_instance=record.ks_shopify_instance)
                    record.ks_update_failed_state()
                    self.env.cr.commit()
                    _logger.info(str(e))
                self.env['ir.cron'].cron_initiate()
            if record.ks_model == 'product_template_active':
                record.ks_update_progress_state()
                try:
                    if record.ks_operation == 'wl_to_shopify':
                        _logger.info("Product status syncing from Shopify to odoo starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        # product_data = json.loads(record.ks_data)
                        product_record = self.env['ks.shopify.product.template'].browse(record.ks_record_id)
                        product_record.ks_update_product_status_to_shopify(record.ks_shopify_instance, domain='active')
                        if record.state == 'progress':
                            self.env['ks.shopify.logger'].ks_create_odoo_log_param(
                                ks_operation_performed="create",
                                ks_model='product.template',
                                ks_layer_model='product.template',
                                ks_message="Product status update Successful",
                                ks_status="success",
                                ks_type="product_status",
                                ks_record_id=record.id,
                                ks_operation_flow="odoo_to_shopify",
                                ks_shopify_id=0,
                                ks_shopify_instance=record.ks_shopify_instance)
                            record.ks_update_done_state()
                        self.env['ir.cron'].cron_initiate()
                except Exception as e:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(
                        ks_operation_performed="create",
                        ks_model='product.template',
                        ks_layer_model='product.template',
                        ks_message="Product status update Successful",
                        ks_status="failed",
                        ks_type="product_status",
                        ks_record_id=record.id,
                        ks_operation_flow="odoo_to_shopify",
                        ks_shopify_id=0,
                        ks_shopify_instance=record.ks_shopify_instance)
                    record.ks_update_failed_state()
                    self.env.cr.commit()
                    _logger.info(str(e))
                self.env['ir.cron'].cron_initiate()
            if record.ks_model == 'stock':
                record.ks_update_progress_state()
                try:
                    if record.ks_operation == 'wl_to_shopify':
                        _logger.info("Locations syncing from Odoo to Shopify starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        stock_data = self.env['ks.shopify.product.template'].sudo().search([('ks_shopify_product_id', '=', record.ks_shopify_id), ('ks_shopify_instance', '=', record.ks_shopify_instance.id)])
                        stock_record_exist = stock_data.ks_action_shopify_export_product_stock()
                    elif record.ks_operation == 'shopify_to_odoo':
                        _logger.info("Stock syncing from Shopify to odoo starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        product_data = json.loads(record.ks_data)
                        product_data_non_filter = self.env[
                            'ks.shopify.product.template'].ks_get_product_data_for_stock_adjustment(
                            product_data, record.ks_shopify_instance)
                        valid_product_data = []
                        for rec in product_data_non_filter:
                            if rec.get('product_id'):
                                valid_product_data.append(rec)
                        inventory_adjustment_created = self.env['stock.inventory'].ks_create_stock_inventory_adjustment(
                            valid_product_data, record.ks_shopify_instance.ks_warehouse.lot_stock_id,
                            queue_record=record)
                        if inventory_adjustment_created:
                            for inventory in inventory_adjustment_created:
                                inventory.for_shopify = True
                    if record.state == 'progress':
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(
                            ks_operation_performed="create",
                            ks_model='stock.inventory',
                            ks_layer_model='stock.inventory',
                            ks_message="Inventory Operation Successful",
                            ks_status="success",
                            ks_type="stock",
                            ks_record_id=record.id,
                            ks_operation_flow='shopify_to_odoo' if record.ks_operation == 'shopify_to_odoo' else 'odoo_to_shopify',
                            ks_shopify_id=0,
                            ks_shopify_instance=record.ks_shopify_instance)
                        record.ks_update_done_state()
                    self.env['ir.cron'].cron_initiate()
                except Exception as e:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(
                        ks_operation_performed="create",
                        ks_model='stock.inventory',
                        ks_layer_model='stock.inventory',
                        ks_message="Inventory Operation error",
                        ks_status="failed",
                        ks_type="stock",
                        ks_record_id=record.id,
                        ks_operation_flow='shopify_to_odoo' if record.ks_operation == 'shopify_to_odoo' else 'odoo_to_shopify',
                        ks_shopify_id=0,
                        ks_shopify_instance=record.ks_shopify_instance)
                    record.ks_update_failed_state()
                    self.env.cr.commit()
                    _logger.info(str(e))
                self.env['ir.cron'].cron_initiate()
            if record.ks_model == 'sale_order':
                record.ks_update_progress_state()
                try:
                    if record.ks_operation == 'shopify_to_odoo':
                        _logger.info("Orders syncing from Shopify to odoo starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        order_data = json.loads(record.ks_data)
                        order_record_exist = self.env['sale.order'].search(
                            ['|', ('ks_shopify_order_id', '=', record.ks_shopify_id),
                             ('ks_shopify_draft_order_id', '=', record.ks_shopify_id),
                             ('ks_shopify_instance', '=', record.ks_shopify_instance.id),])
                        if order_record_exist:
                            order_record_exist.ks_shopify_import_order_update(order_data, queue_record=record)
                        else:
                            if not order_data.get('cancelled_at'):
                                order_record_exist = order_record_exist.ks_shopify_import_order_create(
                                    order_data, record.ks_shopify_instance, queue_record=record)
                        if order_record_exist:
                            record.ks_record_id = order_record_exist.id

                    if record.ks_operation == 'odoo_to_shopify':
                        _logger.info("Orders syncing from Odoo to Shopify starts for instance [%s -(%s)]",
                                     record.ks_shopify_instance.ks_instance_name, record.ks_shopify_instance.id)
                        sale_order_record = self.env['sale.order'].browse(record.ks_record_id)
                        sale_order_record.ks_export_order_to_shopify(queue_record=record)
                except Exception as e:
                    record.ks_update_failed_state()
                    self.env.cr.commit()
                    _logger.info(str(e))
                if record.state == 'progress':
                    record.ks_update_done_state()
                self.env['ir.cron'].cron_initiate()
        #
        self += self.search([('state', 'in', ['new', 'failed', 'progress'])])

    #
    def get_model(self, instance_model):
        if instance_model == "ks.shopify.partner":
            return "customer"
        elif instance_model == "ks.shopify.product.variant":
            return "product_product"
        elif instance_model == "ks.shopify.product.template":
            return "product_template"
        elif instance_model == 'ks.shopify.product.tag':
            return "tag"
        elif instance_model == 'ks.shopify.product.category':
            return "category"
        elif instance_model == 'ks.shopify.product.attribute':
            return "attribute"
        elif instance_model == "ks.shopify.pro.attr.value":
            return "attribute_value"
        elif instance_model == 'ks.shopify.payment.gateway':
            return "payment_gateway"
        else:
            return "coupon"

    def ks_create_prepare_record_in_queue(self, instance, instance_model, active_model, record_id, type,
                                          update_to_shopify=False, export_to_shopify=False):
        current_record = self.env[active_model].browse(record_id)
        odoo_model = self.env['ir.model'].search([('model', '=', current_record._name)])
        model_involved = self.get_model(instance_model)
        record_data = {
            'ks_name': current_record.display_name,
            'ks_shopify_instance': instance.id,
            'ks_record_id': record_id,
            'ks_odoo_model': odoo_model.id,
            'ks_type': 'prepare',
            'ks_operation_type': type,
            'ks_operation': 'odoo_to_wl',
            "ks_direct_update": update_to_shopify,
            "ks_direct_export": export_to_shopify,
            'ks_layer_model': instance_model,
            'ks_model': model_involved
        }
        try:
            self.create(record_data)
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create_in_queue',
                                                                   ks_model=active_model,
                                                                   ks_shopify_instance=instance,
                                                                   ks_record_id=record_id,
                                                                   ks_message='Prepare operation to queue jobs added Successfully',
                                                                   ks_shopify_id=0,
                                                                   ks_operation_flow='odoo_to_shopify',
                                                                   ks_status="success",
                                                                   ks_type="system_status")
            self.env['ir.cron'].cron_initiate()
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create_in_queue',
                                                                   ks_model=active_model,
                                                                   ks_shopify_instance=instance,
                                                                   ks_record_id=record_id,
                                                                   ks_message="Prepare operation to queue jobs Failed due to %s" % e,
                                                                   ks_shopify_id=0,
                                                                   ks_operation_flow='odoo_to_shopify',
                                                                   ks_status="Failed",
                                                                   ks_type="system_status")

    def ks_create_discount_record_in_queue(self, instance=False, data=[], records=[]):
        vals = []
        if data:
            for record in data:
                collection_data = {
                    'ks_name': record.get('title'),
                    'ks_shopify_instance': instance.id,
                    'ks_data': json.dumps(record),
                    'ks_type': 'import',
                    'state': 'new',
                    'ks_operation': 'shopify_to_wl',
                    'ks_model': 'discount',
                    'ks_shopify_id': record.get('id')
                }
                vals.append(collection_data)
        elif records:
            for each_record in records:
                collection_data = {
                    'ks_name': each_record.display_name,
                    'ks_model': 'discount',
                    'ks_record_id': each_record.id,
                    'ks_shopify_id': each_record.ks_shopify_discount_id,
                    'ks_operation': 'wl_to_shopify',
                    'state': 'new',
                    'ks_shopify_instance': each_record.ks_shopify_instance.id,
                    'ks_type': 'export'
                }
                vals.append(collection_data)
        if vals:
            self.create(vals)
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create_in_queue',
                                                                   ks_type='discount',
                                                                   ks_shopify_instance=instance,
                                                                   ks_record_id=0,
                                                                   ks_message="Discount Sync operation to queue jobs added Successfully",
                                                                   ks_shopify_id=0,
                                                                   ks_operation_flow='odoo_to_shopify' if records else 'shopify_to_odoo',
                                                                   ks_status="success")
            self.env['ir.cron'].cron_initiate()

    def ks_create_stock_record_in_queue(self, instance=False, data=[], records=[]):
        vals = []
        if data:
            for record in data:
                stock_data = {
                    'ks_name': record.get('name'),
                    'ks_shopify_instance': instance.id,
                    'ks_data': json.dumps(record),
                    'ks_type': 'import',
                    'state': 'new',
                    'ks_operation': 'shopify_to_wl',
                    'ks_model': 'stock',
                    'ks_shopify_id': record.get('id')
                }
                vals.append(stock_data)
        elif records:
            for each_record in records:
                stock_data = {
                    'ks_name': each_record.display_name,
                    'ks_model': 'stock',
                    'ks_record_id': each_record.id,
                    'ks_shopify_id': each_record.ks_shopify_product_id,
                    'ks_operation': 'wl_to_shopify',
                    'state': 'new',
                    'ks_shopify_instance': each_record.ks_shopify_instance.id,
                    'ks_type': 'export'
                }
                vals.append(stock_data)
        if vals:
            self.create(vals)
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create_in_queue',
                                                                   ks_type='stock',
                                                                   ks_shopify_instance=instance,
                                                                   ks_record_id=0,
                                                                   ks_message="Stock Sync operation to queue jobs added Successfully",
                                                                   ks_shopify_id=0,
                                                                   ks_operation_flow='odoo_to_shopify' if records else 'shopify_to_odoo',
                                                                   ks_status="success")
            self.env['ir.cron'].cron_initiate()

    def ks_create_collections_record_in_queue(self, instance=False, data=[], records=[], option=None):
        vals = []
        if data:
            for record in data:
                collection_data = {
                    'ks_name': record.get('title'),
                    'ks_shopify_instance': instance.id,
                    'ks_data': json.dumps(record),
                    'ks_type': 'import',
                    'state': 'new',
                    'ks_operation': 'shopify_to_wl',
                    'ks_model': 'collection',
                    'ks_shopify_id': record.get('id')
                }
                vals.append(collection_data)
        elif records:
            for each_record in records:
                collection_data = {
                    'ks_name': each_record.display_name,
                    'ks_model': 'collection',
                    'ks_record_id': each_record.id,
                    'ks_shopify_id': each_record.ks_shopify_collection_id,
                    'ks_operation': 'wl_to_shopify',
                    'state': 'new',
                    'ks_shopify_instance': each_record.ks_shopify_instance.id,
                    'ks_type': 'export'
                }
                vals.append(collection_data)
        if vals:
            self.create(vals)
            if not option:
                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create_in_queue',
                                                                       ks_type='collection',
                                                                       ks_shopify_instance=instance,
                                                                       ks_record_id=0,
                                                                       ks_message="Collection Sync operation to queue jobs added Successfully",
                                                                       ks_shopify_id=0,
                                                                       ks_operation_flow='odoo_to_shopify' if records else 'shopify_to_odoo',
                                                                       ks_status="success")
            self.env['ir.cron'].cron_initiate()

    def ks_create_locations_record_in_queue(self, instance=False, data=[], records=[]):
        vals = []
        if data:
            for record in data:
                location_data = {
                    'ks_name': record.get('name'),
                    'ks_shopify_instance': instance.id,
                    'ks_data': json.dumps(record),
                    'ks_type': 'import',
                    'state': 'new',
                    'ks_operation': 'shopify_to_wl',
                    'ks_model': 'locations',
                    'ks_shopify_id': record.get('id')
                }
                vals.append(location_data)
        elif records:
            for each_record in records:
                location_data = {
                    'ks_name': each_record.display_name,
                    'ks_model': 'locations',
                    'ks_record_id': each_record.id,
                    'ks_shopify_id': each_record.ks_shopify_location_id,
                    'ks_operation': 'wl_to_shopify',
                    'state': 'new',
                    'ks_shopify_instance': each_record.ks_shopify_instance.id,
                    'ks_type': 'export'
                }
                vals.append(location_data)
        if vals:
            self.create(vals)
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create_in_queue',
                                                                   ks_type='locations',
                                                                   ks_shopify_instance=instance,
                                                                   ks_record_id=0,
                                                                   ks_message="Location Sync operation to queue jobs added Successfully",
                                                                   ks_shopify_id=0,
                                                                   ks_operation_flow='odoo_to_shopify' if records else 'shopify_to_odoo',
                                                                   ks_status="success")
            self.env['ir.cron'].cron_initiate()

    def ks_create_customer_record_in_queue(self, instance=False, data=False, records=False, option=None):
        vals = []
        if data:
            for record in data:
                ks_shopify_id = record.get('id')
                customer_data = {
                    'ks_name': record.get('first_name'),
                    'ks_shopify_instance': instance.id,
                    'ks_data': json.dumps(record),
                    'ks_type': 'import',
                    'state': 'new',
                    'ks_operation': 'shopify_to_wl',
                    'ks_model': 'customer',
                    'ks_shopify_id': ks_shopify_id
                }
                vals.append(customer_data)
        elif records:
            for each_record in records:
                customer_data = {
                    'ks_name': each_record.display_name,
                    'ks_model': 'customer',
                    'ks_record_id': each_record.id,
                    'ks_shopify_id': each_record.ks_shopify_partner_id,
                    'ks_operation': 'wl_to_shopify',
                    'state': 'new',
                    'ks_shopify_instance': each_record.ks_shopify_instance.id,
                    'ks_type': 'export'
                }
                vals.append(customer_data)
        if vals:
            self.create(vals)
            if not option:
                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create_in_queue',
                                                                       ks_type='customer',
                                                                       ks_shopify_instance=instance,
                                                                       ks_record_id=0,
                                                                       ks_message="Customer Sync operation to queue jobs added Successfully",
                                                                       ks_shopify_id=0,
                                                                       ks_operation_flow='odoo_to_shopify' if records else 'shopify_to_odoo',
                                                                       ks_status="success")
            self.env['ir.cron'].cron_initiate()

    def ks_create_product_record_in_queue(self, instance=False, data=False, records=False, product_config=False, option=None):
        vals = []
        if data:
            for record in data:
                ks_shopify_id = record.get('id')
                product_data = {
                    'ks_name': record.get('title'),
                    'ks_shopify_instance': instance.id,
                    'ks_data': json.dumps(record),
                    'ks_type': 'import',
                    'state': 'new',
                    'ks_operation': 'shopify_to_wl',
                    'ks_model': 'product_template',
                    'ks_shopify_id': ks_shopify_id
                }
                vals.append(product_data)
        elif records:
            for each_record in records:
                product_data = {
                    'ks_name': each_record.display_name,
                    'ks_model': 'product_template',
                    'ks_record_id': each_record.id,
                    'ks_shopify_id': each_record.ks_shopify_product_id,
                    'ks_operation': 'wl_to_shopify',
                    'state': 'new',
                    'ks_shopify_instance': each_record.ks_shopify_instance.id,
                    'ks_type': 'export'
                }
                if product_config:
                    raw_data = product_config.read()
                    json_data = json.dumps(raw_data, default=date_utils.json_default)
                    product_data.update(
                        {
                            'ks_product_config': json_data
                        }
                    )
                vals.append(product_data)
        if vals:
            self.create(vals)
            if not option:
                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create_in_queue',
                                                                       ks_type='product',
                                                                       ks_shopify_instance=instance,
                                                                       ks_record_id=0,
                                                                       ks_message="Product Sync operation to queue jobs added Successfully",
                                                                       ks_shopify_id=0,
                                                                       ks_operation_flow='odoo_to_shopify' if records else 'shopify_to_odoo',
                                                                       ks_status="success")
            self.env['ir.cron'].cron_initiate()

    def ks_create_product_status_record_in_queue(self, instance=False, data=False, records=False, domain=False):
        vals = []
        if data:
            for record in data:
                ks_shopify_id = record.get('id')
                product_data = {
                    'ks_name': record.get('title'),
                    'ks_shopify_instance': instance.id,
                    'ks_data': json.dumps(record),
                    'ks_type': 'import',
                    'state': 'new',
                    'ks_operation': 'shopify_to_wl',
                    'ks_model': 'product_template_draft' if domain=='draft' else 'product_template_active',
                    'ks_shopify_id': ks_shopify_id
                }
                vals.append(product_data)
        elif records:
            for each_record in records:
                product = {
                    'ks_name': each_record.display_name,
                    'ks_model': 'product_template_draft' if domain=='draft' else 'product_template_active',
                    'ks_record_id': each_record.id,
                    'ks_shopify_id': each_record.ks_shopify_product_id,
                    'ks_operation': 'wl_to_shopify',
                    'state': 'new',
                    'ks_shopify_instance': each_record.ks_shopify_instance.id,
                    'ks_type': 'export'
                }
                vals.append(product)
        if vals:
            self.create(vals)
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create_in_queue',
                                                                   ks_type='product_status',
                                                                   ks_shopify_instance=instance,
                                                                   ks_record_id=0,
                                                                   ks_message="Product Status Sync operation to queue jobs added Successfully",
                                                                   ks_shopify_id=0,
                                                                   ks_operation_flow='odoo_to_shopify' if records else 'shopify_to_odoo',
                                                                   ks_status="success")
            self.env['ir.cron'].cron_initiate()

    def ks_import_stock_shopify_in_queue(self, instance, data):
        vals = []
        if data:
            # for record in data:
            stock_data = {
                'ks_name': 'Inventory Adjustment ',
                'ks_shopify_instance': instance.id,
                'ks_data': json.dumps(data),
                'ks_type': 'import',
                'state': 'new',
                'ks_operation': 'shopify_to_odoo',
                'ks_model': 'stock',
                'ks_shopify_id': 0
            }
            vals.append(stock_data)
        if vals:
            self.create(vals)
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create_in_queue',
                                                                   ks_type='stock',
                                                                   ks_shopify_instance=instance,
                                                                   ks_record_id=0,
                                                                   ks_message='stock import operation to queue jobs added Successfully',
                                                                   ks_shopify_id=0,
                                                                   ks_operation_flow='shopify_to_odoo',
                                                                   ks_status="success")

    def ks_create_order_record_in_queue(self, instance=False, data=False, records=False, order_type=False, option=None):
        vals = []
        if data:
            for record in data:
                if order_type:
                    record.update({
                        'order_type': order_type,
                    })
                shopify_id = record.get("id")
                order_data = {
                    'ks_name': "Sale Order #" + str(shopify_id),
                    'ks_shopify_instance': instance.id,
                    'ks_data': json.dumps(record),
                    'ks_type': 'import',
                    'state': 'new',
                    'ks_operation': 'shopify_to_odoo',
                    'ks_model': 'sale_order',
                    'ks_shopify_id': shopify_id
                }
                vals.append(order_data)
        if records:
            for each_record in records:
                order_data = {
                    'ks_name': each_record.display_name,
                    'ks_shopify_instance': each_record.ks_shopify_instance.id,
                    'ks_record_id': each_record.id,
                    'ks_type': 'export',
                    'state': 'new',
                    'ks_operation': 'odoo_to_shopify',
                    'ks_model': 'sale_order',
                    'ks_shopify_id': each_record.ks_shopify_order_id
                }
                vals.append(order_data)
        if vals:
            self.create(vals)
            if not option:
                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create_in_queue',
                                                                       ks_type='order',
                                                                       ks_shopify_instance=instance,
                                                                       ks_record_id=0,
                                                                       ks_message='Orders Enqueue operation to queue jobs added Successfully',
                                                                       ks_shopify_id=0,
                                                                       ks_operation_flow='odoo_to_shopify' if records else 'shopify_to_odoo',
                                                                       ks_status="success")
            self.env['ir.cron'].cron_initiate()

    def ks_update_failed_state(self):
        self.state = 'failed'
        self.env.cr.commit()

    def ks_update_done_state(self):
        self.state = 'done'
        self.env.cr.commit()

    def ks_update_progress_state(self):
        self.state = 'progress'
        self.env.cr.commit()
