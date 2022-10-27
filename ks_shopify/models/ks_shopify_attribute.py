# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class KsProductAttributeInherit(models.Model):
    _inherit = "product.attribute"

    ks_connected_shopify_attributes = fields.One2many('ks.shopify.product.attribute', 'ks_product_attribute',
                                                  string="Shopify Attribute Ids")

    def action_shopify_layer_attributes(self):
        """
        opens wizard fot shopify layer attributes
        :return: action
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("ks_shopify.action_ks_shopify_product_attribute")
        action['domain'] = [('id', 'in', self.ks_connected_shopify_attributes.ids)]
        return action


class KsModelProductAttribute(models.Model):
    _name = 'ks.shopify.product.attribute'
    _description = "Shopify Product Attribute"
    _rec_name = 'ks_name'

    # Fields need to be Connected to any Connector
    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Instance", readonly=True,
                                     help=_("Shopify Connector Instance reference"),
                                     ondelete='cascade')
    ks_shopify_attribute_id = fields.Char('Shopify Attribute ID', readonly=True,
                                         help=_("the record id of the attribute record defined in the Connector"))
    ks_product_attribute = fields.Many2one('product.attribute', string="Odoo Product Attribute", readonly=True,
                                           ondelete='cascade', help="Displays Odoo Product Attribute Reference")
    ks_need_update = fields.Boolean(help=_("This will need to determine if a record needs to be updated, Once user "
                                           "update the record it will set as False"), readonly=True,
                                    string="Need Update")
    ks_mapped = fields.Boolean(string="Manual Mapping", readonly = True)

    # Connector Information related
    ks_name = fields.Char(string="Name", related='ks_product_attribute.name', help="Displays Shopify Attribute Name")
    ks_slug = fields.Char(string="Slug", help="Displays Shopify Attribute Slug Name")
    ks_display_type = fields.Selection([
        ('radio', 'Radio'),
        ('select', 'Select'),
        ('color', 'Color')], default='radio', string="Type", required=True,
        help="The display type used in the Product Configurator.")
    ks_company_id = fields.Many2one("res.company", string="Company", compute="_compute_company", store=True,
                                    help="Displays Company Name")

    @api.depends('ks_shopify_instance')
    def _compute_company(self):
        """
        Computes company for the Shopify Product Attribute
        :return:
        """
        for rec in self:
            if rec.ks_shopify_instance.ks_company_id:
                rec.ks_company_id = rec.ks_shopify_instance.ks_company_id.id
            else:
                rec.ks_company_id = self._context.get('company_id', self.env.company.id)

    def check_if_already_prepared(self, instance, product_attribute):
        """
        Checks if data is already prepared for exporting on layer model
        :param instance: shopify instance
        :param product_attribute: shopify product attribute
        :return: attribute_exist
        """
        attribute_exist = self.search([('ks_shopify_instance', '=', instance.id),
                                       ('ks_product_attribute', '=', product_attribute.id)], limit=1)
        if attribute_exist:
            return attribute_exist
        else:
            return False

    def action_shopify_layer_attribute_terms(self):
        """
        opens layer model attributes values
        :return: action
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("ks_shopify.action_ks_shopify_product_attribute_value")
        action['domain'] = [('ks_attribute_id', '=', self.ks_product_attribute.id)]
        return action

    def ks_map_attribute_data_for_odoo(self, json_data):
        data = {}
        if json_data:
            data = {
                "name": json_data.get('name'),
                "display_type": 'select',
            }
        return data

    def ks_map_attribute_data_for_layer(self, attribute_data, product_attribute, instance):
        data = {
            "ks_product_attribute": product_attribute.id,
            "ks_shopify_instance": instance.id,
            "ks_display_type": "select",
            "ks_shopify_attribute_id": attribute_data.get("id")
        }
        return data

    def ks_manage_attribute_import(self, shopify_instance, attribute_data, queue_record=False):
        """
        :param shopify_instance:
        :param attribute_data: attributes json data
        :param queue_record: boolean trigger for queue
        :return: None
        """
        try:
            layer_attribute = self
            layer_attribute = self.search([('ks_shopify_instance', '=', shopify_instance.id),
                                           ("ks_shopify_attribute_id", '=', attribute_data.get("id") if attribute_data else None)])
            odoo_attribute = layer_attribute.ks_product_attribute
            odoo_main_data = self.ks_map_attribute_data_for_odoo(attribute_data)
            if layer_attribute:
                try:
                    odoo_attribute.ks_manage_attribute_in_odoo(odoo_main_data.get('name'),
                                                               odoo_main_data.get('display_type'),
                                                               odoo_attribute=odoo_attribute)
                    layer_data = self.ks_map_attribute_data_for_layer(attribute_data, odoo_attribute, shopify_instance)
                    layer_attribute.write(layer_data)
                    # attribute_terms = self.env['ks.shopify.pro.attr.value'].ks_shopify_get_all_attribute_terms(shopify_instance,
                    #                                                                                    layer_attribute.ks_shopify_attribute_id)
                    # if attribute_terms:
                    self.env['ks.shopify.pro.attr.value'].ks_manage_attribute_value_import(shopify_instance,
                                                                                       attribute_data,
                                                                                       odoo_attribute,
                                                                                       queue_record=queue_record)
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                       ks_model='product.attribute',
                                                                       ks_layer_model='ks.shopify.product.attribute',
                                                                       ks_message="Attribute import update success",
                                                                       ks_status="success",
                                                                       ks_type="attribute",
                                                                       ks_record_id=layer_attribute.id,
                                                                       ks_operation_flow="shopify_to_odoo",
                                                                       ks_shopify_id=attribute_data.get("id", 0),
                                                                       ks_shopify_instance=shopify_instance)
                except Exception as e:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                       ks_model='product.attribute',
                                                                       ks_layer_model='ks.shopify.product.attribute',
                                                                       ks_message=str(e),
                                                                       ks_status="failed",
                                                                       ks_type="attribute",
                                                                       ks_record_id=layer_attribute.id,
                                                                       ks_operation_flow="shopify_to_odoo",
                                                                       ks_shopify_id=attribute_data.get("id", 0),
                                                                       ks_shopify_instance=shopify_instance)
            else:
                try:
                    if attribute_data.get('id'):
                        odoo_attribute = odoo_attribute.ks_manage_attribute_in_odoo(odoo_main_data.get('name'),
                                                                                    odoo_main_data.get('display_type'),
                                                                                    odoo_attribute=odoo_attribute)
                        layer_data = self.ks_map_attribute_data_for_layer(attribute_data, odoo_attribute, shopify_instance)
                        layer_attribute = self.create(layer_data)
                        # attribute_terms = self.env['ks.shopify.pro.attr.value'].ks_shopify_get_all_attribute_terms(shopify_instance,
                        #                                                                                    layer_attribute.ks_shopify_attribute_id)
                        # if attribute_terms:
                        self.env['ks.shopify.pro.attr.value'].ks_manage_attribute_value_import(shopify_instance,
                                                                                           attribute_data,
                                                                                           odoo_attribute,
                                                                                           queue_record=queue_record)
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                           ks_model='product.attribute',
                                                                           ks_layer_model='ks.shopify.product.attribute',
                                                                           ks_message="Attribute import create success",
                                                                           ks_status="success",
                                                                           ks_type="attribute",
                                                                           ks_record_id=layer_attribute.id,
                                                                           ks_operation_flow="shopify_to_odoo",
                                                                           ks_shopify_id=attribute_data.get("id", 0),
                                                                           ks_shopify_instance=shopify_instance)
                    else:
                        odoo_attribute = odoo_attribute.ks_manage_attribute_in_odoo(odoo_main_data.get('name'),
                                                                                    odoo_main_data.get(
                                                                                        'display_type'),
                                                                                    odoo_attribute=odoo_attribute)
                        for rec in attribute_data.get('options'):
                            data = {
                                "name": rec,
                                "display_type": 'select',
                                "attribute_id": odoo_attribute.id,
                            }
                            self.env['product.attribute.value'].ks_manage_attribute_value_in_odoo(data.get('name'),
                                                              odoo_attribute.id,
                                                              odoo_attribute_value=False)
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                           ks_model='product.attribute',
                                                                           ks_layer_model='ks.shopify.product.attribute',
                                                                           ks_message="Attribute import create success",
                                                                           ks_status="success",
                                                                           ks_type="attribute",
                                                                           ks_record_id=layer_attribute.id,
                                                                           ks_operation_flow="shopify_to_odoo",
                                                                           ks_shopify_id=attribute_data.get("id", 0),
                                                                           ks_shopify_instance=shopify_instance)
                except Exception as e:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                       ks_model='product.attribute',
                                                                       ks_layer_model='ks.shopify.product.attribute',
                                                                       ks_message=str(e),
                                                                       ks_status="failed",
                                                                       ks_type="attribute",
                                                                       ks_record_id=0,
                                                                       ks_operation_flow="shopify_to_odoo",
                                                                       ks_shopify_id=attribute_data.get("id", 0),
                                                                       ks_shopify_instance=shopify_instance)
            return odoo_attribute
        except Exception as e:
            if queue_record:
                queue_record.ks_update_failed_state()
            raise e

    def ks_manage_attribute_export(self, queue_record=False):
        """
        :param queue_record: Queue Boolean Trigger
        :return: json response
        """
        shopify_attribute_data_response = None
        odoo_base_attribute = self.ks_product_attribute
        try:
            shopify_attribute_id = self.ks_shopify_attribute_id
            shopify_attribute_data = self.ks_prepare_export_json_data(odoo_base_attribute, self)
            if shopify_attribute_id:
                try:
                    shopify_attribute_data_response = self.ks_shopify_update_attribute(shopify_attribute_id, shopify_attribute_data,
                                                                               self.ks_shopify_instance)
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                       ks_model='product.attribute',
                                                                       ks_layer_model='ks.shopify.product.attribute',
                                                                       ks_message="Attribute Export Update Successful",
                                                                       ks_status="success",
                                                                       ks_type="attribute",
                                                                       ks_record_id=self.id,
                                                                       ks_operation_flow="odoo_to_shopify",
                                                                       ks_shopify_id=shopify_attribute_data_response.get("id",
                                                                                                                 0),
                                                                       ks_shopify_instance=self.ks_shopify_instance)
                except Exception as e:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                       ks_model='product.attribute',
                                                                       ks_layer_model='ks.shopify.product.attribute',
                                                                       ks_message=str(e),
                                                                       ks_status="failed",
                                                                       ks_type="attribute",
                                                                       ks_record_id=self.id,
                                                                       ks_operation_flow="odoo_to_shopify",
                                                                       ks_shopify_id=0,
                                                                       ks_shopify_instance=self.ks_shopify_instance)
            else:
                try:
                    shopify_attribute_data_response = self.ks_shopify_post_attribute(shopify_attribute_data,
                                                                             self.ks_shopify_instance)
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                       ks_model='product.attribute',
                                                                       ks_layer_model='ks.shopify.product.attribute',
                                                                       ks_message="Attribute Export create Successful",
                                                                       ks_status="success",
                                                                       ks_type="attribute",
                                                                       ks_record_id=self.id,
                                                                       ks_operation_flow="odoo_to_shopify",
                                                                       ks_shopify_id=shopify_attribute_data_response.get("id",
                                                                                                                 0),
                                                                       ks_shopify_instance=self.ks_shopify_instance)
                except Exception as e:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                       ks_model='product.attribute',
                                                                       ks_layer_model='ks.shopify.product.attribute',
                                                                       ks_message=str(e),
                                                                       ks_status="failed",
                                                                       ks_type="attribute",
                                                                       ks_record_id=self.id,
                                                                       ks_operation_flow="odoo_to_shopify",
                                                                       ks_shopify_id=0,
                                                                       ks_shopify_instance=self.ks_shopify_instance)
            if shopify_attribute_data_response:
                self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(shopify_attribute_data_response,
                                                                                 self,
                                                                                 'ks_shopify_attribute_id',
                                                                                 {
                                                                                     "ks_slug": shopify_attribute_data_response.get(
                                                                                         'slug') or ''}
                                                                                 )
            all_attribute_values = self.env['ks.shopify.pro.attr.value'].search(
                [('ks_attribute_id', '=', self.ks_product_attribute.id),
                 ('ks_shopify_instance', '=', self.ks_shopify_instance.id)])
            all_attribute_values.ks_manage_attribute_value_export(self.ks_shopify_attribute_id, queue_record)
            return shopify_attribute_data_response
        except Exception as e:
            if queue_record:
                queue_record.ks_update_failed_state()
            raise e

    def ks_map_prepare_data_for_layer(self, instance, product_attribute):
        """
        :param product_category: product.category()
        :param instance: ks.shopify.connector.instance()
        :return: layer compatible data
        """
        data = {
            "ks_product_attribute": product_attribute.id,
            "ks_shopify_instance": instance.id,
        }
        return data

    def create_shopify_record(self, instance, odoo_attribute, export_to_shopify=False, queue_record=False):
        """
        """
        try:
            shopify_layer_exist = self.search([("ks_product_attribute", '=', odoo_attribute.id),
                                           ('ks_shopify_instance', '=', instance.id)], limit=1)
            if not shopify_layer_exist:
                data = self.ks_map_prepare_data_for_layer(instance, odoo_attribute)
                layer_attribute = self.create(data)
                self.env['ks.shopify.pro.attr.value'].ks_manage_value_preparation(instance, odoo_attribute.value_ids)
                self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_create",
                                                                       status="success",
                                                                       type="attribute",
                                                                       instance=instance,
                                                                       odoo_model="product.attribute",
                                                                       layer_model="ks.shopify.product.attribute",
                                                                       id=odoo_attribute.id,
                                                                       message="Layer preparation Success")
                if export_to_shopify:
                    try:
                        layer_attribute.ks_manage_attribute_export()
                    except Exception as e:
                        _logger.info(str(e))
                return layer_attribute
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_create",
                                                                       status="failed",
                                                                       type="attribute",
                                                                       instance=instance,
                                                                       odoo_model="product.attribute",
                                                                       layer_model="ks.shopify.product.attribute",
                                                                       id=odoo_attribute.id,
                                                                       message=str(e))

            if queue_record:
                queue_record.ks_update_failed_state()

    def update_shopify_record(self, instance, odoo_attribute, export_to_shopify=False, queue_record=False):
        """
        """
        try:
            shopify_layer_exist = self.search([("ks_product_attribute", '=', odoo_attribute.id),
                                           ('ks_shopify_instance', '=', instance.id)], limit=1)
            if shopify_layer_exist:
                data = self.ks_map_prepare_data_for_layer(instance, odoo_attribute)
                shopify_layer_exist.write(data)
                self.env['ks.shopify.pro.attr.value'].ks_manage_value_preparation(instance, odoo_attribute.value_ids)
                self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_update",
                                                                       status="success",
                                                                       type="attribute",
                                                                       instance=instance,
                                                                       odoo_model="product.attribute",
                                                                       layer_model="ks.shopify.product.attribute",
                                                                       id=odoo_attribute.id,
                                                                       message="Layer preparation Success")
                if export_to_shopify:
                    try:
                        shopify_layer_exist.ks_manage_attribute_export()
                    except Exception as e:
                        _logger.info(str(e))
                return shopify_layer_exist
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_update",
                                                                       status="failed",
                                                                       type="attribute",
                                                                       instance=instance,
                                                                       odoo_model="product.attribute",
                                                                       layer_model="ks.shopify.product.attribute",
                                                                       id=odoo_attribute.id,
                                                                       message=str(e))

            if queue_record:
                queue_record.ks_update_failed_state()
