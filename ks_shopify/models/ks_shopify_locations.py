# -*- coding: utf-8 -*-

from odoo import api, fields, models


class KsShopifyLocations(models.Model):
    _name = "ks.shopify.locations"
    _description = "List of Shopify Warehouse/Locations"
    _rec_name = "ks_name"

    # ks_stock_location = fields.One2many('stock.location', 'ks_shopify_location', string="Stock Location")
    ks_shopify_location_id = fields.Char("Id")
    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Shopify Instance", help="Displays Shopify Instance Name")
    ks_name = fields.Char("Name")
    ks_address1 = fields.Char("Address 1")
    ks_address2 = fields.Char("Address 2")
    ks_city = fields.Char("City")
    ks_zip = fields.Char("ZIP")
    ks_province = fields.Char("Province")
    ks_country = fields.Many2one('res.country', 'Country')
    ks_phone = fields.Char("Phone")
    ks_created_at = fields.Datetime("Created At")
    ks_updated_at = fields.Datetime("Updated At")
    ks_active = fields.Boolean("Active")

    def ks_manage_shopify_locations_import(self, instance, location_data, queue_record=False):
        """
        :param instance: ks.shopify.instance
        :param location_data: json data from shopify
        :param queue_record: queue job record
        :return: layer discounts
        """
        try:
            location_exist = self.search([('ks_shopify_instance', '=', instance.id),
                                          ('ks_shopify_location_id', '=', location_data.get("id"))])
            location_record = self.ks_map_shopify_locations_data_for_odoo(instance, location_data)
            if location_exist:
                location_exist.update(location_record)
                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='update',
                                                                       ks_status='success',
                                                                       ks_operation_flow='shopify_to_odoo',
                                                                       ks_type='locations',
                                                                       ks_shopify_instance=instance,
                                                                       ks_shopify_id=str(location_data.get('id')),
                                                                       ks_record_id=location_exist.id,
                                                                       ks_message="Shopify Import Update successful",
                                                                       ks_model='ks.shopify.locations')
            else:
                location_exist = self.create(location_record)
                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create',
                                                                       ks_status='success',
                                                                       ks_operation_flow='shopify_to_odoo',
                                                                       ks_type='locations',
                                                                       ks_shopify_instance=instance,
                                                                       ks_shopify_id=str(location_data.get('id')),
                                                                       ks_record_id=location_exist.id,
                                                                       ks_message="Shopify Import Update successful",
                                                                       ks_model='ks.shopify.locations')
            return location_exist
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='import',
                                                                   ks_status='failed',
                                                                   ks_operation_flow='shopify_to_odoo',
                                                                   ks_type='locations',
                                                                   ks_shopify_instance=instance,
                                                                   ks_shopify_id=str(location_data.get('id')),
                                                                   ks_record_id=0,
                                                                   ks_message="Shopify Import Failed due to %s" % str(
                                                                       e),
                                                                   ks_model='ks.shopify.locations')
            if queue_record:
                queue_record.ks_update_failed_state()


    def ks_map_shopify_locations_data_for_odoo(self, instance, data):
        """
        :param instance: shopify instance
        :param data: json data from shopify
        :return: mapped data odoo compatible
        """
        try:
            odoo_data = {
                "ks_name": data.get("name", ' '),
                "ks_active": data.get("active", ' '),
                "ks_shopify_location_id": data.get("id", ' '),
                "ks_shopify_instance": instance.id,
                "ks_address1": data.get("address1", ' '),
                "ks_address2": data.get("address2", ' '),
                "ks_city": data.get("city", ' '),
                "ks_zip": data.get("zip", ' '),
                "ks_province": data.get("province", ' '),
                "ks_country": self.env['res.country'].search([('code', '=', data.get("country_code", ' '))], limit=1).id,
                "ks_phone": data.get("phone", ' '),
                "ks_created_at": instance.ks_convert_datetime({'created_at': data.get('created_at')}).get(
                        'created_at'),
                "ks_updated_at": instance.ks_convert_datetime({'update_date': data.get('updated_at')}).get(
                        'update_date'),
            }
            return odoo_data
        except Exception as e:
            raise e
