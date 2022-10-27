from odoo import fields, models, api
from odoo.exceptions import ValidationError
from datetime import datetime
import pytz
import json


class KsWooMetaMapping(models.Model):
    _name = "ks.shopify.meta.mapping"
    _description = "Shopify Meta Mapping"
    _rec_name = "ks_meta_key"

    ks_model_id = fields.Many2one("ir.model", string="Shopify Model", help="Displays odoo default models",
                                  domain="[('model', 'in', ['product.product','product.template','sale.order','res.partner','ks.shopify.custom.collections'])]")
    ks_meta_key = fields.Char(string="Shopify Meta Key", required=True, help="Displays the Shopify ID")
    ks_fields = fields.Many2one("ir.model.fields", string="Meta Mapping Field",
                                domain="[('model_id', '=', ks_model_id)]", help="Displays fields of the particular selected model")
    ks_active = fields.Boolean(string="Active", help="Enables/Disables state")
    ks_shopify_instance_id = fields.Many2one("ks.shopify.connector.instance", string="Instance Id")

    @api.constrains("ks_model_id", "ks_fields")
    def _check_null_values(self):
        if not self.ks_fields or not self.ks_model_id:
            raise ValidationError("Either of Model or Fields is Empty")

    def get_meta_fields_data(self, instance, ids=False, additional_id=None, model=None, ks_model=None):
        meta_data = False
        meta_maps_ids = instance.ks_meta_mapping_ids.search([('ks_shopify_instance_id', '=', instance.id),
                                                            ('ks_active', '=', True),
                                                            ('ks_model_id.model', '=', ks_model)])

        if meta_maps_ids:
            meta_data = self.env['ks.api.handler'].ks_get_all_data(instance=instance,
                                                                   domain="metafields",
                                                                   ids=ids,
                                                                   additional_id=additional_id,
                                                                   model=model)

        data = {}
        for ks_map in meta_maps_ids:
            odoo_field = ks_map.ks_fields.name
            json_key = ks_map.ks_meta_key
            for meta in meta_data:
                if meta.get('key', '') == json_key:
                    value = self.get_meta_value(meta, ks_map.ks_fields)
                    if odoo_field == 'barcode':
                        domain = False
                        if ks_model == 'product.template':
                            domain = [('ks_shopify_product_template.ks_shopify_product_id', '!=', ids),
                                      ('barcode', '=', value if value else meta.get('value', ''))]
                        elif ks_model == 'product.product':
                            domain = [('ks_shopify_product_variant.ks_shopify_variant_id', '!=', ids),
                                      ('barcode', '=', value if value else meta.get('value', ''))]
                        if self.env[ks_model].search_count(domain):
                            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                                   ks_model=ks_model,
                                                                                   ks_layer_model='ks.shopify.meta.mapping',
                                                                                   ks_message='Duplicate Barcode Exists',
                                                                                   ks_status="failed",
                                                                                   ks_type="product",
                                                                                   ks_record_id=0,
                                                                                   ks_operation_flow="shopify_to_odoo",
                                                                                   ks_shopify_id=ids,
                                                                                   ks_shopify_instance=instance)
                            return False
                    data.update({
                        odoo_field: value if value else meta.get('value', '')
                    })
        return data

    def get_meta_value(self, meta, odoo_fields):
        if odoo_fields.ttype == 'float' and meta.get('type') in ['number_decimal', 'number_integer']:
            return float(meta.get('value', ''))
        if odoo_fields.ttype == 'integer' and meta.get('type') in ['number_decimal', 'number_integer']:
            return int(meta.get('value', ''))
        if odoo_fields.ttype == 'datetime' and meta.get('type') == 'date_time':
            return str(datetime.fromisoformat(meta.get('value', '')[:-1]))
        if meta.get('type') == 'rating':
            value = float(json.loads(meta.get('value')).get('value'))
            return value
        return False
