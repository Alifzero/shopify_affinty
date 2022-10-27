from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import logging
from datetime import datetime
import pytz
import random
from string import ascii_uppercase, digits

_logger = logging.getLogger(__name__)


class KsShopifyPriceRuleDiscounts(models.Model):
    _name = 'ks.shopify.discounts'
    _description = 'Shopify Discounts'
    _rec_name = 'ks_title'
    _order = 'create_date desc'

    ks_title = fields.Char(string="Discount Code", copy=False)
    ks_shopify_instance = fields.Many2one('ks.shopify.connector.instance', string="Shopify Instance")
    ks_company_id = fields.Many2one("res.company", string="Company", related="ks_shopify_instance.ks_company_id",
                                    store=True, help="Displays Company Name", readonly=True)
    ks_shopify_discount_id = fields.Char(string="Shopify Discount ID", readonly=True, copy=False)
    ks_shopify_price_rule_id = fields.Char(string="Shopify Price Rule ID", readonly=True, copy=False)
    ks_date_created = fields.Datetime('Date Created', help=_("The date on which the record is created on the Connected"
                                                             " Connector Instance"), readonly=True)
    ks_date_updated = fields.Datetime('Date Updated', help=_("The latest date on which the record is updated on the"
                                                             " Connected Connector Instance"), readonly=True)
    ks_customer_selection = fields.Selection([('all', 'The price rule is valid for all customers'),
                                              ('prerequisite',
                                               'The customer must either belong to one of the customer saved or have ids')],
                                             string='Customer Selection', required=True)
    ks_allocation_method = fields.Selection([('each', 'The discount is applied to each of the entitled items'),
                                             ('across',
                                              'The calculated discount amount will be applied across the entitled items')],
                                            string="Allocation Method", required=True)
    ks_date_starts = fields.Datetime(string="Date Coupon Starts", required=True)
    ks_date_ends = fields.Datetime(string="Date Coupon Expires")
    ks_entitled_collection_ids = fields.Many2many('ks.shopify.custom.collections', string="Entitled Collections")
    ks_once_per_customer = fields.Boolean(string="Use once per customer ?")
    ks_entitled_customer_ids = fields.Many2many("ks.shopify.partner", string="Entitled Customers")
    ks_prereq_quantity = fields.Integer(string="Minimum Quantity of Products")
    ks_prereq_ship_price = fields.Float(string="Maximum Shipping Price")
    ks_prereq_subtotal = fields.Float(string="Minimum Subtotal")
    ks_target_selection = fields.Selection([('all', 'The price rule applies the discount to all line items'),
                                            ('entitled',
                                             'The price rule applies the discount to selected entitlements')],
                                           string="Target Selection", default='all', required=True)
    ks_target_type = fields.Selection([('line_item', 'The price rule applies to the cart line items'),
                                       ('shipping_line', 'The price rule applies to the cart shipping lines'),
                                       ], string="Target Type", required=True)
    ks_usage_limit = fields.Integer(string="Coupon Usgae Limits")
    ks_value = fields.Float(string="Amount")
    ks_value_type = fields.Selection([('fixed_amount', 'Unit Currency Amount'),
                                      ('percentage', 'Percentage Amount')], string="Amount Type",
                                     default='fixed_amount', required=True)

    @api.constrains('ks_value', 'ks_value_type')
    def _onchange_ks_value(self):
        for rec in self:
            # if rec.ks_value_type == 'percentage':
            #     if rec.ks_value < 0 or rec.ks_value > 100:
            #         raise ValidationError(_("Amount should be Greater than 0 and less than 100 !"))
            if rec.ks_value_type == 'fixed_amount':
                if rec.ks_value > 0:
                    raise ValidationError(_("Amount should be in negative for discount !"))

    @api.constrains('ks_target_type', 'ks_allocation_method', 'ks_value', 'ks_value_type', 'ks_target_selection')
    def check_allocation(self):
        if self.ks_target_type == 'shipping_line' and self.ks_allocation_method != 'each':
            raise ValidationError("""When the value of target_type is shipping_line, 
            then allocation method value must be each.""")
        if self.ks_target_type == 'shipping_line' and self.ks_value != -100:
            raise ValidationError("""The value of the price rule. If if the value of target_type is shipping_line,
             then only -100 is accepted. The value must be negative.""")
        if self.ks_target_type == 'shipping_line' and self.ks_value_type != 'percentage':
            raise ValidationError("""When Target type is shipping line only percentage is accepted as value type""")
        if self.ks_target_selection == 'all' and self.ks_allocation_method != 'across':
            raise ValidationError("""Allocation Methods must be across for target selection All""")

    def ks_manage_shopify_discounts_import(self, instance, discount_data, queue_record=False):
        """
        :param instance: ks.shopify.instance
        :param discount_data: json data from shopify
        :param queue_record: queue job record
        :return: layer discounts
        """
        try:
            discount_record = None
            discount_exist = self.search(['|', ('ks_shopify_discount_id', '=', discount_data.get("id")),
                                          ('ks_shopify_price_rule_id', '=', discount_data.get("id")),
                                          ('ks_shopify_instance', '=', instance.id)])
            if discount_exist:
                discount_record = discount_exist.ks_update_shopify_discount(instance, discount_data)
                self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(discount_data,
                                                                                         discount_record,
                                                                                         'ks_shopify_discount_id')
                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='update',
                                                                       ks_status='success',
                                                                       ks_operation_flow='shopify_to_odoo',
                                                                       ks_type='discount',
                                                                       ks_shopify_instance=instance,
                                                                       ks_shopify_id=str(discount_data.get('id')),
                                                                       ks_record_id=discount_record.id,
                                                                       ks_message="Shopify Import Update successful",
                                                                       ks_model='ks.shopify.discounts')
            else:
                discount_record = self.ks_create_shopify_discount(instance, discount_data)
                self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(discount_data,
                                                                                         discount_record,
                                                                                         'ks_shopify_discount_id')
                self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create',
                                                                       ks_status='success',
                                                                       ks_operation_flow='shopify_to_odoo',
                                                                       ks_type='discount',
                                                                       ks_shopify_instance=instance,
                                                                       ks_shopify_id=str(discount_data.get('id')),
                                                                       ks_record_id=discount_record.id,
                                                                       ks_message="Shopify Import Update successful",
                                                                       ks_model='ks.shopify.discounts')
            if discount_record:
                pricerule_discount_data = self.env['ks.api.handler'].ks_get_all_data(instance=instance,
                                                                                     domain="discount_codes",
                                                                                     ids=discount_data.get('id'))
                if pricerule_discount_data:
                    discount_record.ks_shopify_price_rule_id = pricerule_discount_data[0].get('id')
                else:
                    discount_record.ks_shopify_price_rule_id = discount_record.ks_shopify_price_rule_id
            return discount_record

        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='import',
                                                                   ks_status='failed',
                                                                   ks_operation_flow='shopify_to_odoo',
                                                                   ks_type='discount',
                                                                   ks_shopify_instance=instance,
                                                                   ks_shopify_id=str(discount_data.get('id')),
                                                                   ks_record_id=0,
                                                                   ks_message="Shopify Import Failed due to %s" % str(
                                                                       e),
                                                                   ks_model='ks.shopify.discounts')

            if queue_record:
                queue_record.ks_update_failed_state()

    def ks_create_shopify_discount(self, instance, discount_data):
        """
        :param instance: shopify instance
        :param discount_data: json api data
        :return: odoo discount record
        """
        try:
            data = self.ks_map_shopify_discount_data_for_odoo(instance, discount_data)
            shopify_discount = self.create(data)
            return shopify_discount
        except Exception as e:
            raise e

    def ks_update_shopify_discount(self, instance, discount_data):
        """
        :param instance: shopify instance
        :param discount_data: json data from shopify
        :return: layer model record
        """
        try:
            data = self.ks_map_shopify_discount_data_for_odoo(instance, discount_data)
            shopify_discount = self.write(data)
            return self
        except Exception as e:
            raise e

    def ks_map_shopify_discount_data_for_odoo(self, instance, data):
        """
        :param instance: shopify instance
        :param data: json data from shopify
        :return: mapped data odoo compatible
        """
        try:
            odoo_data = {
                "ks_title": data.get("title", ' '),
                "ks_shopify_instance": instance.id,
                "ks_shopify_discount_id": data.get("id", ' '),
                "ks_entitled_collection_ids": [(6, 0,
                                                self.ks_manage_entitled_collections(instance,
                                                                                    data.get('entitled_collection_ids',
                                                                                             [])))],
                "ks_once_per_customer": data.get("once_per_customer", False),
                "ks_entitled_customer_ids": [(6, 0,
                                              self.ks_manage_entitled_customers(instance,
                                                                                data.get('prerequisite_customer_ids',
                                                                                         [])))],
                "ks_prereq_quantity": data.get("prerequisite_quantity_range").
                    get('greater_than_or_equal_to', 0) if data.get('prerequisite_quantity_range') else False,
                "ks_prereq_ship_price": data.get("prerequisite_shipping_price_range").
                    get("less_than_or_equal_to", 0) if data.get("prerequisite_shipping_price_range") else False,
                "ks_prereq_subtotal": data.get("prerequisite_subtotal_range").
                    get("greater_than_or_equal_to") if data.get("prerequisite_subtotal_range") else False,
                "ks_target_selection": data.get("target_selection", False),
                "ks_target_type": data.get("target_type", False),
                "ks_usage_limit": data.get("usage_limit", 0),
                "ks_value": data.get("value", 0.0),
                'ks_customer_selection': data.get('customer_selection'),
                'ks_allocation_method': data.get('allocation_method'),
                "ks_value_type": data.get("value_type", False)
            }
            if data.get("starts_at") or data.get("ends_at"):
                converted_time = self.env['ks.shopify.connector.instance'].ks_convert_datetime(
                    {"starts_at": data.get("starts_at", False),
                     "ends_at": data.get("ends_at", False)})
                if converted_time:
                    odoo_data.update({
                        'ks_date_starts': converted_time.get("starts_at", False),
                        'ks_date_ends': converted_time.get("ends_at", False)
                    })
            return odoo_data
        except Exception as e:
            raise e

    def ks_manage_entitled_collections(self, instance, ids):
        """
        :param instance: shopify instance
        :param ids: shopify ids
        :return: collections odoo ids
        """
        try:
            odoo_ids = []
            collections_data = {}
            for id in ids:
                collections_data = self.env['ks.api.handler'].ks_get_specific_data(instance, 'collections', id)
                if collections_data:
                    collections_data = collections_data.get("collection", {})
                if collections_data:
                    custom_collection = self.env['ks.shopify.custom.collections'].ks_manage_shopify_collections_import(
                        instance, collections_data
                    )
                    if custom_collection:
                        odoo_ids.append(custom_collection.id)

            return odoo_ids
        except Exception as e:
            raise e

    def ks_manage_entitled_customers(self, instance, ids):
        """
        :param instance: shopify instance
        :param ids: json ids for shopify
        :return: odoo ids
        """
        try:
            odoo_ids = []
            for id in ids:
                customer_data = self.env['ks.api.handler'].ks_get_specific_data(instance, 'customers', id)
                customer_data = customer_data.get("customer", {})
                if customer_data:
                    shopify_customer = self.env['ks.shopify.partner'].ks_manage_shopify_customer_import(instance,
                                                                                                        customer_data)
                    if shopify_customer:
                        layer_partner = shopify_customer.ks_partner_shopify_ids.filtered(
                            lambda x: x.ks_shopify_instance.id == instance.id)
                        odoo_ids.append(layer_partner.id)
            return odoo_ids
        except Exception as e:
            raise e

    def ks_manage_shopify_discounts_export(self, queue_record=False):
        """
        :param queue_record: queue job record refrence
        :return: json response
        """
        try:
            json_response = None
            if self.ks_shopify_instance and self.ks_shopify_discount_id:
                data = self.ks_map_discount_data_for_shopify()
                json_response = self.env['ks.api.handler'].ks_put_data(self.ks_shopify_instance,
                                                                       "price_rules", data,
                                                                       self.ks_shopify_discount_id)
                if json_response:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='update',
                                                                           ks_status='success',
                                                                           ks_operation_flow='wl_to_shopify',
                                                                           ks_type='discount',
                                                                           ks_shopify_instance=self.ks_shopify_instance,
                                                                           ks_shopify_id=str(
                                                                               json_response.get('price_rule')['id']),
                                                                           ks_record_id=self.id,
                                                                           ks_message="Shopify Export Update successfull",
                                                                           ks_model='ks.shopify.discounts')
                    return json_response.get('price_rule')
            elif self.ks_shopify_instance and not self.ks_shopify_price_rule_id:
                data = self.ks_map_discount_data_for_shopify()
                json_response = self.env['ks.api.handler'].ks_post_data(self.ks_shopify_instance, "price_rules", data)
                if json_response:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='create',
                                                                           ks_status='success',
                                                                           ks_operation_flow='wl_to_shopify',
                                                                           ks_type='discount',
                                                                           ks_shopify_instance=self.ks_shopify_instance,
                                                                           ks_shopify_id=str(
                                                                               json_response.get('price_rule')['id']),
                                                                           ks_record_id=self.id,
                                                                           ks_message="Shopify Export Create successfull",
                                                                           ks_model='ks.shopify.discounts')
                    self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(
                        json_response.get("price_rule"),
                        self,
                        'ks_shopify_discount_id')
                    data = {
                        'discount_code': {
                            # 'price_rule_id': json_response.get('price_rule')['id'],
                            'code': self.ks_title,
                        }
                    }
                    discount_json_response = self.env['ks.api.handler'].ks_post_data(self.ks_shopify_instance,
                                                                                     "discount_codes",
                                                                                     data,
                                                                                     json_response.get('price_rule')[
                                                                                         'id'])
                    self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(
                        discount_json_response.get("discount_code"),
                        self,
                        'ks_shopify_price_rule_id')
                    return json_response.get('price_rule')
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed='export',
                                                                   ks_status='failed',
                                                                   ks_operation_flow='wl_to_shopify',
                                                                   ks_type='discount',
                                                                   ks_shopify_instance=self.ks_shopify_instance,
                                                                   ks_shopify_id='',
                                                                   ks_record_id=self.id,
                                                                   ks_message="Shopify Export Update Failed because of : %s" % str(
                                                                       e),
                                                                   ks_model='ks.shopify.discounts')

            if queue_record:
                queue_record.ks_update_failed_state()

    def ks_export_to_shopify(self):
        if not self:
            self = self.search([])
        for rec in self:
            self.env['ks.shopify.queue.jobs'].ks_create_discount_record_in_queue(rec.ks_shopify_instance,
                                                                                 records=rec)

    def ks_map_discount_data_for_shopify(self):
        """
        :return: json data shopify compatible
        """
        try:
            data = {'price_rule': {
                'title': self.ks_title or '',
                'value': "-%s" % str(abs(self.ks_value)) or None,
                'entitled_collection_ids': self.ks_manage_entitled_collections_export(),
                'once_per_customer': self.ks_once_per_customer,
                'prerequisite_customer_ids': self.ks_manage_prequisite_customers_export(),
                'prerequisite_quantity_range': {
                    'greater_than_or_equal_to': str(self.ks_prereq_quantity)} if self.ks_prereq_quantity else None,
                'prerequisite_shipping_price_range': {
                    'less_than_or_equal_to': str(self.ks_prereq_ship_price)} if self.ks_prereq_ship_price else None,
                'prerequisite_subtotal_range': {
                    'greater_than_or_equal_to': str(self.ks_prereq_subtotal)} if self.ks_prereq_subtotal else None,
                'target_selection': self.ks_target_selection or 'all',
                'target_type': self.ks_target_type or None,
                'usage_limit': self.ks_usage_limit or None,
                'value_type': self.ks_value_type or 'fixed_amount',
                'allocation_method': self.ks_allocation_method,
                'customer_selection': self.ks_customer_selection
            }}
            if self.ks_date_starts:
                date_time = self.ks_date_starts.strftime("%Y-%m-%d %H:%M:%S")
                date_time = datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S").astimezone(
                    pytz.timezone(self.env.user.tz or "UTC")).isoformat()
                data['price_rule'].update({'starts_at': date_time})
            if self.ks_date_ends:
                date_time = self.ks_date_ends.strftime("%Y-%m-%d %H:%M:%S")
                date_time = datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S").astimezone(
                    pytz.timezone(self.env.user.tz or "UTC")).isoformat()
                data['price_rule'].update({'ends_at': date_time})
            return data
        except Exception as e:
            raise e

    def ks_manage_entitled_collections_export(self):
        """
        :return: list of ids of exported collections
        """
        try:
            shopify_collections_ids = []
            for coll in self.ks_entitled_collection_ids:
                json_response = coll.ks_manage_shopify_collection_export()
                if json_response:
                    id = json_response.get('id')
                    shopify_collections_ids.append(id)
            return shopify_collections_ids
        except Exception as e:
            raise e

    def ks_manage_prequisite_customers_export(self):
        """
        :return: list of ids of exported customers
        """
        try:
            shopify_customer_ids = []
            for customer in self.ks_entitled_customer_ids:
                json_response = customer.ks_manage_shopify_customer_export()
                if json_response:
                    id = json_response.get("id")
                    shopify_customer_ids.append(id)
            return shopify_customer_ids
        except Exception as e:
            raise e

    def ks_generate_code(self):
        def ks_code_gen():
            code = [random.choice(ascii_uppercase + digits) for _ in range(12)]
            code = ''.join(code)
            return code

        code = ks_code_gen()
        search_code = self.search([('ks_title', '=', code)])
        if search_code:
            code = ks_code_gen()
        self.write({'ks_title': code})
