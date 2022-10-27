# -*- coding: utf-8 -*-

from odoo import fields, models, _,api
import logging
_logger = logging.getLogger(__name__)


class KsProductAttributeValueExtended(models.Model):
    _inherit = "product.attribute.value"

    ks_connected_shopify_attribute_terms = fields.One2many('ks.shopify.pro.attr.value', 'ks_pro_attr_value',
                                                       string="Shopify Attribute Values Ids")


class KsShopifyProductAttributeModel(models.Model):
    _name = "ks.shopify.pro.attr.value"
    _rec_name = "ks_name"
    _description = "Shopify Product Attribute Value"

    ks_attribute_id = fields.Many2one('product.attribute', string="Attribute", ondelete='cascade',
                                      related='ks_pro_attr_value.attribute_id',
                                      index=True,
                                      help="The attribute cannot be changed once the value is used on at least one "
                                           "product.")
    ks_shopify_attribute_id = fields.Char('Shopify Attribute ID', readonly=True,
                                         help=_("the record id of the particular record defied in the Connector"))
    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Instance", readonly=True,
                                     help=_("Shopify Connector Instance reference"),
                                     ondelete='cascade')
    ks_pro_attr_value = fields.Many2one('product.attribute.value', string="Odoo Attribute Value", ondelete='cascade', help="Displays Odoo Attribute Value Name Reference")
    ks_name = fields.Char(string='Value', related="ks_pro_attr_value.name", translate=True, help="Displays Shopify Attribute Value Name")
    ks_mapped = fields.Boolean(string="Manual Mapping", readonly=True)
    ks_company_id = fields.Many2one("res.company", string="Company", compute="_compute_company", store=True,
                                    help="Displays Company Name")

    @api.depends('ks_shopify_instance')
    def _compute_company(self):
        """
        Computes company for the Shopify Product Attribute Value
        :return:
        """
        for rec in self:
            if rec.ks_shopify_instance.ks_company_id:
                rec.ks_company_id = rec.ks_shopify_instance.ks_company_id.id
            else:
                rec.ks_company_id = self._context.get('company_id', self.env.company.id)

    def ks_manage_value_preparation(self, instance, attribute_values):
        for value in attribute_values:
            product_attr_value_exist = self.check_if_already_prepared(instance, value)
            if not product_attr_value_exist:
                self.create_shopify_record(instance, value)
            else:
                self.update_shopify_record(instance, value)

    def ks_map_prepare_data_for_layer(self, instance, product_attribute_value):
        """
        """
        data = {
            "ks_pro_attr_value": product_attribute_value.id,
            "ks_shopify_instance": instance.id,
            "ks_attribute_id": product_attribute_value.attribute_id.id
        }
        return data

    def create_shopify_record(self, instance, attribute_value):
        """
        Created shopify data in layer model shopify to odoo
        :param instance: shopify Instance
        :param attribute_value: attribute value model domain
        :return:
        """
        data = self.ks_map_prepare_data_for_layer(instance, attribute_value)
        try:
            shopify_attribute_term = self.create(data)
            return shopify_attribute_term
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_create",
                                                                   status="failed",
                                                                   type="attribute_value",
                                                                   instance=instance,
                                                                   odoo_model="product.attribute.value",
                                                                   layer_model="ks.shopify.pro.attr.value",
                                                                   id=attribute_value.id,
                                                                   message=str(e))

    def update_shopify_record(self, instance, attribute_value):
        """
        Updates layer model record with attribute data from shopify
        :param instance: Shopify Instances
        :param attribute_value: attribute value model domain
        :return:
        """
        data = self.ks_map_prepare_data_for_layer(instance, attribute_value)
        try:
            product_attr_value_exist = self.check_if_already_prepared(instance, attribute_value)
            if product_attr_value_exist:
                product_attr_value_exist.write(data)
                return product_attr_value_exist
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_update",
                                                                   status="failed",
                                                                   type="attribute_value",
                                                                   instance=instance,
                                                                   odoo_model="product.attribute.value",
                                                                   layer_model="ks.shopify.pro.attr.value",
                                                                   id=attribute_value.id,
                                                                   message=str(e))

    def update_record_data_in_odoo(self):
        """
        Use: This will update the Layer record data to The Main Attribute linked to it
        :return:
        """
        for rec in self:
            try:
                json_data = rec.ks_pro_attr_value.ks_map_odoo_attribute_term_data_to_update(rec)
                rec.ks_pro_attr_value.write(json_data)
                rec.ks_need_update = False
            except Exception as e:
                self.env['ks.shopify.logger'].ks_create_log_param('update', 'attribute_value', rec.ks_shopify_instance,
                                                              rec.ks_attribute_id.id, 'Failed due to',
                                                              rec.ks_shopify_attribute_id, 'wl_to_odoo',
                                                              'failed', 'product.attribute.value',
                                                              'ks.shopify.pro.attr.value', e)

    def ks_populate_layer_update_to_odoo(self):
        """
        Use: This will check the No of instance in the main record if single record exist then it will update directly
        :return: None
        """
        self.ks_need_update = True
        if len(self.ks_shopify_instance) == 1:
            self.update_record_data_in_odoo()

    def check_if_already_prepared(self, instance, product_attr_value):
        """
        Checks if the records are already prepared or not
        :param instance: Shopify Instances
        :param product_attr_value: Product attribute value layer model domain
        :return: product_attr_value domain
        """
        product_attr_value_exist = self.search([('ks_shopify_instance', '=', instance.id),
                                                ('ks_pro_attr_value', '=', product_attr_value.id)], limit=1)
        return product_attr_value_exist


    def ks_prepare_import_json_data(self, json_data, attribute_id):
        """
        Prepares data to be imported on odoo from shopify
        :param json_data: api json data from shopify
        :param attribute_id: id of attribute
        :return: json data
        """
        data = {
            "ks_name": json_data.get('name'),
            # "ks_slug": json_data.get('slug') or '',
            "ks_shopify_attribute_id": attribute_id
        }
        return data

    def ks_manage_attribute_value_import(self, shopify_instance, shopify_attribute, odoo_attribute, queue_record=False):
        try:
            for value_data in shopify_attribute.get('values'):
                layer_attribute_value = self.search([('ks_shopify_instance', '=', shopify_instance.id),
                                                     ("ks_attribute_id", '=', odoo_attribute.id),
                                                     ("ks_name", '=', value_data)
                                                     ])
                odoo_attribute_value = layer_attribute_value.ks_pro_attr_value
                odoo_main_data = self.ks_map_attribute_value_data_for_odoo(value_data, odoo_attribute.id)
                if layer_attribute_value:
                    odoo_attribute_value.ks_manage_attribute_value_in_odoo(odoo_main_data.get('name'),
                                                                           odoo_attribute.id,
                                                                           odoo_attribute_value=odoo_attribute_value)
                    layer_data = self.ks_map_attribute_value_data_for_layer(value_data, odoo_attribute, odoo_attribute_value, shopify_attribute.get('id'), shopify_instance)
                    layer_attribute_value.write(layer_data)
                else:
                    odoo_attribute_value = odoo_attribute_value.ks_manage_attribute_value_in_odoo(odoo_main_data.get('name'),
                                                                                                  odoo_attribute.id,
                                                                                                  odoo_attribute_value=odoo_attribute_value)
                    layer_data = self.ks_map_attribute_value_data_for_layer(value_data,
                                                                            odoo_attribute,
                                                                            odoo_attribute_value, shopify_attribute.get('id'), shopify_instance)
                    layer_attribute_value = self.create(layer_data)
        except Exception as e:
            if queue_record:
                queue_record.ks_update_failed_state()
            _logger.info(str(e))

    def ks_map_attribute_value_data_for_odoo(self, value_data, attribute_id):
        data = {
            "name": value_data,
            "display_type": 'select',
            "attribute_id": attribute_id
        }
        return data

    def ks_prepare_export_json_data(self, odoo_attribute_value):
        """
        Prepares to export json data from odoo to shopify
        :return: shopify compatible data
        """
        data = {
            "name": odoo_attribute_value.name,
            # "slug": self.ks_slug if self.ks_slug else '',
        }
        return data
    
    def ks_manage_attribute_value_export(self, attribute_id, queue_record=False):
        """
        :param queue_record: Queue Boolean Trigger
        :return: json response
        """
        try:
            for attribute_value in self:
                odoo_base_attribute_value = attribute_value.ks_pro_attr_value
                shopify_attribute_id = attribute_value.ks_shopify_attribute_id or attribute_id
                shopify_attribute_value_id = attribute_value.ks_shopify_attribute_term_id
                shopify_attribute_data = attribute_value.ks_prepare_export_json_data(odoo_base_attribute_value)
                if shopify_attribute_value_id:
                    shopify_attribute_value_data_response = attribute_value.ks_shopify_update_attribute_term(shopify_attribute_id,
                                                                                          shopify_attribute_value_id,
                                                                                          shopify_attribute_data,
                                                                                          self.ks_shopify_instance)
                else:
                    shopify_attribute_value_data_response = attribute_value.ks_shopify_post_attribute_term(shopify_attribute_data,shopify_attribute_id,

                                                                                   self.ks_shopify_instance)
                if shopify_attribute_value_data_response:
                    self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(shopify_attribute_value_data_response,
                                                                                     attribute_value,
                                                                                     'ks_shopify_attribute_term_id',
                                                                                             {
                                                                                         "ks_shopify_attribute_id": shopify_attribute_id}
                                                                                     )
        except Exception as e:
            if queue_record:
                queue_record.ks_update_failed_state()

    def ks_map_attribute_value_data_for_layer(self, value_data, odoo_attribute, odoo_attribute_value, shopify_attribute_id, shopify_instance):
        data = {
                "ks_name": value_data,
                # "ks_slug": value_data.get('slug') or '',
                "ks_shopify_attribute_id": shopify_attribute_id,
                "ks_attribute_id": odoo_attribute.id,
                "ks_shopify_instance": shopify_instance.id,
                "ks_pro_attr_value": odoo_attribute_value.id,
                # "ks_shopify_attribute_term_id": value_data.get('id')

            }
        return data
