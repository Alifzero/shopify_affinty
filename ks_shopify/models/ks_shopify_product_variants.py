from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class KsShopifyProductVariant(models.Model):
    _name = "ks.shopify.product.variant"
    _rec_name = "ks_shopify_product_variant"
    _description = "Shopify Product Variant"
    _order = 'create_date desc'

    ks_weight = fields.Float(string='Weight')
    ks_option1 = fields.Char("Option 1")
    ks_option2 = fields.Char("Option 2")
    ks_option3 = fields.Char("Option 3")
    # ks_volume = fields.Float(string='Volume', compute="_ks_compute_volume", store=True)
    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Instance", readonly=True,
                                     help=_("Shopify Connector Instance reference"), ondelete='cascade')

    ks_shopify_variant_id = fields.Char(string='Record ID',
                                       help=_("the record id of the particular record defied in the Connector"))
    ks_date_created = fields.Datetime(string='Date Created', help=_("The date on which the record is created on the Connected"
                                                             " Connector Instance"), readonly=True)
    ks_date_updated = fields.Datetime(string='Date Updated', help=_("The latest date on which the record is updated on the"
                                                             " Connected Connector Instance"), readonly=True)
    ks_shopify_rp_pricelist = fields.Many2one("product.pricelist.item", compute="_ks_calculate_prices", store=True,
                                          string="Regular Pricelist Item", help="Displays Shopify Regular Price")
    ks_shopify_cp_pricelist = fields.Many2one("product.pricelist.item", compute="_ks_calculate_prices", store=True,
                                          string="Compare Pricelist Item", help="Displays Shopify compare Price")
    ks_shopify_regular_price = fields.Float(string='shopify Regular Price', compute="ks_update_shopify_regular_price", default=0.0)
    ks_shopify_compare_price = fields.Float(string='Shopify Compare Price', compute='ks_update_shopify_compare_price', default=0.0)
    ks_shopify_product_variant = fields.Many2one('product.product', string='Odoo Product Variant', readonly=True, help="Displays Odoo Linked Product Variant Name")
    ks_name = fields.Char(string="Name", related="ks_shopify_product_variant.name")
    ks_shopify_product_tmpl_id = fields.Many2one('ks.shopify.product.template', string="Shopify Product Template", readonly=True,
                                            ondelete='cascade', help="Displays Shopify Product Template Name")
    ks_shopify_image_ids = fields.One2many('ks.shopify.product.images', 'ks_shopify_variant_id', string='Images', readonly=True)
    # ks_shopify_manage_stock = fields.Boolean("Manage Stock in Shopify")
    ks_shopify_description = fields.Html(string="Description", help="Message displayed as product description on Shopify")
    ks_default_code = fields.Char(string='SKU')
    ks_barcode = fields.Char(string='Barcode')
    # ks_manage_template = fields.Char('Manage Template', default=False)
    # ks_sync_states = fields.Boolean(string="Sync Status", compute='compute_sync_status', readonly=True)
    ks_active = fields.Boolean(string="Variant Active", default=False, help="Enables/Disables the variant")
    ks_mapped = fields.Boolean(string="Manual Mapping", readonly=True)
    ks_shopify_inventory_id = fields.Char("Inventory ID")
    ks_inventory_policy = fields.Selection([('continue', 'Continue'), ('deny', 'Deny')], 'Inventory Policy', default='deny')
    ks_company_id = fields.Many2one("res.company", string="Company", compute="_compute_company", store=True,
                                    help="Displays Company Name")

    @api.depends('ks_shopify_instance')
    def _compute_company(self):
        """
        Computes company for the Shopify Product Variant to be created on odoo layer
        :return:
        """
        for rec in self:
            if rec.ks_shopify_instance.ks_company_id:
                rec.ks_company_id = rec.ks_shopify_instance.ks_company_id.id
            else:
                rec.ks_company_id = self._context.get('company_id', self.env.company.id)

    @api.depends('ks_shopify_instance', 'ks_shopify_instance.ks_shopify_regular_pricelist', 'ks_shopify_instance.ks_shopify_compare_pricelist', 'ks_shopify_product_variant')
    def _ks_calculate_prices(self):
        for rec in self:
            rec.ks_shopify_rp_pricelist = False
            rec.ks_shopify_cp_pricelist = False
            instance = rec.ks_shopify_instance
            if instance:
                regular_price_list = self.env['product.pricelist.item'].search(
                    [('pricelist_id', '=', instance.ks_shopify_regular_pricelist.id),
                     ('product_id', '=', rec.ks_shopify_product_variant.id)], limit=1)
                rec.ks_shopify_rp_pricelist = regular_price_list.id
                compare_price_list = self.env['product.pricelist.item'].search(
                    [('pricelist_id', '=', instance.ks_shopify_compare_pricelist.id),
                     ('product_id', '=', rec.ks_shopify_product_variant.id)], limit=1)
                rec.ks_shopify_cp_pricelist = compare_price_list.id

    def ks_update_shopify_regular_price(self):
        """
        Updates the Regular price from the pricelist
        :return: None
        """
        for rec in self:
            rec.ks_shopify_regular_price = (self.env['product.pricelist.item'].search(
                [('pricelist_id', '=', rec.ks_shopify_instance.ks_shopify_regular_pricelist.id),
                 ('product_id', '=', rec.ks_shopify_product_variant.id)], limit=1).fixed_price) if self.env[
                'product.pricelist.item'].search(
                [('pricelist_id', '=', rec.ks_shopify_instance.ks_shopify_regular_pricelist.id),
                 ('product_id', '=', rec.ks_shopify_product_variant.id)], limit=1).fixed_price else '0.0'

    def ks_update_shopify_compare_price(self):
        """
        Updates the compare price from the pricelist
        :return: None
        """
        for rec in self:
            rec.ks_shopify_compare_price = (self.env['product.pricelist.item'].search(
                [('pricelist_id', '=', rec.ks_shopify_instance.ks_shopify_compare_pricelist.id),
                 ('product_id', '=', rec.ks_shopify_product_variant.id)], limit=1).fixed_price) if self.env[
                'product.pricelist.item'].search(
                [('pricelist_id', '=', rec.ks_shopify_instance.ks_shopify_compare_pricelist.id),
                 ('product_id', '=', rec.ks_shopify_product_variant.id)], limit=1).fixed_price else '0.0'

    def open_regular_pricelist_rules_data(self):
        """
        :return: The tree view for the regular pricelist item
        """
        self.ensure_one()
        domain = [('product_id', '=', self.ks_shopify_product_variant.id if self.ks_shopify_product_variant.id else 0),
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

    def open_compare_pricelist_rules_data(self):
        """
        :return: The tree view for the compare pricelist
        """
        self.ensure_one()
        domain = [('product_id', '=', self.ks_shopify_product_variant.id if self.ks_shopify_product_variant.id else 0),
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

    def ks_update_shopify_product_variant(self, product_tmpl_id, variant_record_id, data, instance):
        try:
            product_data = self.env['ks.api.handler'].ks_put_data(instance, 'variants', data, variant_record_id, product_tmpl_id)
            return product_data
        except ConnectionError:
            raise Exception("Couldn't Connect the Instance at time of Customer Syncing !! Please check the network "
                            "connectivity or the configuration parameters are not correctly set")
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="update",
                                                               status="failed",
                                                               type="product_variant",
                                                               instance=instance,
                                                               operation_flow="odoo_to_shopify",
                                                               shopify_id=0,
                                                               layer_model="ks.shopify.product.variant",
                                                               message=str(e))

    def ks_manage_shopify_prepare_variant(self, odoo_product, layer_product, instance, operation=False, generic_wizard=False):
        """
        :param odoo_product: product.template()
        :param layer_product: ks.shopify.product.template()
        :param instance: ks.shopify.connector.instance()
        :return: ks.shopify.product.variants
        """
        try:
            if odoo_product and layer_product:
                variants = odoo_product.product_variant_ids
                variant_prepared = None
                for variant in variants:
                    variant_prepared = variant.ks_shopify_product_variant.filtered(lambda x:x.ks_shopify_instance == instance)
                    data = self.ks_map_prepare_variant_data(variant, layer_product, instance, variant_prepared=variant_prepared, generic_wizard=generic_wizard)
                    if variant_prepared and variant.ks_shopify_product_template.filtered(lambda x:x.ks_shopify_instance == instance)[0].id == layer_product.id:
                        variant_prepared.write(data)
                        self.env['product.product'].ks_shopify_manage_price_to_export(variant,
                                                                              instance)
                    else:
                        if operation == 'update':
                            data["ks_active"] = False
                        data = self.ks_map_prepare_variant_data(variant, layer_product, instance, variant_prepared=variant_prepared, generic_wizard=generic_wizard)
                        variant_prepared = self.create(data)
                        self.env['product.product'].ks_shopify_manage_price_to_export(variant,
                                                                              instance)
                    if variant.image_1920:
                        variant_product_image = [i for i in variant_prepared.ks_shopify_image_ids if variant.image_1920 == i.ks_image]
                        product_var_image = variant_product_image[0] if len(variant_product_image) else False
                        variant_id = variant.ks_shopify_product_template.filtered(lambda x:x.ks_shopify_instance == instance)
                        image_data = {
                            "ks_name": variant.name,
                            "ks_shopify_image_id": product_var_image.ks_shopify_image_id if product_var_image else '',
                            "ks_image_name": variant.name + str(variant.id),
                            "ks_shopify_variant_id": variant_prepared.id,
                            "ks_image": variant.image_1920,
                            "ks_shopify_template_id": variant_id.id

                        }
                        if not image_data.get('ks_shopify_image_id'):
                            for var in variant_prepared.ks_shopify_image_ids:
                                var.ks_shopify_variant_id = False
                            variant_image = variant_prepared.ks_shopify_image_ids.create(image_data)
        except Exception as e:
            raise e

    def ks_map_prepare_variant_data(self, odoo_variant, layer_product, instance, variant_prepared=False, generic_wizard=False):
        """
        :param odoo_variant: product.product()
        :param layer_product: ks.shopify.product.template()
        :param instance: ks.shopify.connector.instance()
        :return:variant layer compatible data
        """
        inventory_policy = layer_product.ks_inventory_policy if generic_wizard and generic_wizard.ks_push_additional_data else variant_prepared.ks_inventory_policy if variant_prepared.ks_inventory_policy else 'deny'
        data = {
            "ks_shopify_instance": instance.id,
            "ks_shopify_product_variant": odoo_variant.id,
            "ks_shopify_product_tmpl_id": layer_product.id,
            "ks_weight": odoo_variant.weight,
            "ks_active": True,
            "ks_inventory_policy": inventory_policy
        }
        count = 1
        for rec in odoo_variant.product_template_attribute_value_ids:
            option_value = "ks_option"+str(count)
            data.update({
                option_value: rec.name
            })
            count += 1
        return data

    def ks_shopify_get_all_product_variant(self, instance, templ_id, include=False):
        """
        :param instance: ks.shopify.connector.instance()
        :param templ_id: shopify product id
        :param include: specific ids
        :return: json response
        """
        try:
            all_retrieved_data = self.env['ks.api.handler'].ks_get_all_data(instance, 'variants', templ_id)
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                               status="failed",
                                                               type="product_variant",
                                                               instance=instance,
                                                               operation_flow="shopify_to_odoo",
                                                               shopify_id=0,
                                                               layer_model="ks.shopify.product.variant",
                                                               message=str(e))
        else:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                               status="success",
                                                               type="product_variant",
                                                               instance=instance,
                                                               operation_flow="shopify_to_odoo",
                                                               shopify_id=0,
                                                               layer_model="ks.shopify.product.variant",
                                                               message="Fetch of product variant Successful")
            return all_retrieved_data

    def get_all_variants_data(self, all_odoo_variations):
        """
        :param all_odoo_variations: [product.product()]
        :return: data for all varaints
        """
        data = []
        for var in all_odoo_variations:
            var_data = {}
            var_data["variant_id"] = var.id
            var_data["values"] = []
            for attr in var.product_template_attribute_value_ids:
                var_data['values'].append({"attribute_id": attr.attribute_id.id,
                                           "attribute_name": attr.attribute_id.name,
                                           "attribute_value_id": attr.product_attribute_value_id.id,
                                           "attribute_value_name": attr.product_attribute_value_id.name})

            data.append(var_data)

        return data

    def ks_shopify_manage_variations_import(self, instance, odoo_main_product, shopify_layer_product, product_json_data):
        """
        :param instance: ks.shopify.connector.instance()
        :param odoo_main_product: product.temnplate()
        :param product_json_data: shopify product json data
        :return: ks.shopify.product.variant()
        """
        all_odoo_variations = odoo_main_product.product_variant_ids
        all_variants_data = self.get_all_variants_data(all_odoo_variations)
        all_shopify_variations = self.ks_shopify_get_all_product_variant(instance, product_json_data.get("id"),
                                                                 include=product_json_data.get("variations"))
        variant_exist = None
        for index, variant in enumerate(all_shopify_variations):
            variant_exist = self.search([('ks_shopify_instance', '=', instance.id),
                                         ('ks_shopify_variant_id', '=', variant.get("id"))])
            if variant_exist:
                # Run update command here
                layer_data = self.ks_map_variant_data_for_layer(variant, all_variants_data, instance, shopify_layer_product)
                variant_exist.write(layer_data)
                self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(variant,
                                                                                 variant_exist,
                                                                                 "ks_shopify_variant_id")
            else:
                ks_barode_exists = self.env['product.product'].search([('barcode', '=', variant.get('barcode'))])
                if variant.get('barcode') and ks_barode_exists and not self.env.context.get('auto_sync_map'):
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                           ks_model='product.product',
                                                                           ks_layer_model='ks.shopify.product.variant',
                                                                           ks_message='Duplicate Barcode Exists',
                                                                           ks_status="failed",
                                                                           ks_type="product",
                                                                           ks_record_id=0,
                                                                           ks_operation_flow="shopify_to_odoo",
                                                                           ks_shopify_id=product_json_data.get(
                                                                               "id", 0),
                                                                           ks_shopify_instance=instance)
                    return False
                layer_data = self.ks_map_variant_data_for_layer(variant, all_variants_data, instance, shopify_layer_product)
                variant_exist = self.create(layer_data)
                self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(variant,
                                                                                 variant_exist,
                                                                                 "ks_shopify_variant_id")
            if instance.ks_sync_price:
                variant_exist.ks_shopify_product_variant.ks_manage_shopify_price_to_import(instance, variant.get("price"),
                                                                          variant.get("compare_at_price"))
        not_active_variant = []
        ks_product_shopify_id = odoo_main_product.ks_shopify_product_template.filtered(
            lambda x: x.ks_shopify_instance == instance)
        for variants in ks_product_shopify_id.ks_shopify_variant_ids:
            flag = 0
            for shopify_variants in product_json_data.get('variants'):
                if variants.ks_shopify_variant_id == str(shopify_variants.get('id')):
                    flag = 1
            if not flag:
                not_active_variant.append(variants)
        try:
            for var in not_active_variant:
                var.update({"ks_active": False})

        except Exception as e:
            _logger.info(str(e))
        # return variant_exist

    def ks_find_variant_match(self, all_variants_data, attribute):
        """
        :param all_variants_data: odoo variants data
        :param attribute: json shopify attribute
        :return:
        """
        for values in all_variants_data:
            flag = 0
            for attr in values['values']:
                for shopify_att in attribute:
                    attribute_name = shopify_att
                    attribute_value = shopify_att
                    if attribute_value.lower() == attr.get("attribute_value_name").lower():
                        flag += 1
                if flag == len(attribute):
                    return values['variant_id']
        return False

    def ks_map_variant_data_for_layer(self, variant, all_variants_data, instance, shopify_layer_product):
        """
        :param variant: shopify json data
        :param all_variants_data: dict of all attributes and attributes values
        :param instance: ks.shopify.connector.instance()
        :param odoo_main_product: product.template()
        :return: ks.shopify.product.variant() compatible data
        """
        data = {
            "ks_weight": variant.get("weight", 0),
            "ks_shopify_instance": instance.id,
            "ks_shopify_variant_id": str(variant.get("id")),
            "ks_shopify_product_tmpl_id": shopify_layer_product.id,
            "ks_shopify_description": variant.get("description", ''),
            "ks_default_code": variant.get("sku", ''),
            "ks_barcode": variant.get("barcode", ''),
            "ks_option1": variant.get('option1') or '',
            "ks_option2": variant.get('option2') or '',
            "ks_option3": variant.get('option3') or '',
            "ks_shopify_inventory_id": variant.get('inventory_item_id'),
            "ks_inventory_policy": variant.get('inventory_policy'),
        }
        attribute = []
        if variant.get('option1'):
            attribute.append(variant.get('option1'))
        if variant.get('option2'):
            attribute.append(variant.get('option2'))
        if variant.get('option3'):
            attribute.append(variant.get('option3'))
        # attribute = variant['attributes']
        find_variant = self.ks_find_variant_match(all_variants_data, attribute)
        if find_variant:
            product_variant = self.env['product.product'].browse(find_variant)
            if product_variant:
                variant_data = {"weight": variant.get('weight') or False,
                                "default_code": variant.get('sku') or None,
                                "barcode": variant.get('barcode') or None}

                if instance.ks_meta_fields_map:
                    meta_data = self.env['ks.shopify.meta.mapping'].get_meta_fields_data(instance=instance, model='variants',
                                                                           ids=variant.get('id'), ks_model='product.product',
                                                                                         additional_id=variant.get('product_id'))
                    variant_data.update(meta_data)
                product_variant.write(variant_data)
            data.update({"ks_shopify_product_variant": find_variant, "ks_active": True})
        else:
            data.update({"ks_active": False})
        return data

    def ks_prepare_product_variant_to_export(self, product_config=False):
        variant = self.ks_shopify_product_variant
        server_action = product_config.get("server_action") if product_config else False
        stock_qty = self.env['product.product'].ks_get_stock_quantity(self.ks_shopify_instance.ks_warehouse,
                                                                      variant,
                                                                      self.ks_shopify_instance.ks_stock_field_type.name)
        data = {
            'product_id': int(variant.ks_shopify_product_template.filtered(lambda x:x.ks_shopify_instance == self.ks_shopify_instance).ks_shopify_product_id) if variant.ks_shopify_product_template else 0,
            'description': self.ks_shopify_description if self.ks_shopify_description else '',
            'weight': str(self.ks_weight),
            "option1": self.ks_option1,
            "option2": self.ks_option2,
            "option3": self.ks_option3,
            "barcode": variant.barcode or '',
            "sku": variant.default_code if variant.default_code else '',
            "inventory_management": "shopify",
            "manage_stock": True,
        }
        if self.ks_shopify_variant_id:
            data.update({
                'id': int(self.ks_shopify_variant_id) if self.ks_shopify_variant_id else 0,
            })
        compare_price = self.ks_shopify_instance.ks_shopify_regular_pricelist.item_ids.search([('product_id', '=', variant.id), ('pricelist_id', '=', self.ks_shopify_instance.ks_shopify_compare_pricelist.id)], limit=1).fixed_price
        if product_config:
            if product_config["ks_update_price"]:
                data.update(
                    {
                        "price": str(
                            self.ks_shopify_instance.ks_shopify_regular_pricelist.item_ids.search([('product_id', '=', variant.id), ('pricelist_id', '=', self.ks_shopify_instance.ks_shopify_regular_pricelist.id)], limit=1).fixed_price),
                        "compare_at_price": str(compare_price) if compare_price else '',
                    }
                )
            if product_config["ks_inventory_policy"]:
                data.update(
                    {
                        'inventory_policy': product_config["ks_inventory_policy"]
                    }
                )
            else:
                data.update(
                    {
                        'inventory_policy': self.ks_inventory_policy
                    }
                )

        else:
            data.update({
                # "inventory_quantity": int(stock_qty),
                "price": str(self.ks_shopify_instance.ks_shopify_regular_pricelist.item_ids.search([('product_id', '=', variant.id), ('pricelist_id', '=', self.ks_shopify_instance.ks_shopify_regular_pricelist.id)], limit=1).fixed_price),
                "compare_at_price": str(compare_price) if compare_price else '',
            })
        return data

    def ks_manage_variant_attributes(self, variant):
        attribute_data = []
        if variant.product_template_attribute_value_ids:
            for attribute_value in variant.product_template_attribute_value_ids:
                # Manage the syncing of already prepared
                value_layer_exist = self.env['ks.shopify.pro.attr.value'].check_if_already_prepared(self.ks_shopify_instance,
                                                                                                attribute_value.product_attribute_value_id)
                if value_layer_exist:
                    attribute_data.append({
                        "id": value_layer_exist.ks_shopify_attribute_id,
                        "name": value_layer_exist.ks_name,
                        "option": attribute_value.product_attribute_value_id.name
                    })
                else:
                    attribute_data.append({
                        "id": 0,
                        "name": attribute_value.attribute_id.name,
                        "option": attribute_value.product_attribute_value_id.name
                    })
        return attribute_data

    def ks_manage_shopify_product_variant_export(self, instance, queue_record=False, product_config=False):
        for rec in self:
            if rec.ks_active and rec.ks_shopify_product_variant:
                try:
                    product_exported = rec.ks_shopify_variant_id
                    data = rec.ks_prepare_product_variant_to_export(product_config)
                    if product_exported:
                        product_data_response = self.ks_update_shopify_product_variant(
                            rec.ks_shopify_product_tmpl_id.ks_shopify_product_id,
                            product_exported, data, instance)
                        if product_data_response:
                            self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(product_data_response,
                                                                                             rec,
                                                                                             'ks_shopify_variant_id')
                except Exception as e:
                    if queue_record:
                        queue_record.ks_update_failed_state()


class KsProductVariantInherit(models.Model):
    _inherit = "product.product"

    ks_shopify_product_variant = fields.One2many('ks.shopify.product.variant', 'ks_shopify_product_variant')

    def ks_shopify_manage_price_to_export(self, product_variant, instance):
        regular_price_list = instance.ks_shopify_regular_pricelist
        compare_price_list = instance.ks_shopify_compare_pricelist
        ks_product_shopify_id = product_variant.ks_shopify_product_template.filtered(
            lambda x: x.ks_shopify_instance == instance)
        compare_price = ks_product_shopify_id.ks_shopify_compare_price
        all_regular_price_list = instance.ks_shopify_pricelist_ids.filtered(lambda l: l.ks_shopify_instance == instance and (l.ks_shopify_regular_pricelist))
        all_compare_price_list = instance.ks_shopify_pricelist_ids.filtered(
            lambda l: l.ks_shopify_instance == instance and (l.ks_shopify_compare_pricelist))
        for price_list in all_regular_price_list:
            if product_variant.ks_shopify_product_variant.filtered(lambda x:x.ks_shopify_instance == instance):
                reg_price = product_variant.ks_shopify_product_variant.filtered(lambda x:x.ks_shopify_instance == instance)[0].ks_shopify_regular_price
            else:
                reg_price = product_variant.ks_shopify_product_template.filtered(lambda x:x.ks_shopify_instance == instance)[0].ks_shopify_regular_price
            price_list.ks_set_product_price(product_id=product_variant.id, price=reg_price, main_price_list=regular_price_list)
        for price_list in all_compare_price_list:
            if compare_price != ks_product_shopify_id.ks_shopify_compare_price:
                ks_product_shopify_id.ks_shopify_compare_price = compare_price
            if product_variant.ks_shopify_product_variant.filtered(lambda x:x.ks_shopify_instance == instance):
                comp_price = product_variant.ks_shopify_product_variant.filtered(lambda x:x.ks_shopify_instance == instance)[0].ks_shopify_compare_price
            else:
                comp_price = product_variant.ks_shopify_product_template.filtered(lambda x:x.ks_shopify_instance == instance)[0].ks_shopify_compare_price
            price_list.ks_set_product_price(product_id=product_variant.id, price=comp_price, main_price_list=compare_price_list)

    def ks_manage_shopify_price_to_import(self, instance, regular_price=0, compare_price=0):
        regular_price = float(regular_price or 0.0) if instance.ks_sync_price else 0.0
        compare_price = float(compare_price or 0.0) if instance.ks_sync_price else 0.0
        regular_price_list = instance.ks_shopify_regular_pricelist
        compare_price_list = instance.ks_shopify_compare_pricelist
        all_regular_price_list = instance.ks_shopify_pricelist_ids.filtered(lambda l: l.ks_shopify_instance == instance and (l.ks_shopify_regular_pricelist))
        all_compare_price_list = instance.ks_shopify_pricelist_ids.filtered(lambda l: l.ks_shopify_instance == instance and (l.ks_shopify_compare_pricelist))
        for price_list in all_regular_price_list:
            price_list.ks_set_product_price(product_id=self.id, price=regular_price, main_price_list=regular_price_list)
        for price_list in all_compare_price_list:
            price_list.ks_set_product_price(product_id=self.id, price=compare_price, main_price_list=compare_price_list)
