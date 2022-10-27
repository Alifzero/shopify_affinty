from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class KsShopifyCollections(models.Model):
    _name = 'ks.shopify.custom.collections'
    _description = 'Shopify Collections'
    _rec_name = 'ks_name'
    _order = 'create_date desc'

    ks_name = fields.Char(string="Collection Name", required=True, translate=True)
    ks_shopify_instance = fields.Many2one('ks.shopify.connector.instance', string="Shopify Instance")
    ks_company_id = fields.Many2one("res.company", string="Company", related="ks_shopify_instance.ks_company_id",
                                    store=True, help="Displays Company Name", readonly=True)
    ks_body = fields.Html(string="Body")
    ks_handle = fields.Char(string="Shopify Handle")
    ks_shopify_collection_id = fields.Char(string="Shopify Collection ID", readonly=True)
    ks_date_created = fields.Datetime('Date Created', help=_("The date on which the record is created on the Connected"
                                                             " Connector Instance"), readonly=True)
    ks_date_updated = fields.Datetime('Date Updated', help=_("The latest date on which the record is updated on the"
                                                             " Connected Connector Instance"), readonly=True)
    ks_product_ids = fields.Many2many('ks.shopify.product.template', string="Product Ids",
                                      domain=[('ks_shopify_product_id', 'not in', [False, 0, '0'])])
    ks_collection_condition = fields.One2many("ks.collection.conditions", "ks_collection", string="Collection String")

    def ks_manage_shopify_collections_import(self, instance, collection_data, queue_record=False):
        """
        :param instance: "ks.shopify.connector.instance"
        :param collection_data: json data from api
        :param queue_record: ks.shopify.queue.jobs
        :return: ks.shopify.custom.collections
        """
        try:
            shopify_collection = None
            collection_exist = self.search([('ks_shopify_instance', '=', instance.id),
                                            ('ks_shopify_collection_id', '=', collection_data.get('id'))])
            if collection_exist:
                shopify_collection = collection_exist.ks_update_shopify_collection(instance, collection_data)
                self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(collection_data,
                                                                                         shopify_collection,
                                                                                         'ks_shopify_collection_id')
                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='update',
                                                                       ks_status='success',
                                                                       ks_operation_flow='shopify_to_odoo',
                                                                       ks_type='collection',
                                                                       ks_shopify_instance=instance,
                                                                       ks_shopify_id=str(collection_data.get('id')),
                                                                       ks_record_id=shopify_collection.id,
                                                                       ks_message="Shopify Import Update successful",
                                                                       ks_model='ks.shopify.custom.collections')
            else:
                shopify_collection = self.ks_create_shopify_collection(instance, collection_data)
                self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(collection_data,
                                                                                         shopify_collection,
                                                                                         'ks_shopify_collection_id')
                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create',
                                                                       ks_status='success',
                                                                       ks_operation_flow='shopify_to_odoo',
                                                                       ks_type='collection',
                                                                       ks_shopify_instance=instance,
                                                                       ks_shopify_id=str(collection_data.get('id')),
                                                                       ks_record_id=shopify_collection.id,
                                                                       ks_message="Shopify Import Create successful",
                                                                       ks_model='ks.shopify.custom.collections')
            return shopify_collection
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='import',
                                                                   ks_status='failed',
                                                                   ks_operation_flow='shopify_to_odoo',
                                                                   ks_type='collection',
                                                                   ks_shopify_instance=instance,
                                                                   ks_shopify_id=str(collection_data.get(
                                                                       'id')) if collection_data else '',
                                                                   ks_record_id=0,
                                                                   ks_message="Shopify Import Failed due to %s" % str(
                                                                       e),
                                                                   ks_model='ks.shopify.custom.collections')
            if queue_record:
                queue_record.ks_update_failed_state()

    def ks_create_shopify_collection(self, instance, collection_data):
        """
        :param instance: "ks.shopify.connector.instance"
        :param collection_data: json data from api
        :return: ks.shopify.custom.collections
        """
        try:
            data = self.ks_map_collection_data_for_odoo(instance, collection_data)
            shopify_collection = self.create(data)
            return shopify_collection
        except Exception as e:
            raise e

    def ks_update_shopify_collection(self, instance, collection_data):
        """
        :param instance: "ks.shopify.connector.instance"
        :param collection_data: json data from api
        :return: ks.shopify.custom.collections
        """
        try:
            data = self.ks_map_collection_data_for_odoo(instance, collection_data)
            self.write(data)
            return self
        except Exception as e:
            raise e

    def ks_map_collection_data_for_odoo(self, instance, data):
        """
        :param instance: "ks.shopify.connector.instance"
        :param collection_data: json data from api
        :return: odoo compatible data
        """
        try:
            collect_data = self.env['ks.api.handler'].ks_get_all_data(instance,
                                                                      "collects", data.get("id"))
            shopify_product_ids = []
            product_ids = []
            if collect_data:
                for rec in collect_data:
                    if rec['collection_id'] == data.get("id"):
                        shopify_product_ids.append(rec.get('product_id'))
                product_ids_exits = self.env['ks.shopify.product.template'].search(
                        [('ks_shopify_instance', '=', instance.id),
                         ('ks_shopify_product_id', 'in', shopify_product_ids)])
                ks_exists_product = [int(i.ks_shopify_product_id) for i in product_ids_exits]
                ks_product_ids = [i for i in shopify_product_ids if i not in ks_exists_product]
                if product_ids_exits:
                    product_ids = product_ids_exits.ids
                if ks_product_ids:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='import',
                                                                           ks_status='failed',
                                                                           ks_operation_flow='shopify_to_odoo',
                                                                           ks_type='collection',
                                                                           ks_shopify_instance=instance,
                                                                           ks_shopify_id=str(
                                                                               data.get(
                                                                                   'id')) if data else '',
                                                                           ks_record_id=0,
                                                                           ks_message="Shopify import failed due to products %s does not exist." % ks_product_ids,
                                                                           ks_model='ks.shopify.custom.collections')

            ks_data = {
                'ks_shopify_collection_id': str(data.get('id', '')),
                'ks_name': data.get('title', ''),
                'ks_shopify_instance': instance.id,
                'ks_company_id': instance.ks_company_id.id,
                'ks_body': data.get('body_html', ''),
                'ks_handle': data.get('handle', ''),
                'ks_product_ids': [(6, 0, product_ids)]
            }
            all_condition = []
            if not self and data.get("rules"):
                for rec in data.get("rules"):
                    ks_condition = {
                        'ks_type': rec.get("column"),
                        'ks_relation': rec.get("relation"),
                        'ks_condition': rec.get("condition"),
                    }
                    condition_data = self.env["ks.collection.conditions"].create(ks_condition)
                    all_condition.append(condition_data.id)
            else:
                all_condition = []
                if data.get("rules"):
                    for rec in data.get("rules"):
                        for cond in self.ks_collection_condition:
                            if not (cond.ks_type == rec.get("column") and cond.ks_relation == rec.get("relation") and cond.ks_condition == rec.get("condition")):
                                ks_condition = {
                                    'ks_type': rec.get("column"),
                                    'ks_relation': rec.get("relation"),
                                    'ks_condition': rec.get("condition"),
                                }
                                condition_data = self.env["ks.collection.conditions"].create(ks_condition)
                                all_condition.append(condition_data.id)
                            else:
                                all_condition.append(cond.id)
            ks_data.update({
                'ks_collection_condition': all_condition
            })
            if instance.ks_meta_fields_map:
                meta_data = self.env['ks.shopify.meta.mapping'].get_meta_fields_data(instance=instance,
                                                                                     model='collections',
                                                                                     ids=data.get(
                                                                                         'id'),
                                                                                     ks_model='ks.shopify.custom.collections')
                ks_data.update(meta_data)
            return ks_data
        except Exception as e:
            raise e

    def ks_manage_product_collection_linkage(self, json_data):
        try:
            custom_collection_id = json_data['custom_collection']['id']

            all_retrieved_data = self.env['ks.api.handler'].ks_get_all_data(self.ks_shopify_instance, 'collections', custom_collection_id)
            exist_products = [i.get('id') for i in all_retrieved_data]
            for rec in self.ks_product_ids:
                collect = False
                product_id = int(rec.ks_shopify_product_id)
                if product_id not in exist_products:
                    collect = {"collect": {
                        "product_id": product_id,
                        "collection_id": int(custom_collection_id)
                    }}
                if collect:
                    json_response = self.env['ks.api.handler'].ks_post_data(self.ks_shopify_instance, "collects", collect)
        except Exception as e:
            raise e

    def ks_manage_shopify_collection_export(self, queue_record=False):
        """
        :param queue_record: ks.shopify.queue.jobs
        :return: api json response
        """
        try:
            if self.ks_shopify_instance and self.ks_shopify_collection_id:
                data = self.ks_map_collection_data_for_shopify()
                json_response = self.env['ks.api.handler'].ks_put_data(self.ks_shopify_instance,
                                                                       "custom_collections", data,
                                                                       self.ks_shopify_collection_id)
                if json_response:
                    if self.ks_product_ids:
                        self.ks_manage_product_collection_linkage(json_response)
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='update',
                                                                           ks_status='success',
                                                                           ks_operation_flow='wl_to_shopify',
                                                                           ks_type='collection',
                                                                           ks_shopify_instance=self.ks_shopify_instance,
                                                                           ks_shopify_id=str(
                                                                               json_response.get("custom_collection")[
                                                                                   'id']),
                                                                           ks_record_id=self.id,
                                                                           ks_message="Shopify Export Update successfull",
                                                                           ks_model='ks.shopify.custom.collections')
                    self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(
                        json_response.get("custom_collection"),
                        self,
                        'ks_shopify_collection_id')
                    return json_response.get("custom_collection")
            elif self.ks_shopify_instance and not self.ks_shopify_collection_id:
                data = self.ks_map_collection_data_for_shopify()
                json_response = self.env['ks.api.handler'].ks_post_data(self.ks_shopify_instance, "custom_collections",
                                                                        data)
                if json_response:
                    if self.ks_product_ids:
                        self.ks_manage_product_collection_linkage(json_response)
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create',
                                                                           ks_status='success',
                                                                           ks_operation_flow='wl_to_shopify',
                                                                           ks_type='collection',
                                                                           ks_shopify_instance=self.ks_shopify_instance,
                                                                           ks_shopify_id=str(
                                                                               json_response.get("custom_collection")[
                                                                                   'id']),
                                                                           ks_record_id=self.id,
                                                                           ks_message="Shopify Export Create successfull",
                                                                           ks_model='ks.shopify.custom.collections')
                    self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(
                        json_response.get("custom_collection"),
                        self,
                        'ks_shopify_collection_id')
                    return json_response.get("custom_collection")
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='export',
                                                                   ks_status='failed',
                                                                   ks_operation_flow='wl_to_shopify',
                                                                   ks_type='collection',
                                                                   ks_shopify_instance=self.ks_shopify_instance,
                                                                   ks_shopify_id='',
                                                                   ks_record_id=self.id,
                                                                   ks_message="Shopify Export Failed due to %s" % str(
                                                                       e),
                                                                   ks_model='ks.shopify.custom.collections')

            if queue_record:
                queue_record.ks_update_failed_state()

    def ks_map_collection_data_for_shopify(self):
        try:
            ks_condition_list = []
            for rec in self.ks_collection_condition:
                data = {
                    'column': rec.ks_type,
                    'relation': rec.ks_relation,
                    'condition': rec.ks_condition,
                }
                ks_condition_list.append(data)
            json_data = {
                'custom_collection': {
                    'handle': self.ks_handle or '',
                    'title': self.ks_name or ' ',
                    'body_html': self.ks_body,
                    'rules': ks_condition_list,
                }
            }
            return json_data
        except Exception as e:
            raise e

    def ks_shopify_import_collections(self):
        try:
            self = self.filtered(lambda x: x.ks_shopify_instance and x.ks_shopify_collection_id)
            if len(self) > 1:
                for rec in self:
                    collection_data = self.env['ks.api.handler'].ks_get_specific_data(rec.ks_shopify_instance,
                                                                                      "collections",
                                                                                      rec.ks_shopify_collection_id)

                    if collection_data:
                        collection_data = collection_data.get("collection")
                        self.env['ks.shopify.queue.jobs'].ks_create_collections_record_in_queue(rec.ks_shopify_instance,
                                                                                                data=collection_data)

            else:
                collection_data = self.env['ks.api.handler'].ks_get_specific_data(self.ks_shopify_instance,
                                                                                  "collections",
                                                                                  self.ks_shopify_collection_id)
                if collection_data:
                    collection_data = collection_data.get("collection")
                    custom_collection = self.ks_manage_shopify_collections_import(self.ks_shopify_instance,
                                                                                  collection_data)

        except Exception as e:
            _logger.warning("Action server import operation failed : %s" % str(e))

    def ks_shopify_export_collections(self):
        try:
            self = self.filtered(lambda x: x.ks_shopify_instance)
            if len(self) > 1:
                self.env['ks.shopify.queue.jobs'].ks_create_collections_record_in_queue(records=self)

            else:
                collection_response = self.ks_manage_shopify_collection_export()

        except Exception as e:
            _logger.warning("Action server export operation failed : %s" % str(e))


class KsCollectionCondition(models.Model):
    _name = "ks.collection.conditions"
    _description = "Contains the Product based condition for the collection"

    ks_type = fields.Selection([("title", "Title"), ("type", "Type"), ("vendor", "Vendor"),
                                ("variant_price", "Product Price"), ("tag", "Product Tag"),
                                ("variant_compare_at_price", "Compare at Price"), ("variant_weight", "Weight"),
                                ("variant_inventory", "Inventory Stock"), ("variant_title", "Variant's Title")],
                               string="Type")
    ks_relation = fields.Selection([("contains", "Contains"), ("not_contains", "Not Contains"),
                                    ("starts_with", "Starts With"), ("ends_with", "Ends With"),
                                    ("greater_than", "Greater Than"), ("less_than", "Less Than"),
                                    ("equals", "Equals"), ("not_equals", "Not Equals")], string="Relation")
    ks_condition = fields.Char("Condition")
    ks_collection = fields.Many2one("ks.shopify.custom.collections", string = "Collection")