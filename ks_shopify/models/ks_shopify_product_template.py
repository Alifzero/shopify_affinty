import logging
import re

import requests

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class KsShopifyProductTemplate(models.Model):
    _name = "ks.shopify.product.template"
    _rec_name = "ks_shopify_product_template"
    _description = "Shopify Product Model"
    _order = 'create_date desc'

    ks_shopify_description = fields.Html('Description', help="Message displayed as product description on Shopify")
    ks_shopify_short_description = fields.Html('Short Description',
                                               help="Message displayed as product short description on Shopify")
    ks_published = fields.Boolean('Shopify Product Active Status',
                                  copy=False,
                                  help="""Shopify Status: If enabled that means the product is published on the Shopify 
                                       Instance.""")
    ks_shopify_product_type = fields.Selection([('simple', 'Simple Product'), ('grouped', 'Grouped Product'),
                                                ('variable', 'Variable Product')], readonly=True,
                                               string='Shopify Product Type', store=True, default="simple",
                                               help="Displays Shopify Product Type")
    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Instance", readonly=True,
                                          help=_("Shopify Connector Instance reference"), ondelete='cascade')
    ks_shopify_product_id = fields.Char('Shopify Product ID',
                                        help=_("the record id of the particular record defied in the Connector"))
    ks_shopify_product_variant_id = fields.Char('Shopify Product Variant ID',
                                                help=_(
                                                    "the record id of the particular record defied in the Connector"))
    ks_date_created = fields.Datetime('Date Created', help=_("The date on which the record is created on the Connected"
                                                             " Connector Instance"), readonly=True)
    ks_date_updated = fields.Datetime('Date Updated', help=_("The latest date on which the record is updated on the"
                                                             " Connected Connector Instance"), readonly=True)
    ks_shopify_product_template = fields.Many2one('product.template', 'Odoo Product Template', readonly=True,
                                                  ondelete='cascade', help="Displays Odoo Linked Product Template Name")
    ks_name = fields.Char(string="Name", related="ks_shopify_product_template.name")
    ks_product_product = fields.Many2one('product.product', 'Odoo Product Variant',
                                         related="ks_shopify_product_template.product_variant_id",
                                         readonly=True)
    ks_shopify_type_product = fields.Char("Product Type")
    ks_shopify_tags = fields.Char("Tags")
    ks_shopify_vendor = fields.Char("Vendor")
    ks_shopify_inventory_id = fields.Char("Inventory ID")
    ks_shopify_variant_ids = fields.One2many('ks.shopify.product.variant', 'ks_shopify_product_tmpl_id',
                                             string='Variants',
                                             readonly=True)
    ks_shopify_rp_pricelist = fields.Many2one("product.pricelist.item", string="Regular Pricelist",
                                              help="Displays Shopify Regular Price")
    ks_shopify_cp_pricelist = fields.Many2one("product.pricelist.item", string="Compare Pricelist",
                                              help=" Displays Shopify Compare Price")
    ks_shopify_regular_price = fields.Float('Shopify Regular Price', compute="ks_update_shopify_regular_price",
                                            default=0.0)
    ks_shopify_compare_price = fields.Float('Shopify Compare Price', compute='ks_update_shopify_compare_price',
                                            default=0.0)
    ks_shopify_image_ids = fields.One2many('ks.shopify.product.images', 'ks_shopify_template_id', string='Images',
                                           readonly=True)
    ks_mapped = fields.Boolean(string="Manual Mapping", readonly=True)
    ks_barcode = fields.Char("Barcode", invisible=True)
    profile_image = fields.Many2one("ks.shopify.product.images", string="Profile Image")
    ks_collections_ids = fields.Many2many('ks.shopify.custom.collections', string="Collection Ids")
    ks_inventory_policy = fields.Selection([('continue', 'Continue'), ('deny', 'Deny')], 'Inventory Policy',
                                           default='deny', )
    ks_company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company.id,
                                    required=True, readonly=True, help=" Shows the name of the company")

    def ks_action_shopify_export_product_stock(self):
        self.ks_shopify_product_template.ks_action_shopify_export_product_template_stock()

    def ks_product_list_for_cron(self, cron_id=False):
        try:
            if not cron_id:
                if self._context.get('params'):
                    cron_id = self.env["ir.cron"].browse(self._context.get('params').get('id'))
            else:
                cron_id = self.env["ir.cron"].browse(cron_id)
            instance_id = cron_id.ks_shopify_instance
            if instance_id and instance_id.ks_instance_state == 'active':
                # order_status = ','.join(instance_id.ks_order_status.mapped('status'))
                product_records = self.search([
                    ('ks_shopify_instance', '=', instance_id.id)
                ])
                _logger.info("Products being exported to Shopify with %s records." % str(
                    len(product_records)))
                self.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(instance_id,
                                                                                    records=product_records)
        except Exception as e:
            _logger.info(str(e))

    @api.depends('ks_shopify_instance', 'ks_shopify_instance.ks_shopify_regular_pricelist',
                 'ks_shopify_instance.ks_shopify_compare_pricelist',
                 'ks_shopify_product_template.product_variant_id')
    @api.model
    def _ks_calculate_prices(self):
        for rec in self:
            rec.ks_shopify_rp_pricelist = False
            rec.ks_shopify_cp_pricelist = False
            if rec.ks_shopify_product_type == "simple":
                variant = rec.ks_shopify_product_template.product_variant_id
                instance = rec.ks_shopify_instance
                if instance and variant:
                    regular_price_list = self.env['product.pricelist.item'].search(
                        [('pricelist_id', '=', instance.ks_shopify_regular_pricelist.id),
                         ('product_id', '=', variant.id)], limit=1)
                    rec.ks_shopify_rp_pricelist = regular_price_list.id
                    compare_price_list = self.env['product.pricelist.item'].search(
                        [('pricelist_id', '=', instance.ks_shopify_compare_pricelist.id),
                         ('product_id', '=', variant.id)], limit=1)
                    rec.ks_shopify_cp_pricelist = compare_price_list.id

    def ks_update_shopify_regular_price(self):
        """
        Updates the Regular price from the pricelist
        :return: None
        """
        for rec in self:
            rec.ks_shopify_regular_price = (self.env['product.pricelist.item'].search(
                [('pricelist_id', '=', rec.ks_shopify_instance.ks_shopify_regular_pricelist.id),
                 ('product_id', '=', rec.ks_product_product.id)], limit=1).fixed_price) if self.env[
                'product.pricelist.item'].search(
                [('pricelist_id', '=', rec.ks_shopify_instance.ks_shopify_regular_pricelist.id),
                 ('product_id', '=', rec.ks_product_product.id)], limit=1).fixed_price else '0.0'

    def ks_update_shopify_compare_price(self):
        """
        Updates the compare price from the pricelist
        :return: None
        """
        for rec in self:
            rec.ks_shopify_compare_price = (self.env['product.pricelist.item'].search(
                [('pricelist_id', '=', rec.ks_shopify_instance.ks_shopify_compare_pricelist.id),
                 ('product_id', '=', rec.ks_product_product.id)], limit=1).fixed_price) if self.env[
                'product.pricelist.item'].search(
                [('pricelist_id', '=', rec.ks_shopify_instance.ks_shopify_compare_pricelist.id),
                 ('product_id', '=', rec.ks_product_product.id)], limit=1).fixed_price else '0.0'

    def open_regular_pricelist_rules_data(self):
        """
        :return: The tree view for the regular pricelist item
        """
        self.ensure_one()
        if self.ks_shopify_product_type == 'simple':
            domain = [('product_id', '=',
                       self.ks_shopify_product_template.product_variant_id.id if self.ks_shopify_product_template.product_variant_id.id else 0),
                      ('currency_id', '=', self.ks_shopify_instance.ks_shopify_currency.id),
                      ('pricelist_id', '=', self.ks_shopify_instance.ks_shopify_regular_pricelist.id)
                      ]
            return {
                'name': _('Price Rules'),
                'view_mode': 'form',
                'views': [(self.env.ref('product.product_pricelist_item_tree_view_from_product').id, 'tree'),
                          (False, 'form')],
                'res_model': 'product.pricelist.item',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'domain': domain,
            }

    def action_show_variants(self):
        action = {
            'domain': [('id', 'in', self.ks_shopify_variant_ids.ids)],
            'name': 'Shopify Variants',
            'view_mode': 'tree,form',
            'res_model': 'ks.shopify.product.variant',
            'type': 'ir.actions.act_window',
        }
        return action

    def open_compare_pricelist_rules_data(self):
        """
        :return: The tree view for the compare pricelist
        """
        self.ensure_one()
        domain = [('product_id', '=',
                   self.ks_shopify_product_template.product_variant_id.id if self.ks_shopify_product_template.product_variant_id.id else 0),
                  ('currency_id', '=', self.ks_shopify_instance.ks_shopify_currency.id),
                  ('pricelist_id', '=', self.ks_shopify_instance.ks_shopify_compare_pricelist.id)
                  ]
        return {
            'name': _('Price Rules'),
            'view_mode': 'tree,form',
            'views': [(self.env.ref('product.product_pricelist_item_tree_view_from_product').id, 'tree'),
                      (False, 'form')],
            'res_model': 'product.pricelist.item',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'domain': domain
        }

    @api.depends('ks_shopify_instance')
    def _ks_calculate_prices(self):
        for rec in self:
            if rec.ks_product_product and rec.ks_shopify_product_type == "simple":
                variant = rec.ks_product_product
                instance = rec.ks_shopify_instance
                if instance:
                    regular_price = self.env['product.pricelist.item'].search(
                        [('pricelist_id', '=', instance.ks_shopify_regular_pricelist.id),
                         ('product_id', '=', variant.id)], limit=1).price
                    rec.ks_shopify_regular_price = regular_price
                    compare_price = self.env['product.pricelist.item'].search(
                        [('pricelist_id', '=', instance.ks_shopify_compare_pricelist.id),
                         ('product_id', '=', variant.id)], limit=1).price
                    rec.ks_shopify_compare_price = compare_price
            else:
                rec.ks_shopify_compare_price = '0'
                rec.ks_shopify_regular_price = '0'

    def compute_sync_status(self):
        if self:
            for rec in self:
                if not rec.ks_date_created and not rec.ks_date_updated:
                    rec.ks_sync_states = False

                elif rec.ks_date_updated >= rec.write_date \
                        or (abs(rec.ks_date_updated - rec.write_date).total_seconds() / 60) < 2:
                    rec.ks_sync_states = True

                else:
                    rec.ks_sync_states = False

    def action_publish(self):
        try:
            for rec in self:
                if rec.ks_shopify_product_id:
                    json_data = {
                        "status": 'publish' if not rec.ks_published else 'draft'
                    }
                    product_data = self.ks_shopify_update_product(rec.ks_shopify_product_id, json_data,
                                                                  rec.ks_shopify_instance)
                    rec.ks_published = not rec.ks_published if product_data else rec.ks_published

        except Exception as e:
            _logger.info(str(e))

    def ks_shopify_get_product(self, product_id, instance):
        try:
            all_json_data = self.env['ks.api.handler'].ks_get_all_data(instance, 'products', product_id)
            return all_json_data
        except ConnectionError:
            raise Exception("Couldn't Connect the Instance at time of Customer Syncing !! Please check the network "
                            "connectivity or the configuration parameters are not correctly set")
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                   status="failed",
                                                                   type="product",
                                                                   instance=instance,
                                                                   operation_flow="shopify_to_odoo",
                                                                   shopify_id=0,
                                                                   layer_model="ks.shopify.product.template",
                                                                   message=str(e))

    def ks_shopify_get_all_products(self, instance, include=False, date_before=False, date_after=False):
        try:
            if include:
                all_retrieved_data = self.env['ks.api.handler'].ks_get_all_data(instance, 'products', include)
            else:
                all_retrieved_data = self.env['ks.api.handler'].ks_get_all_data(instance, 'products')
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                   status="failed",
                                                                   type="product",
                                                                   instance=instance,
                                                                   operation_flow="shopify_to_odoo",
                                                                   shopify_id=0,
                                                                   layer_model="ks.shopify.product.template",
                                                                   message=str(e))
        else:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                   status="success",
                                                                   type="product",
                                                                   operation_flow="shopify_to_odoo",
                                                                   instance=instance,
                                                                   shopify_id=0,
                                                                   layer_model="ks.shopify.product.template",
                                                                   message="Fetch of Products successful")
            return all_retrieved_data

    def ks_shopify_update_product(self, product_tmpl_id, data, instance):
        try:
            product_data = self.env['ks.api.handler'].ks_put_data(instance, 'products', {'product': data},
                                                                  product_tmpl_id)
            if product_data:
                product_data = product_data.get('product')
            return product_data
        except ConnectionError:
            raise Exception("Couldn't Connect the Instance at time of Customer Syncing !! Please check the network "
                            "connectivity or the configuration parameters are not correctly set")
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="update",
                                                                   status="failed",
                                                                   type="product",
                                                                   instance=instance,
                                                                   operation_flow="shopify_to_odoo",
                                                                   shopify_id=0,
                                                                   layer_model="ks.shopify.product.template",
                                                                   message=str(e))

    def ks_shopify_post_product_template(self, data, instance):
        try:
            product_data = self.env['ks.api.handler'].ks_post_data(instance, 'products', {'product': data},
                                                                   )
            if product_data:
                product_data = product_data.get('product')
            return product_data
        except ConnectionError:
            raise Exception("Couldn't Connect the Instance at time of Product Syncing !! Please check the network "
                            "connectivity or the configuration parameters are not correctly set")
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="create",
                                                                   status="failed",
                                                                   type="product",
                                                                   instance=instance,
                                                                   operation_flow="shopify_to_odoo",
                                                                   shopify_id=0,
                                                                   layer_model="ks.shopify.product.template",
                                                                   message=str(e))

    def create_shopify_product(self, instance, product_json_data, odoo_main_product, export_to_shopify=False):
        if odoo_main_product.type == "product":
            layer_product_data = self.ks_map_product_template_data_for_layer(instance, product_json_data,
                                                                             odoo_main_product)
            try:
                shopify_product = self.create(layer_product_data)
                return shopify_product
            except Exception as e:
                _logger.info(str(e))

    def update_shopify_product(self, instance, product_exist, product_json_data, update_to_shopify=False):
        if product_exist.ks_shopify_product_template.type == "product":
            layer_product_data = self.ks_map_product_template_data_for_layer(instance, product_json_data,
                                                                             product_exist.ks_shopify_product_template)
            try:
                product_exist.write(layer_product_data)
                return product_exist
            except Exception as e:
                _logger.info(str(e))

    def ks_auto_import_shopify_product(self, cron_id=False):
        try:
            if not cron_id:
                if self._context.get('params'):
                    cron_id = self.env["ir.cron"].browse(self._context.get('params').get('id'))
            else:
                cron_id = self.env["ir.cron"].browse(cron_id)
            instance_id = cron_id.ks_shopify_instance
            if instance_id and instance_id.ks_instance_state == 'active':
                # order_status = ','.join(instance_id.ks_order_status.mapped('status'))
                product_json_records = self.ks_shopify_get_all_products(
                    instance=instance_id)
                for product_data in product_json_records:
                    self.ks_manage_shopify_product_template_import(instance_id, product_data)
        except Exception as e:
            _logger.info(str(e))

    def ks_action_shopify_import_product(self):
        if len(self) > 1:
            try:
                records = self.filtered(lambda e: e.ks_shopify_instance and e.ks_shopify_product_id)
                if len(records):
                    for dat in records:
                        json_data = self.ks_shopify_get_product(dat.ks_shopify_product_id, dat.ks_shopify_instance)
                        if json_data[0]:
                            self.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(data=json_data,
                                                                                                instance=dat.ks_shopify_instance)
                    return self.env['ks.message.wizard'].ks_pop_up_message("success",
                                                                           '''Products Records enqueued in Queue 
                                                                           Please refer Queue and logs for further details
                                                                           ''')

            except Exception as e:
                raise e

        else:
            try:
                self.ensure_one()
                if self.ks_shopify_product_id and self.ks_shopify_instance:
                    json_data = self.ks_shopify_get_product(self.ks_shopify_product_id, self.ks_shopify_instance)
                    if json_data:
                        for rec in json_data:
                            product = self.ks_manage_shopify_product_template_import(self.ks_shopify_instance, rec)

            except Exception as e:
                raise e

    def ks_action_shopify_export_product(self, product_config=False):
        if len(self) > 1:
            try:
                records = self.filtered(lambda e: e.ks_shopify_instance)
                if len(records):
                    self.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(records=records,
                                                                                        product_config=product_config)
                    return self.env['ks.message.wizard'].ks_pop_up_message("success",
                                                                           '''Product Records enqueued in Queue 
                                                                              Please refer Queue and logs for further details
                                                                              ''')
            except Exception as e:
                _logger.info(str(e))

        else:
            try:
                self.ensure_one()
                self.ks_manage_shopify_product_template_export(self.ks_shopify_instance, product_config=product_config)

            except Exception as e:
                _logger.info(str(e))

    def ks_manage_variant_images(self, odoo_product, instance, shopify_json):
        """
        :param odoo_product: product.template()
        :param shopify_json: Shopify json data
        :return:
        """
        try:
            if odoo_product and shopify_json:
                image_json_data = shopify_json.get("images", [])
                if image_json_data:
                    main_image_url = image_json_data[0]['src']
                    if main_image_url:
                        image = self.env['ks.common.product.images'].get_image_from_url(main_image_url)
                        odoo_product.write({'image_1920': image})
                variant_ids = odoo_product.product_variant_ids
                shopify_variants = shopify_json.get("variations", "")
                if shopify_variants:
                    for index, id in enumerate(shopify_variants):
                        shopify_variant = self.ks_shopify_get_product(id, instance)
                        if shopify_variant.get("images"):
                            image = shopify_variant.get('images')[0]['src']
                            if image:
                                bin_image = self.env['ks.common.product.images'].get_image_from_url(image)
                                variant_ids[index].write({"image_1920": bin_image})
        except Exception as e:
            _logger.info(str(e))

    def ks_manage_shopify_product_template_import(self, instance, product_json_data, queue_record=False,
                                                  odoo_main_product=False):
        """
        :param instance: Shopify Instance ks.shopify.connector.instance()
        :param product_json_data: json data for product template
        :param queue_record: queue handler
        :return: managed ks.shopify.product.template()
        """
        try:
            product_exist = self.env['ks.shopify.product.template'].search(
                [('ks_shopify_instance', '=', instance.id),
                 ('ks_shopify_product_id', '=', product_json_data.get("id"))])
            product_type = product_json_data.get('variants')[0].get('title') == 'Default Title'
            if product_type:
                if product_exist:
                    try:
                        main_product_data = self.ks_map_product_template_data_for_odoo(product_json_data, instance)
                        if product_exist.ks_shopify_product_template and main_product_data:
                            product_exist.ks_shopify_product_template.write(main_product_data)
                        if instance.ks_sync_price:
                            product_exist.ks_shopify_product_template.product_variant_id.ks_manage_shopify_price_to_import(
                                instance,
                                product_json_data.get(
                                    'variants')[
                                    0].get(
                                    'price'),
                                product_json_data.get(
                                    'variants')[
                                    0].get(
                                    'compare_at_price'))
                        self.update_shopify_product(instance, product_exist, product_json_data)
                        self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(product_json_data,
                                                                                                 product_exist,
                                                                                                 "ks_shopify_product_id")
                        if instance.ks_sync_images:
                            self.env['ks.shopify.product.images'].ks_shopify_update_images_for_odoo(
                                product_json_data.get("images"),
                                product_json_data.get("image"),
                                product=product_exist.id)
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                               ks_model='product.template',
                                                                               ks_layer_model='ks.shopify.product.template',
                                                                               ks_message="Product import update success",
                                                                               ks_status="success",
                                                                               ks_type="product",
                                                                               ks_record_id=product_exist.id,
                                                                               ks_operation_flow="shopify_to_odoo",
                                                                               ks_shopify_id=product_json_data.get(
                                                                                   "id", 0),
                                                                               ks_shopify_instance=instance)
                        return product_exist
                    except Exception as e:
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                               ks_model='product.template',
                                                                               ks_layer_model='ks.shopify.product.template',
                                                                               ks_message=str(e),
                                                                               ks_status="failed",
                                                                               ks_type="product",
                                                                               ks_record_id=0,
                                                                               ks_operation_flow="shopify_to_odoo",
                                                                               ks_shopify_id=product_json_data.get(
                                                                                   "id", 0),
                                                                               ks_shopify_instance=instance)

                else:
                    try:
                        if not odoo_main_product:
                            main_product_data = self.ks_map_product_template_data_for_odoo(product_json_data, instance)
                            main_product_data.update({
                                "create": True
                            })
                            if main_product_data.get('barcode') and self.env['product.template'].search_count(
                                    [('barcode', '=', main_product_data.get('barcode'))]):
                                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                                       ks_model='product.template',
                                                                                       ks_layer_model='ks.shopify.product.template',
                                                                                       ks_message='Duplicate Barcode Exists',
                                                                                       ks_status="failed",
                                                                                       ks_type="product",
                                                                                       ks_record_id=0,
                                                                                       ks_operation_flow="shopify_to_odoo",
                                                                                       ks_shopify_id=product_json_data.get(
                                                                                           "id", 0),
                                                                                       ks_shopify_instance=instance)
                                return False
                            odoo_main_product = self.env['product.template'].ks_create_product_template(
                                main_product_data)
                        else:
                            main_product_data = self.ks_map_product_template_data_for_odoo(product_json_data, instance,
                                                                                           odoo_main_product)
                            odoo_main_product.write(main_product_data)
                        shopify_layer_product = self.create_shopify_product(instance, product_json_data,
                                                                            odoo_main_product)
                        if instance.ks_sync_price:
                            shopify_layer_product.ks_shopify_product_template.product_variant_id.ks_manage_shopify_price_to_import(
                                instance,
                                product_json_data.get(
                                    'variants')[
                                    0].get(
                                    'price'),
                                product_json_data.get(
                                    'variants')[
                                    0].get(
                                    'compare_at_price'))
                        self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(product_json_data,
                                                                                                 shopify_layer_product,
                                                                                                 "ks_shopify_product_id")
                        if instance.ks_sync_images:
                            self.env['ks.shopify.product.images'].ks_shopify_update_images_for_odoo(
                                product_json_data.get("images"),
                                product_json_data.get("image"),
                                product=shopify_layer_product.id)

                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                               ks_model='product.template',
                                                                               ks_layer_model='ks.shopify.product.template',
                                                                               ks_message="Product import create success",
                                                                               ks_status="success",
                                                                               ks_type="product",
                                                                               ks_record_id=shopify_layer_product.id,
                                                                               ks_operation_flow="shopify_to_odoo",
                                                                               ks_shopify_id=product_json_data.get(
                                                                                   "id", 0),
                                                                               ks_shopify_instance=instance)
                        return shopify_layer_product

                    except Exception as e:
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                               ks_model='product.template',
                                                                               ks_layer_model='ks.shopify.product.template',
                                                                               ks_message=str(e),
                                                                               ks_status="failed",
                                                                               ks_type="product",
                                                                               ks_record_id=0,
                                                                               ks_operation_flow="shopify_to_odoo",
                                                                               ks_shopify_id=product_json_data.get(
                                                                                   "id", 0),
                                                                               ks_shopify_instance=instance)

                        if queue_record:
                            queue_record.ks_update_failed_state()

            else:
                # Handle variable product import here
                if product_exist:
                    # Run Update of variable product here
                    try:
                        main_product_data = self.ks_map_product_template_data_for_odoo(product_json_data, instance,
                                                                                       product_exist.ks_shopify_product_template)
                        if product_exist.ks_shopify_product_template and main_product_data:
                            product_exist.ks_shopify_product_template.write(main_product_data)
                        self.update_shopify_product(instance, product_exist, product_json_data)
                        self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(product_json_data,
                                                                                                 product_exist,
                                                                                                 "ks_shopify_product_id")
                        layer_variations = self.env['ks.shopify.product.variant'].ks_shopify_manage_variations_import(
                            instance,
                            product_exist.ks_shopify_product_template,
                            product_exist,
                            product_json_data)
                        if instance.ks_sync_images:
                            self.env['ks.shopify.product.images'].ks_shopify_update_images_for_odoo(
                                product_json_data.get("images"), product_json_data.get("image"),
                                product=product_exist.id)
                            self.env['ks.shopify.product.images'].ks_manage_shopify_variant_images_for_odoo(
                                product_json_data, instance,
                                product_exist)
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                               ks_model='product.template',
                                                                               ks_layer_model='ks.shopify.product.template',
                                                                               ks_message="Product import update success",
                                                                               ks_status="success",
                                                                               ks_type="product",
                                                                               ks_record_id=product_exist.id,
                                                                               ks_operation_flow="shopify_to_odoo",
                                                                               ks_shopify_id=product_json_data.get(
                                                                                   "id", 0),
                                                                               ks_shopify_instance=instance)

                        return product_exist

                    except Exception as e:
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                               ks_model='product.template',
                                                                               ks_layer_model='ks.shopify.product.template',
                                                                               ks_message=str(e),
                                                                               ks_status="failed", ks_type="product",
                                                                               ks_record_id=0,
                                                                               ks_operation_flow="shopify_to_odoo",
                                                                               ks_shopify_id=product_json_data.get(
                                                                                   "id", 0),
                                                                               ks_shopify_instance=instance)

                        if queue_record:
                            queue_record.ks_update_failed_state()

                else:
                    # Run Create of variable product here
                    try:
                        if not odoo_main_product:
                            main_product_data = self.ks_map_product_template_data_for_odoo(product_json_data, instance)
                            main_product_data.update({
                                "create": True
                            })
                            if main_product_data.get('barcode') and self.env['product.template'].search_count(
                                    [('barcode', '=', main_product_data.get('barcode'))]):
                                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                                       ks_model='product.template',
                                                                                       ks_layer_model='ks.shopify.product.template',
                                                                                       ks_message='Duplicate Barcode Exists',
                                                                                       ks_status="failed",
                                                                                       ks_type="product",
                                                                                       ks_record_id=0,
                                                                                       ks_operation_flow="shopify_to_odoo",
                                                                                       ks_shopify_id=product_json_data.get(
                                                                                           "id", 0),
                                                                                       ks_shopify_instance=instance)
                                return False
                            odoo_main_product = self.env['product.template'].ks_create_product_template(
                                main_product_data)
                        else:
                            main_product_data = self.ks_map_product_template_data_for_odoo(product_json_data, instance,
                                                                                           odoo_main_product)
                            odoo_main_product.write(main_product_data)
                        shopify_layer_product = self.create_shopify_product(instance, product_json_data,
                                                                            odoo_main_product)
                        self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(product_json_data,
                                                                                                 shopify_layer_product,
                                                                                                 "ks_shopify_product_id")
                        layer_variations = self.env['ks.shopify.product.variant'].ks_shopify_manage_variations_import(
                            instance,
                            odoo_main_product,
                            shopify_layer_product,
                            product_json_data)
                        if instance.ks_sync_images:
                            self.env['ks.shopify.product.images'].ks_shopify_update_images_for_odoo(
                                product_json_data.get("images"), product_json_data.get("image"),
                                product=shopify_layer_product.id)

                            self.env['ks.shopify.product.images'].ks_manage_shopify_variant_images_for_odoo(
                                product_json_data, instance,
                                shopify_layer_product)
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                               ks_model='product.template',
                                                                               ks_layer_model='ks.shopify.product.template',
                                                                               ks_message="Product import create success",
                                                                               ks_status="success",
                                                                               ks_type="product",
                                                                               ks_record_id=shopify_layer_product.id,
                                                                               ks_operation_flow="shopify_to_odoo",
                                                                               ks_shopify_id=product_json_data.get(
                                                                                   "id", 0),
                                                                               ks_shopify_instance=instance)

                        return shopify_layer_product

                    except Exception as e:
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                               ks_model='product.template',
                                                                               ks_layer_model='ks.shopify.product.template',
                                                                               ks_message=str(e),
                                                                               ks_status="failed",
                                                                               ks_type="product",
                                                                               ks_record_id=0,
                                                                               ks_operation_flow="shopify_to_odoo",
                                                                               ks_shopify_id=product_json_data.get(
                                                                                   "id", 0),
                                                                               ks_shopify_instance=instance)

                        if queue_record:
                            queue_record.ks_update_failed_state()

        except Exception as e:
            if queue_record:
                queue_record.ks_update_failed_state()
            raise e

    def ks_manage_shopify_product_template_export(self, instance, queue_record=False, product_config=False):
        """
        :param instance: ks.shopify.connector.instance()
        :param queue_record: Boolean trigger for queue job
        :return: json response after updation or creation
        """
        if product_config:
            product_config = product_config[0]
        try:
            product_exported = self.ks_shopify_product_id
            product_template = self.ks_shopify_product_template
            if product_exported:
                try:
                    data = self.ks_prepare_product_data_to_export(instance, product_template,
                                                                  self.ks_shopify_product_type,
                                                                  product_config)
                    product_data_response = self.ks_shopify_update_product(self.ks_shopify_product_id, data, instance)
                    if product_data_response:
                        self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(product_data_response,
                                                                                                 self,
                                                                                                 'ks_shopify_product_id')
                        self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(product_data_response,
                                                                                                 self,
                                                                                                 'ks_shopify_product_variant_id')
                        self.env['ks.shopify.connector.instance'].ks_shopify_update_variants_response(
                            product_data_response,
                            self.ks_shopify_variant_ids, )
                        if product_config and product_config.get('ks_update_image'):
                            all_images = self.ks_get_all_images()
                            for rec in all_images:
                                data = rec.ks_prepare_images_for_shopify()
                                ks_api_data = self.env['ks.api.handler'].ks_post_data(instance, 'images',
                                                                                      {'image': data},
                                                                                      self.ks_shopify_product_id)
                                if ks_api_data:
                                    update_data = {
                                        'ks_shopify_image_id': ks_api_data.get('image').get('id'),
                                        'ks_url': ks_api_data.get('image').get('src'),
                                    }
                                    rec.update(update_data)
                            product_image_response = self.ks_shopify_get_product(self.ks_shopify_product_id,
                                                                                 instance)
                            self.env['ks.shopify.product.images'].ks_shopify_update_images_for_odoo(
                                product_image_response[0].get("images"), product_image_response[0].get("image"),
                                product=self.id)
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                               ks_model='product.template',
                                                                               ks_layer_model='ks.shopify.product.template',
                                                                               ks_message="Product export update success",
                                                                               ks_status="success",
                                                                               ks_type="product",
                                                                               ks_record_id=self.id,
                                                                               ks_operation_flow="odoo_to_shopify",
                                                                               ks_shopify_id=product_data_response.get(
                                                                                   "id", 0),
                                                                               ks_shopify_instance=instance)

                except Exception as e:
                    if queue_record:
                        queue_record.ks_update_failed_state()
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                           ks_model='product.template',
                                                                           ks_layer_model='ks.shopify.product.template',
                                                                           ks_message=str(e),
                                                                           ks_status="failed",
                                                                           ks_type="product",
                                                                           ks_record_id=self.id,
                                                                           ks_operation_flow="odoo_to_shopify",
                                                                           ks_shopify_id=0,
                                                                           ks_shopify_instance=instance)

            else:
                ##Use create command here
                try:
                    data = self.ks_prepare_product_data_to_export(instance, product_template,
                                                                  self.ks_shopify_product_type,
                                                                  product_config)
                    product_data_response = self.ks_shopify_post_product_template(data, instance)
                    if product_data_response:
                        self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(product_data_response,
                                                                                                 self,
                                                                                                 'ks_shopify_product_id', )
                        self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(product_data_response,
                                                                                                 self,
                                                                                                 'ks_shopify_product_variant_id', )
                        if self.ks_shopify_variant_ids:
                            self.env['ks.shopify.connector.instance'].ks_shopify_update_variants_response(
                                product_data_response,
                                self.ks_shopify_variant_ids, )
                    else:
                        if queue_record:
                            queue_record.ks_update_failed_state()
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                               ks_model='product.template',
                                                                               ks_layer_model='ks.shopify.product.template',
                                                                               ks_message="Product Export to shopify failed",
                                                                               ks_status="failed",
                                                                               ks_type="product",
                                                                               ks_record_id=self.id,
                                                                               ks_operation_flow="odoo_to_shopify",
                                                                               ks_shopify_id=0,
                                                                               ks_shopify_instance=instance)
                    if product_config and product_config.get('ks_update_image'):
                        all_images = self.ks_get_all_images()
                        for rec in all_images:
                            data = rec.ks_prepare_images_for_shopify()
                            ks_api_data = self.env['ks.api.handler'].ks_post_data(instance, 'images', {'image': data},
                                                                                  self.ks_shopify_product_id)
                            update_data = {
                                'ks_shopify_image_id': ks_api_data.get('image').get('id'),
                                'ks_url': ks_api_data.get('image').get('src'),
                            }
                            rec.update(update_data)
                        product_image_response = self.ks_shopify_get_product(self.ks_shopify_product_id,
                                                                             instance)
                        self.env['ks.shopify.product.images'].ks_shopify_update_images_for_odoo(
                            product_image_response[0].get("images"), product_image_response[0].get("image"),
                            product=self.id)
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                           ks_model='product.template',
                                                                           ks_layer_model='ks.shopify.product.template',
                                                                           ks_message="Product export create success",
                                                                           ks_status="success",
                                                                           ks_type="product",
                                                                           ks_record_id=self.id,
                                                                           ks_operation_flow="odoo_to_shopify",
                                                                           ks_shopify_id=product_data_response.get(
                                                                               "id", 0),
                                                                           ks_shopify_instance=instance)

                except Exception as e:
                    if queue_record:
                        queue_record.ks_update_failed_state()
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                           ks_model='product.template',
                                                                           ks_layer_model='ks.shopify.product.template',
                                                                           ks_message=str(e),
                                                                           ks_status="failed",
                                                                           ks_type="product",
                                                                           ks_record_id=self.id,
                                                                           ks_operation_flow="odoo_to_shopify",
                                                                           ks_shopify_id=0,
                                                                           ks_shopify_instance=instance)

        except Exception as e:
            if queue_record:
                queue_record.ks_update_failed_state()

            _logger.info(str(e))

    def ks_update_product_status_to_shopify(self, instance, queue_record=False, domain=False):
        """
        :param instance: ks.shopify.connector.instance()
        :param queue_record: Boolean trigger for queue job
        :return: json response after updation or creation
        """
        try:
            data = {
                'id': self.ks_shopify_product_id,
                'status': domain,
            }
            product_data_response = self.ks_shopify_update_product(self.ks_shopify_product_id, data, instance)
            if product_data_response:
                self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(product_data_response,
                                                                                         self,
                                                                                         'ks_shopify_product_id')
                self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(product_data_response,
                                                                                         self,
                                                                                         'ks_shopify_product_variant_id')
                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                       ks_model='product.template',
                                                                       ks_layer_model='ks.shopify.product.template',
                                                                       ks_message="Product Status export update success",
                                                                       ks_status="success",
                                                                       ks_type="product_status",
                                                                       ks_record_id=self.id,
                                                                       ks_operation_flow="odoo_to_shopify",
                                                                       ks_shopify_id=product_data_response.get(
                                                                           "id", 0),
                                                                       ks_shopify_instance=instance)

        except Exception as e:
            if queue_record:
                queue_record.ks_update_failed_state()
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                   ks_model='product.template',
                                                                   ks_layer_model='ks.shopify.product.template',
                                                                   ks_message=str(e),
                                                                   ks_status="failed",
                                                                   ks_type="product_status",
                                                                   ks_record_id=self.id,
                                                                   ks_operation_flow="odoo_to_shopify",
                                                                   ks_shopify_id=0,
                                                                   ks_shopify_instance=instance)

    def ks_get_all_images(self):
        ks_all_images = []
        for rec in self.ks_shopify_image_ids:
            if not rec.ks_shopify_image_id:
                ks_all_images.append(rec)
        for rec in self.ks_shopify_variant_ids:
            for image in rec.ks_shopify_image_ids:
                if not image.ks_shopify_image_id and image not in ks_all_images:
                    ks_all_images.append(image)
        return ks_all_images

    def ks_prepare_product_data_to_export(self, instance, product_template, product_type=False, product_config=False,
                                          variant=False):
        """
        :param instance: ks.shopify.connector.instance()
        :param product_template: product.template()
        :param product_type: simple / variable (optional)
        :return: shopify compatible json data
        """
        variants = {}
        data = {
            "id": int(self.ks_shopify_product_id),
            "title": product_template.name,
            "product_type": self.ks_shopify_type_product or "",
            "body_html": self.ks_shopify_description or '',
            "vendor": self.ks_shopify_vendor or '',
            "tags": self.ks_shopify_tags or ""
        }

        if product_config and product_config.get("ks_update_website_status"):
            data.update({
                "status": "active" if product_config.get("ks_update_website_status") == 'published' else "draft"
            })
        all_images = []
        if self.ks_shopify_product_type == "simple":
            if self.ks_shopify_product_template.product_variant_id:
                variant = self.ks_shopify_product_template.product_variant_id
                stock_qty = self.env['product.product'].ks_get_stock_quantity(self.ks_shopify_instance.ks_warehouse,
                                                                              variant,
                                                                              self.ks_shopify_instance.ks_stock_field_type.name)
                compare_price = self.ks_shopify_instance.ks_shopify_compare_pricelist.ks_get_product_price(variant)
                if product_config["ks_update_price"]:
                    variants.update({
                        "price": str(product_config['ks_price']),
                        "compare_at_price": str(product_config['ks_compare_at_price'])
                    })
                if product_config["ks_inventory_policy"]:
                    variants.update({
                        'inventory_policy': product_config["ks_inventory_policy"],
                    })
                else:
                    variants.update({
                        'inventory_policy': self.ks_inventory_policy,
                    })
                if product_config['ks_update_stock']:
                    variants.update({
                        "manage_stock": True,
                        "inventory_quantity": int(stock_qty),
                        "old_inventory_quantity": int(stock_qty),
                        "inventory_management": "shopify",
                        # "stock_status": "instock" if stock_qty > 0 else "outofstock",
                        "sku": variant.default_code if variant.default_code else '',
                        # "barcode": product_config.get('ks_barcode') if product_config else '',
                        "barcode": self.ks_shopify_product_template.barcode or '' if self.ks_shopify_product_template else '',
                        "weight": str(product_template.weight) or "",
                    })
                else:
                    variants.update({
                        "inventory_management": "shopify",
                        "manage_stock": True,
                        "weight": str(product_template.weight) or "",
                        "id": int(self.ks_shopify_product_variant_id),
                        "product_id": int(self.ks_shopify_product_id),
                        # "price": int(
                        #     self.ks_shopify_instance.ks_shopify_regular_pricelist.ks_get_product_price(variant)),
                        # "compare_at_price": str(compare_price) if compare_price else '',
                        "sku": variant.default_code if variant.default_code else '',
                        "barcode": self.ks_shopify_product_template.barcode or '' if self.ks_shopify_product_template else '',
                        # "inventory_quantity": int(stock_qty),
                    })
                data.update({
                    'variants': [variants]
                })
        else:
            data.update({
                # "manage_stock": False,
                # "price": '0',
                # "compare_at_price": '0',
                "options": self.ks_manage_product_attributes(self.ks_shopify_product_template)
            })
            variants_data = []
            for product_var in self.ks_shopify_variant_ids.filtered(
                    lambda x: x.ks_active == True):
                variant_data = product_var.ks_prepare_product_variant_to_export(product_config)
                variants_data.append(variant_data)
            data.update({
                'variants': variants_data,
            })
        return data

    def ks_manage_product_attributes(self, product_template):
        attribute_data = []
        attribute_line_ids = product_template.attribute_line_ids
        if attribute_line_ids:
            for line in attribute_line_ids:
                attribute_layer_exist = self.env['ks.shopify.product.attribute'].check_if_already_prepared(
                    self.ks_shopify_instance,
                    line.attribute_id)
                if attribute_layer_exist:
                    if not attribute_layer_exist.ks_shopify_attribute_id:
                        attribute_layer_exist.create_shopify_record(self.ks_shopify_instance, line.attribute_id)
                    else:
                        attribute_layer_exist.update_shopify_record(self.ks_shopify_instance, line.attribute_id)
                attribute_layer_exist = self.env['ks.shopify.product.attribute'].check_if_already_prepared(
                    self.ks_shopify_instance,
                    line.attribute_id)
                attr_val = []
                for value in line.value_ids:
                    attr_val.append(value.name)
                if attribute_layer_exist:
                    # attribute_layer_exist.ks_manage_attribute_export()
                    data = {
                        "id": attribute_layer_exist.ks_shopify_attribute_id,
                        "product_id": int(product_template.ks_shopify_product_template.filtered(
                            lambda x: x.ks_shopify_instance == self.ks_shopify_instance)[0].ks_shopify_product_id) or 0,
                        "name": attribute_layer_exist.ks_name,
                        "values": attr_val
                    }

                else:
                    data = {
                        "id": 0,
                        "product_id": int(product_template.ks_shopify_product_template.filtered(
                            lambda x: x.ks_shopify_instance == self.ks_shopify_instance)[0].ks_shopify_product_id) or 0,
                        "name": line.attribute_id.name,
                        "values": attr_val,
                    }

                if data:
                    attribute_data.append(data)
        return attribute_data

    def check_if_already_prepared(self, instance, odoo_product):
        """
        Checks if record is already prepared to be imported on layer model
        :param instance: shopify instance
        :param odoo_product: product.template()
        :return: product_category
        """
        odoo_product_exists = self.search([('ks_shopify_instance', '=', instance.id),
                                           ('ks_shopify_product_template', '=', odoo_product.id)], limit=1)
        if odoo_product_exists:
            return odoo_product_exists
        else:
            return False

    def create_shopify_record(self, instance, odoo_product, export_to_shopify=False, queue_record=False,
                              generic_wizard=False):
        """
        :param instance: ks.shopify.connector.instance()
        :param odoo_product: product.template()
        :param export_to_shopify: optional, If want to directly export it or not
        :param queue_record: Boolean trigger for queue record
        :return: ks.shopify.product.template()
        """
        try:
            layer_product = None
            product_exists = self.search([('ks_shopify_instance', '=', instance.id),
                                          ('ks_shopify_product_template', '=', odoo_product.id)])
            if not product_exists:
                data = self.ks_map_prepare_data_for_layer(instance, odoo_product, generic_wizard)
                if odoo_product.image_1920:
                    image_data = {"sequence": 0,
                                  "ks_image": odoo_product.image_1920 or False,
                                  "ks_name": odoo_product.name,
                                  "ks_template_id": odoo_product.id}
                    image_exist = self.env["ks.common.product.images"].search(
                        [('ks_image', '=', odoo_product.image_1920), ('ks_name', '=', odoo_product.name),
                         ('ks_template_id', '=', odoo_product.id)], limit=1)
                    if image_exist:
                        image_id = image_exist
                    else:
                        image_id = self.env["ks.common.product.images"].with_context(main_image=True).create(image_data)
                    odoo_product.profile_image_id = image_id.id
                layer_product = self.create(data)
                layer_product.ks_shopify_regular_price = data.get('ks_shopify_regular_price') or 0.0
                layer_product.ks_shopify_compare_price = data.get('ks_shopify_compare_price') or 0.0
                if layer_product.ks_shopify_product_type == 'variable':
                    self.env['ks.shopify.product.variant'].ks_manage_shopify_prepare_variant(odoo_product,
                                                                                             layer_product,
                                                                                             instance,
                                                                                             operation='create',
                                                                                             generic_wizard=generic_wizard)
                else:
                    self.env['product.product'].ks_shopify_manage_price_to_export(
                        layer_product.ks_shopify_product_template.product_variant_id,
                        instance)
                self.env['product.template'].ks_manage_template_images(layer_product, odoo_product)
                if export_to_shopify:
                    try:
                        layer_product.ks_manage_shopify_product_template_export(instance=instance)
                    except Exception as e:
                        _logger.info(str(e))
            self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_create",
                                                                       status="success",
                                                                       type="product",
                                                                       instance=instance,
                                                                       odoo_model="product.template",
                                                                       layer_model="ks.shopify.product.template",
                                                                       id=odoo_product.id,
                                                                       message="Layer preparation Success")
            return layer_product
        except Exception as e:
            if queue_record:
                queue_record.ks_update_failed_state()

            self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_create",
                                                                       status="failed",
                                                                       type="product",
                                                                       instance=instance,
                                                                       odoo_model="product.template",
                                                                       layer_model="ks.shopify.product.template",
                                                                       id=odoo_product.id,
                                                                       message=str(e))

    def update_shopify_record(self, instance, odoo_product, export_to_shopify=False, queue_record=False,
                              generic_wizard=False):
        """
            :param instance: ks.shopify.connector.instance()
            :param odoo_product: product.template()
            :param export_to_shopify: optional, If want to directly export it or not
            :param queue_record: Boolean trigger for queue record
            :return: ks.shopify.product.template()
        """
        try:
            product_exists = self.search([('ks_shopify_instance', '=', instance.id),
                                          ('ks_shopify_product_template', '=', odoo_product.id)])
            if product_exists:
                data = self.ks_map_prepare_data_for_layer(instance, odoo_product, generic_wizard)
                product_exists.write(data)
                if product_exists.ks_shopify_product_type == 'variable':
                    self.env['ks.shopify.product.variant'].ks_manage_shopify_prepare_variant(odoo_product,
                                                                                             product_exists,
                                                                                             instance,
                                                                                             operation='update',
                                                                                             generic_wizard=generic_wizard)
                else:
                    self.env['product.product'].ks_shopify_manage_price_to_export(
                        product_exists.ks_shopify_product_template.product_variant_id,
                        instance)
                self.env['product.template'].ks_manage_template_images(product_exists, odoo_product)
                if export_to_shopify:
                    try:
                        product_exists.ks_manage_shopify_product_template_export(instance=instance,
                                                                                 product_config=generic_wizard)
                    except Exception as e:
                        _logger.info(str(e))
            self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_update",
                                                                       status="success",
                                                                       type="product",
                                                                       instance=instance,
                                                                       odoo_model="product.template",
                                                                       layer_model="ks.shopify.product.template",
                                                                       id=odoo_product.id,
                                                                       message="Layer preparation Success")
            return product_exists

        except Exception as e:
            if queue_record:
                queue_record.ks_update_failed_state()

            self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_update",
                                                                       status="failed",
                                                                       type="product",
                                                                       instance=instance,
                                                                       odoo_model="product.template",
                                                                       layer_model="ks.shopify.product.template",
                                                                       id=odoo_product.id,
                                                                       message=str(e))

    def ks_map_prepare_data_for_layer(self, instance, odoo_product, generic_wizard=False):
        """
        :param instance: ks.shopify.connector.instance()
        :param odoo_product: product.template
        :return: layer compatible json data
        """

        data = {
            "ks_shopify_product_template": odoo_product.id,
            "ks_shopify_instance": instance.id,
            "ks_shopify_product_type": 'simple' if not odoo_product.attribute_line_ids else 'variable'
        }
        if generic_wizard:
            if generic_wizard.ks_shopify_product_template:
                if not odoo_product.ks_shopify_product_template.filtered(
                        lambda x: x.ks_shopify_instance == instance).ks_shopify_rp_pricelist.search(
                    [("product_tmpl_id", '=', odoo_product.id),
                     ("product_id", '=', odoo_product.product_variant_id.id),
                     ("pricelist_id", '=', instance.ks_shopify_regular_pricelist.id)], limit=1):
                    ks_regular_pricelist_items = instance.ks_shopify_regular_pricelist.item_ids.create({
                        "product_tmpl_id": odoo_product.id,
                        "product_id": odoo_product.product_variant_id.id,
                        "pricelist_id": instance.ks_shopify_regular_pricelist.id,
                        "fixed_price": generic_wizard.ks_price,
                        "name": odoo_product.name,
                    })
                else:
                    ks_regular_pricelist_items = odoo_product.ks_shopify_product_template.filtered(
                        lambda x: x.ks_shopify_instance == instance).ks_shopify_rp_pricelist.search(
                        [("product_tmpl_id", '=', odoo_product.id),
                         ("product_id", '=', odoo_product.product_variant_id.id),
                         ("pricelist_id", '=', instance.ks_shopify_regular_pricelist.id)], limit=1)
                    ks_regular_pricelist_items.update({"fixed_price": generic_wizard.ks_price
                                                       })
                data.update({'ks_shopify_rp_pricelist': ks_regular_pricelist_items.id})
                if not odoo_product.ks_shopify_product_template.filtered(
                        lambda x: x.ks_shopify_instance == instance).ks_shopify_rp_pricelist.search(
                    [("product_tmpl_id", '=', odoo_product.id),
                     ("product_id", '=', odoo_product.product_variant_id.id),
                     ("pricelist_id", '=', instance.ks_shopify_compare_pricelist.id)], limit=1):
                    ks_compare_pricelist_items = instance.ks_shopify_compare_pricelist.item_ids.create({
                        "product_tmpl_id": odoo_product.id,
                        "product_id": odoo_product.product_variant_id.id,
                        "pricelist_id": instance.ks_shopify_compare_pricelist.id,
                        "fixed_price": generic_wizard.ks_compare_at_price,
                        "name": odoo_product.name,
                    })
                else:
                    ks_compare_pricelist_items = odoo_product.ks_shopify_product_template.filtered(
                        lambda x: x.ks_shopify_instance == instance).ks_shopify_rp_pricelist.search(
                        [("product_tmpl_id", '=', odoo_product.id),
                         ("product_id", '=', odoo_product.product_variant_id.id),
                         ("pricelist_id", '=', instance.ks_shopify_compare_pricelist.id)], limit=1)
                    ks_compare_pricelist_items.update(
                        {"fixed_price": generic_wizard.ks_compare_at_price
                         })
                data.update({'ks_shopify_cp_pricelist': ks_compare_pricelist_items.id})
            inventory_policy = generic_wizard.ks_inventory_policy if generic_wizard.ks_push_additional_data else 'deny' if not odoo_product.ks_shopify_product_template.ks_inventory_policy else odoo_product.ks_shopify_product_template.ks_inventory_policy
            # odoo_product.ks_shopify_product_template.ks_shopify_cp_pricelist = ks_compare_pricelist_items.id
            data.update({
                'ks_shopify_description': generic_wizard.ks_shopify_description if generic_wizard.ks_shopify_description != '<p><br></p>' else odoo_product.ks_shopify_product_template.filtered(
                    lambda x: x.ks_shopify_instance == instance).ks_shopify_description,
                'ks_shopify_tags': generic_wizard.ks_shopify_tags if generic_wizard.ks_shopify_tags else odoo_product.ks_shopify_product_template.filtered(
                    lambda x: x.ks_shopify_instance == instance).ks_shopify_tags,
                'ks_shopify_type_product': generic_wizard.ks_shopify_type_product if generic_wizard.ks_shopify_type_product else odoo_product.ks_shopify_product_template.filtered(
                    lambda x: x.ks_shopify_instance == instance).ks_shopify_type_product,
                'ks_shopify_vendor': generic_wizard.ks_shopify_vendor if generic_wizard.ks_shopify_vendor else odoo_product.ks_shopify_product_template.filtered(
                    lambda x: x.ks_shopify_instance == instance).ks_shopify_vendor,
                'ks_barcode': generic_wizard.ks_barcode or odoo_product.ks_shopify_product_template.filtered(
                    lambda x: x.ks_shopify_instance == instance).ks_barcode,
                # 'ks_update_price': generic_wizard.ks_update_price,
                # 'ks_update_stock': generic_wizard.ks_update_stock,
                # 'ks_update_website_status': generic_wizard.ks_update_website_status,
                'ks_published': True if generic_wizard.ks_update_website_status == 'published' else False,
                'ks_inventory_policy': inventory_policy,
                'ks_shopify_regular_price': generic_wizard.ks_price or odoo_product.ks_shopify_product_template.filtered(
                    lambda x: x.ks_shopify_instance == instance).ks_shopify_regular_price,
                'ks_shopify_compare_price': generic_wizard.ks_compare_at_price or odoo_product.ks_shopify_product_template.filtered(
                    lambda x: x.ks_shopify_instance == instance).ks_shopify_compare_price,
            })

        return data

    def ks_map_product_template_data_for_layer(self, instance, product_json_data, odoo_main_product):
        product_type = ""
        if product_json_data.get('options')[0].get('name') == 'Title':
            product_type = "simple"
        else:
            product_type = "variable"
        layer_data = {
            "ks_shopify_product_type": product_type,
            'ks_shopify_product_id': product_json_data.get('id'),
            'ks_shopify_product_variant_id': product_json_data.get('variants')[0].get(
                'id') if product_type == "simple" else False,
            'ks_published': product_json_data.get('status') == 'active',
            'ks_shopify_description': product_json_data.get('body_html') or '',
            "ks_shopify_instance": instance.id,
            "ks_shopify_product_template": odoo_main_product.id,
            "ks_shopify_type_product": product_json_data.get('product_type'),
            "ks_shopify_tags": product_json_data.get('tags'),
            "ks_shopify_vendor": product_json_data.get('vendor'),
            "ks_barcode": product_json_data.get('variants')[0].get('barcode') or False,
            "ks_shopify_inventory_id": product_json_data.get('variants')[0].get('inventory_item_id'),
            "ks_inventory_policy": product_json_data.get('variants')[0].get('inventory_policy'),
            'ks_company_id': instance.ks_company_id.id,
        }
        collections_data = self.env['ks.api.handler'].ks_get_all_data(instance, "collects")
        if collections_data:
            custom_linking_record = []
            shopify_product_id = product_json_data.get('id')
            for data in collections_data:
                if shopify_product_id == data.get("product_id"):
                    collections_id = data.get("collection_id")
                    custom_collection_data = self.env['ks.api.handler'].ks_get_specific_data(instance,
                                                                                             'custom_collections',
                                                                                             collections_id)
                    if custom_collection_data:
                        custom_collection_data = custom_collection_data.get("custom_collection")
                        custom_collection_record = self.env[
                            'ks.shopify.custom.collections'].ks_manage_shopify_collections_import(instance,
                                                                                                  custom_collection_data)
                        custom_linking_record.append(custom_collection_record.id)
            if custom_linking_record:
                layer_data.update({"ks_collections_ids": [(6, 0, custom_linking_record)]})
        return layer_data

    def cleanhtml(self, raw_html):
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', raw_html)
        return cleantext

    def ks_map_product_template_data_for_odoo(self, json_data, instance, main_product=False):
        data = {
            "name": json_data.get('title') or '',
            "company_id": instance.ks_company_id.id,
            "default_code": json_data.get('variants')[0].get('sku') or '',
            "type": "product",
            "weight": json_data.get('variants')[0].get('weight') or '',
            "weight_uom_name": json_data.get('variants')[0].get('weight_unit') or '',
            "barcode": json_data.get('variants')[0].get('barcode') or False,
            "description": self.cleanhtml(json_data.get('body_html')) if json_data.get('body_html') else '',
            "responsible_id": False,
        }
        if json_data.get('options')[0].get('name') != 'Title':
            # Update data with attribute line ids
            attribute_json_data = json_data.get('options') if json_data.get('options') else False
            if attribute_json_data:
                odoo_attributes = self.ks_manage_attributes_import(instance, attribute_json_data, main_product)
                data.update({"attribute_line_ids": odoo_attributes})

        if instance.ks_meta_fields_map:
            meta_data = self.env['ks.shopify.meta.mapping'].get_meta_fields_data(instance=instance, model='products',
                                                                                 ids=json_data.get('id'),
                                                                                 ks_model='product.template')
            data.update(meta_data)
        return data

    def ks_manage_attributes_import(self, instance, attribute_json_data, main_product=False):
        """
        :param instance: ks.shopify.connector.instance()
        :param attribute_json_data: attributes json data from shopify
        :return: odoo ids of attributes
        """
        attribute_line_data = []
        for attr in attribute_json_data:
            # shopify_attr_json = self.env['ks.shopify.product.attribute'].ks_shopify_get_attribute(attr, instance)
            odoo_attribute = self.env['ks.shopify.product.attribute'].ks_manage_attribute_import(instance,
                                                                                                 attr if attr else False)
            if main_product:
                attribute_exist = main_product.attribute_line_ids.search([('attribute_id', '=', odoo_attribute.id),
                                                                          ('product_tmpl_id', '=', main_product.id)],
                                                                         limit=1)
            else:
                attribute_exist = False
            value_ids = []
            if attr.get('values'):
                for att_terms in attr.get('values'):
                    att_value = self.env['product.attribute.value'].ks_manage_attribute_value_in_odoo(att_terms,
                                                                                                      odoo_attribute.id)
                    if att_value:
                        value_ids.append(att_value.id)
            if attribute_exist:
                attribute_line_data.append((1, attribute_exist.id, {
                    'attribute_id': odoo_attribute.id,
                    'product_tmpl_id': main_product.id,
                    'value_ids': [(6, 0, value_ids)]
                }))
            else:
                attribute_line_data.append((0, 0, {'attribute_id': odoo_attribute.id,
                                                   'value_ids': [(6, 0, value_ids)]}))

        return attribute_line_data

    def update_record_data_in_odoo(self):
        pass

    def ks_get_product_data_for_stock_adjustment(self, product_data, instance):
        product_json = []
        for product in product_data:
            shopify_product = self.search([('ks_shopify_product_id', '=', product.get('id')),
                                           ('ks_shopify_instance', '=', instance.id)], limit=1)
            if shopify_product:
                variation_id = product.get('variants')
                if variation_id[0].get('title') != 'Default Title':
                    for each_variation in variation_id:
                        shopify_product_variant = self.env['ks.shopify.product.variant'].search(
                            [('ks_shopify_variant_id', '=', each_variation.get('id')),
                             ('ks_shopify_instance', '=', instance.id)], limit=1)
                        if shopify_product_variant:
                            # shopify_variant_record = self.ks_shopify_get_product(each_variation.get('id'), instance)
                            if each_variation.get('inventory_quantity') != 0:
                                product_json.append({
                                    'product_id': shopify_product_variant.ks_shopify_product_variant.id,
                                    'product_qty': each_variation.get('inventory_quantity'),
                                })
                else:
                    linked_product = shopify_product.ks_shopify_product_template.product_variant_id
                    if product.get('variants')[0].get('inventory_quantity') != 0:
                        product_json.append({
                            'product_id': linked_product.id,
                            'product_qty': product.get('variants')[0].get('inventory_quantity'),
                        })
        return product_json


class KsProductTemplateInherit(models.Model):
    _inherit = "product.template"

    ks_shopify_product_template = fields.One2many('ks.shopify.product.template', 'ks_shopify_product_template')

    def ks_action_shopify_export_product_template_stock(self):
        try:
            for product in self:
                for shopify_product in product.ks_shopify_product_template:
                    if shopify_product.ks_shopify_product_id:
                        for rec in product.product_variant_ids:
                            instance = shopify_product.ks_shopify_instance
                            stock_qty = self.env['product.product'].ks_get_stock_quantity(instance.ks_warehouse,
                                                                                          rec,
                                                                                          instance.ks_stock_field_type.sudo().name)
                            if instance.ks_primary_locations and stock_qty:
                                ks_shopify_product_variant = rec.ks_shopify_product_variant.filtered(
                                    lambda x: x.ks_shopify_instance.id == instance.id)
                                product_data = ks_shopify_product_variant if ks_shopify_product_variant else shopify_product
                                data = {
                                    'available': int(stock_qty),
                                    'location_id': instance.ks_primary_locations,
                                    'inventory_item_id': product_data.ks_shopify_inventory_id,
                                }
                                ks_response = self.env['ks.api.handler'].ks_post_data(instance, 'inventory_levels',
                                                                                      data)
                                if ks_response:
                                    self.env['ks.shopify.logger'].ks_create_prepare_log_params(
                                        operation_performed="export",
                                        status="success",
                                        type="stock",
                                        instance=instance,
                                        odoo_model="product.template",
                                        layer_model="ks.shopify.product.template",
                                        id=product_data,
                                        message="Product Stock export successful")
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="export",
                                                                       status="failed",
                                                                       type="stock",
                                                                       instance=False,
                                                                       odoo_model="product.template",
                                                                       layer_model="ks.shopify.product.template",
                                                                       id=0,
                                                                       message=e)

    @api.model
    def create(self, vals):
        create = vals.get('create') or False
        if vals.get('create'):
            vals.pop('create')
        res = super(KsProductTemplateInherit, self).create(vals)
        return res

    @api.constrains('list_price')
    def ks_update_product_template_price(self):
        for rec in self:
            if rec.ks_shopify_product_template and rec.product_variant_ids == rec.product_variant_id:
                ks_shopify_regular_pricelist = self.env['product.pricelist.item'].search(
                    [('pricelist_id', '=',
                      rec.ks_shopify_product_template.ks_shopify_instance.ks_shopify_regular_pricelist.id),
                     ('product_id', '=', rec.product_variant_id.id)], limit=1)
                if ks_shopify_regular_pricelist:
                    ks_shopify_regular_pricelist.fixed_price = rec.list_price

    def action_shopify_layer_templates(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("ks_shopify.action_ks_shopify_product_template_")
        action['domain'] = [('id', 'in', self.ks_shopify_product_template.ids)]
        return action

    def ks_manage_template_images(self, shopify_product, template):
        if template.ks_image_ids:
            for image in template.ks_image_ids:
                image_id = self.env['ks.shopify.product.images'].ks_odoo_prepare_image_data(image,
                                                                                            template_id=shopify_product.id,
                                                                                            variant_id=False)
                if image.id == template.profile_image_id.id:
                    shopify_product.profile_image = image_id.id

    def ks_push_to_shopify(self):
        if self:
            active_ids = self.ids
        else:
            active_ids = self.env.context.get("active_ids")
        records = active_ids
        generic_id = self.env['ks.generic.configuration'].create({'ks_domain': 'product.template',
                                                                  'ks_shopify_product_template': records,
                                                                  'ks_multi_record': True if len(
                                                                      records) > 1 else False,
                                                                  'ks_id': records,
                                                                  'ks_is_variant': True if (len(self.browse(
                                                                      records).product_variant_ids) > 1 if len(
                                                                      records) < 2 else False) else True
                                                                  })
        context = {'default_ks_domain': 'product.template',
                   'default_ks_shopify_product_template_id': records,
                   'default_ks_multi_record': True if len(records) > 1 else False,
                   'default_ks_data': generic_id.id,
                   'default_ks_is_variant': True if len(self.browse(records).product_variant_ids) > 1 else True
                   }

        return {
            'name': 'Product Data Wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': generic_id.id,
            'res_model': 'ks.generic.configuration',
            'target': 'new',
            'context': context,
        }

    def ks_pull_from_shopify(self):
        if self:
            instance_counts = self.env['ks.shopify.connector.instance'].search(
                [('ks_instance_state', 'in', ['active'])])
            if len(instance_counts) > 1:
                action = self.sudo().env.ref('ks_shopify.ks_instance_selection_action_pull').read()[0]
                action['context'] = {'pull_from_shopify': True}
                return action
            else:
                data_prepared = self.ks_shopify_product_template.filtered(
                    lambda x: x.ks_shopify_instance.id == instance_counts.id)
                if data_prepared and data_prepared.ks_shopify_product_id:
                    ##Handle shopify import here
                    shopify_id = data_prepared.ks_shopify_product_id
                    json_data = self.env['ks.shopify.product.template'].ks_shopify_get_product(shopify_id,
                                                                                               instance=instance_counts)
                    if json_data:
                        for rec in json_data:
                            product = self.env['ks.shopify.product.template'].ks_manage_shopify_product_template_import(
                                instance_counts,
                                rec)
                        product_data_non_filter = self.env[
                            'ks.shopify.product.template'].ks_get_product_data_for_stock_adjustment([rec],
                                                                                                    instance_counts)
                        valid_product_data = []
                        for rec in product_data_non_filter:
                            if rec.get('product_id'):
                                valid_product_data.append(rec)
                        inventory_adjustment_created = self.env['stock.inventory'].ks_create_stock_inventory_adjustment(
                            valid_product_data, instance_counts[0].ks_warehouse.lot_stock_id)
                        if inventory_adjustment_created:
                            inventory_adjustment_created.for_shopify = True
                    else:
                        _logger.info("Fatal Error in Syncing Product from shopify")

                else:
                    _logger.info("Layer record must have shopify id")
        else:
            active_ids = self.env.context.get("active_ids")
            instances = self.env['ks.shopify.connector.instance'].search([('ks_instance_state', 'in', ['active'])])
            if len(instances) > 1:
                action = self.sudo().env.ref('ks_shopify.ks_instance_selection_action_pull').read()[0]
                action['context'] = {'pull_from_shopify': True, 'active_ids': active_ids,
                                     'active_model': 'product.template'}
                return action
            else:
                records = self.browse(active_ids)
                if len(records) == 1:
                    data_prepared = self.ks_shopify_product_template.filtered(
                        lambda x: x.ks_shopify_instance.id == instances.id)
                    if data_prepared and data_prepared.ks_shopify_product_id:
                        shopify_id = data_prepared.ks_shopify_product_id
                        json_data = self.env['ks.shopify.product.template'].ks_shopify_get_product(shopify_id,
                                                                                                   instance=instances)
                        if json_data:
                            for rec in json_data:
                                product = self.env[
                                    'ks.shopify.product.template'].ks_manage_shopify_product_template_import(
                                    instances,
                                    rec)
                        else:
                            _logger.info("Fatal Error in Syncing Product from shopify")

                    else:
                        _logger.info("Layer record must have shopify id")

                else:
                    for rec in records:
                        data_prepared = rec.ks_shopify_product_template.filtered(
                            lambda x: x.ks_shopify_instance.id == instances.id)
                        shopify_id = data_prepared.ks_shopify_product_id
                        if shopify_id:
                            json_data = self.env['ks.shopify.product.template'].ks_shopify_get_product(shopify_id,
                                                                                                       instance=instances)
                            if json_data:
                                self.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(instances,
                                                                                                    json_data)

    def ks_manage_shopify_direct_syncing(self, record, instance_ids, push=False, pull=False, generic_wizard=False):
        try:
            for instance in instance_ids:
                if pull:
                    ##Handling of pull ther records from shopify here
                    for product in record:
                        data_prepared = product.ks_shopify_product_template.filtered(
                            lambda x: x.ks_shopify_instance.id == instance.id)
                        if data_prepared and data_prepared.ks_shopify_product_id:
                            ##Handle shopify import here
                            shopify_id = data_prepared.ks_shopify_product_id
                            json_data = self.env['ks.shopify.product.template'].ks_shopify_get_product(shopify_id,
                                                                                                       instance=instance)
                            if json_data:
                                for rec in json_data:
                                    product = self.env[
                                        'ks.shopify.product.template'].ks_manage_shopify_product_template_import(
                                        instance, rec)
                            else:
                                _logger.info("Fatal Error in Syncing Product from shopify")

                        else:
                            _logger.info("Layer record must have shopify id")
                elif push:
                    for product in record:
                        data_prepared = product.ks_shopify_product_template.filtered(
                            lambda c: c.ks_shopify_instance.id == instance.id)
                        if data_prepared:
                            ##Run update prepare command and export here
                            layer_product = self.env['ks.shopify.product.template'].update_shopify_record(instance,
                                                                                                          product,
                                                                                                          generic_wizard=generic_wizard)
                        else:
                            layer_product = self.env['ks.shopify.product.template'].create_shopify_record(instance,
                                                                                                          product,
                                                                                                          generic_wizard=generic_wizard)

                        if layer_product:
                            # layer_product.ks_action_shopify_export_product(product_config)
                            self.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(
                                records=layer_product, instance=instance_ids, product_config=generic_wizard)

        except Exception as e:
            _logger.info(str(e))

    def open_shopify_mapper(self):
        active_records = self._context.get("active_ids", False)
        model = self.env['ir.model'].search([('model', '=', self._name)])
        mapping_wizard = self.env['ks.shopify.global.record.mapping'].action_open_product_mapping_wizard(model,
                                                                                                         active_records,
                                                                                                         "Product Record Mapping")
        return mapping_wizard


class KsStockInventory(models.Model):
    _inherit = "stock.inventory"

    for_shopify = fields.Boolean("Shopify Inventory Update")
