# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class KsShopifyResPartner(models.Model):
    _name = "ks.shopify.partner"
    _rec_name = "ks_res_partner"
    _description = "Custom Partner to Connect Multiple Connectors"
    _order = 'create_date desc'

    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Instance", readonly=True,
                                          help=_("Shopify Connector Instance reference"),
                                          ondelete='cascade')
    ks_shopify_order = fields.Many2one('sale.order', string='Shopify Order')
    ks_shopify_partner_id = fields.Char(string="Shopify Customer ID", readonly=True,
                                           help=_("the record id of the customer record defined in the Connector"))
    ks_res_partner = fields.Many2one("res.partner", string="Odoo Partner", readonly=True, ondelete='cascade',
                                     help="Displays Odoo related record name")
    ks_company_id = fields.Many2one("res.company", string="Company", compute="_compute_company", store=True,
                                    help="Displays Company Name")
    ks_date_created = fields.Datetime(string="Date Created", help=_("The date on which the record is created on the "
                                                                    "Connected Connector Instance"), readonly=True)
    ks_date_updated = fields.Datetime(string="Date Updated", help=_("The latest date on which the record is updated on"
                                                                    " the Connected Connector Instance"), readonly=True)
    # ks_username = fields.Char(string="Username", readonly=True)
    ks_mapped = fields.Boolean(string="Manually Mapped", readonly=True)
    ks_order_count = fields.Integer(string='Order Count', readonly=True)
    ks_total_spent = fields.Float(string='Order Total Spent', readonly=True)
    ks_email_verified = fields.Boolean(string="Email Verified", readonly=True)
    ks_note = fields.Char(string="Note")
    ks_tags = fields.Char(string="Tags")
    ks_type = fields.Selection([('customer', 'Customer'), ('address', 'Address')], string="Type", readonly=True)

    @api.depends('ks_res_partner')
    def _compute_company(self):
        """
        Computes company for the res partner to be created on odoo layer
        :return:
        """
        for rec in self:
            if rec.ks_shopify_instance.ks_company_id:
                rec.ks_company_id = rec.ks_shopify_instance.ks_company_id.id
            else:
                rec.ks_company_id = self._context.get('company_id', self.env.company.id)

    def ks_auto_import_shopify_customer(self, cron_id=False):
        try:
            if not cron_id:
                if self._context.get('params'):
                    cron_id = self.env["ir.cron"].browse(self._context.get('params').get('id'))
            else:
                cron_id = self.env["ir.cron"].browse(cron_id)
            instance_id = cron_id.ks_shopify_instance
            if instance_id and instance_id.ks_instance_state == 'active':
                # order_status = ','.join(instance_id.ks_order_status.mapped('status'))
                customer_json_records = self.ks_shopify_get_all_customers(
                    instance=instance_id)
                for customer_data in customer_json_records:
                    self.ks_manage_shopify_customer_import(instance_id, customer_data)
        except Exception as e:
            _logger.info(str(e))

    def check_if_already_prepared(self, instance, res_partner):
        """
        Checks if the record is already prepared to export
        :param instance: shopifycommerce Instance
        :param res_partner: res partner domain
        :return: customer exist domain
        """
        customer_exist = self.search([('ks_shopify_instance', '=', instance.id),
                                      ('ks_res_partner', '=', res_partner.id)], limit=1)
        if customer_exist:
            return customer_exist
        else:
            return False

    def create_shopify_record(self, instance, res_partner, export_to_shopify=False, queue_record=False, generic_wizard=False):
        """
        Use: Prepare the main Record for Shopify Partner Layer Model with specific Instance
        :param instance: ks.shopify.instance()
        :param res_partner: res.partner()
        :return: ks.shopify.partner() if created.
        """
        try:
            customer_exist = self.search([('ks_shopify_instance', '=', instance.id),
                                          ('ks_res_partner', '=', res_partner.id)])
            if not customer_exist:
                data = self.ks_map_prepare_data_for_layer(res_partner, instance, generic_wizard=generic_wizard)
                layer_customer = self.create(data)
                if layer_customer.ks_res_partner.child_ids:
                    for customer_data in layer_customer.ks_res_partner.child_ids:
                        data = {
                            "ks_shopify_instance": instance.id,
                            "ks_res_partner": customer_data.id,
                            "ks_type": 'address',
                        }
                        child_customer = self.create(data)
                if export_to_shopify:
                    try:
                        layer_customer.ks_manage_shopify_customer_export()
                    except Exception as e:
                        _logger.info(str(e))
                self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_create",
                                                                           status="success",
                                                                           type="customer",
                                                                           instance=instance,
                                                                           odoo_model="res.partner",
                                                                           layer_model="ks.shopify.partner",
                                                                           id=res_partner.id,
                                                                           message="Layer preparation Success")
                return layer_customer

        except Exception as e:
            if queue_record:
                queue_record.ks_update_failed_state()

            self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_create",
                                                                       status="failed",
                                                                       type="customer",
                                                                       instance=instance,
                                                                       odoo_model="res.partner",
                                                                       layer_model="ks.shopify.partner",
                                                                       id=res_partner.id,
                                                                       message=str(e))

    def update_shopify_record(self, instance, res_partner, update_to_shopify=False, queue_record=False, generic_wizard=False):
        """
        Prepare the main Record for Shopify Partner Layer Model with specific Instance
        :param instance: ks.shopify.instance()
        :param res_partner: res.partner()
        :return: ks.shopify.partner() if created.
        """
        try:
            customer_exist = self.search([('ks_shopify_instance', '=', instance.id),
                                          ('ks_res_partner', '=', res_partner.id)])
            if customer_exist:
                data = self.ks_map_prepare_data_for_layer(res_partner, instance, generic_wizard=generic_wizard)
                customer_exist.write(data)
                if update_to_shopify:
                    try:
                        customer_exist.ks_manage_shopify_customer_export()
                    except Exception as e:
                        _logger.info(str(e))
                self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_update",
                                                                           status="success",
                                                                           type="customer",
                                                                           instance=instance,
                                                                           odoo_model="res.partner",
                                                                           layer_model="ks.shopify.partner",
                                                                           id=res_partner.id,
                                                                           message="Layer preparation Success")
                return customer_exist

        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_prepare_log_params(operation_performed="prepare_update",
                                                                       status="failed",
                                                                       type="customer",
                                                                       instance=instance,
                                                                       odoo_model="res.partner",
                                                                       layer_model="ks.shopify.partner",
                                                                       id=res_partner.id,
                                                                       message=str(e))

            if queue_record:
                queue_record.ks_update_failed_state()

    def ks_map_prepare_data_for_layer(self, res_partner, instance, json_data=False, generic_wizard=False):
        """
        :param res_partner: res.partner()
        :param instance: ks.shopify.connector.instance()
        :return: layer compatible data
        """
        data = {
            "ks_shopify_instance": instance.id,
            "ks_res_partner": res_partner.id,
            "ks_type": 'customer',
        }
        if generic_wizard:
            data.update({
                'ks_note': generic_wizard.ks_note,
                'ks_tags': generic_wizard.ks_tags,
            })
        if json_data:
            data.update({'ks_order_count': json_data.get('orders_count'),
                         'ks_total_spent': json_data.get('total_spent'),
                         'ks_email_verified': json_data.get('verified_email'),
                         'ks_note': json_data.get('note'),
                         'ks_tags': json_data.get('tags'),
                         })
            if json_data.get('last_order_name'):
                order_exist = self.env['sale.order'].search([('ks_order_name', '=', json_data.get('last_order_name')), ('ks_shopify_instance', '=', instance.id)])
                if order_exist:
                    data.update({
                        'ks_shopify_order': order_exist.id
                    })
        # if json_data:
        #     data.update({"ks_username": json_data.get('email', '')})
        return data

    def create_layer_partner(self, odoo_partner, instance, json_data):
        """
        :param odoo_partner: res.partner()
        :param instance: ks.shopify.connector.instance()
        :return: ks.shopify.partner()
        """
        try:
            if odoo_partner and instance:
                layer_data = self.ks_map_prepare_data_for_layer(odoo_partner, instance, json_data)
                layer_partner = self.create(layer_data)
                return layer_partner

        except Exception as e:
            raise e

    def update_layer_partner(self, odoo_partner, instance, json_data):
        """
        :param odoo_partner: res.partner()
        :param instance: ks.shopify.connector.instance()
        :return: ks.shopify.partner()
        """
        try:
            if odoo_partner and instance:
                layer_data = self.ks_map_prepare_data_for_layer(odoo_partner, instance, json_data)
                self.write(layer_data)
                return self
        except Exception as e:
            raise e

    def ks_shopify_import_customers(self):
        if len(self) > 1:
            try:
                records = self.filtered(lambda e: e.ks_shopify_instance and e.ks_shopify_partner_id)
                if len(records):
                    for dat in records:
                        json_data = [self.ks_shopify_get_customer(dat.ks_shopify_partner_id, dat.ks_shopify_instance)]
                        if json_data[0]:
                            self.env['ks.shopify.queue.jobs'].ks_create_customer_record_in_queue(data=json_data,
                                                                                                 instance=dat.ks_shopify_instance)
                    return self.env['ks.message.wizard'].ks_pop_up_message("success",
                                                                           '''Customers Records enqueued in Queue 
                                                                              Please refer Queue and logs for further details
                                                                              ''')
            except Exception as e:
                raise e

        else:
            try:
                self.ensure_one()
                if self.ks_shopify_partner_id and self.ks_shopify_instance:
                    json_data = self.ks_shopify_get_customer(self.ks_shopify_partner_id, self.ks_shopify_instance)
                    if json_data:
                        self.ks_manage_shopify_customer_import(self.ks_shopify_instance, json_data)
            except Exception as e:
                raise e

    def ks_shopify_export_customers(self):
        if len(self) > 1:
            try:
                records = self.filtered(lambda e: e.ks_shopify_instance)
                if len(records):
                    self.env['ks.shopify.queue.jobs'].ks_create_customer_record_in_queue(records=records)
                    return self.env['ks.message.wizard'].ks_pop_up_message("success",
                                                                           '''Customers Records enqueued in Queue 
                                                                              Please refer Queue and logs for further details
                                                                              ''')
            except Exception as e:
                raise e
        else:
            try:
                self.ensure_one()
                if self.ks_shopify_instance:
                    self.ks_manage_shopify_customer_export()
            except Exception as e:
                raise e

    def ks_manage_shopify_customer_import(self, instance, partner_json, queue_record=False):
        """
        :param instance: ks.shopify.connector.instance()
        :param partner_json: json data for Shopify about customer
        :param queue_record: Boolean Trigger for queue job
        :return: res.partner()
        """
        try:
            partner_exist = self.search([('ks_shopify_instance', '=', instance.id),
                                         ('ks_shopify_partner_id', '=', partner_json.get("id"))])
            odoo_partner = None
            if partner_exist:
                try:
                    main_partner_data = self.env['res.partner'].ks_map_shopify_odoo_partner_data_to_create(partner_json,
                                                                                                   partner_exist,
                                                                                                   instance=instance)
                    odoo_partner = partner_exist.ks_res_partner.ks_odoo_customer_update(partner_exist.ks_res_partner,
                                                                                        main_partner_data)
                    shopify_partner = partner_exist.update_layer_partner(odoo_partner, instance, partner_json)
                    self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(partner_json,
                                                                                             shopify_partner,
                                                                                             'ks_shopify_partner_id')
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                           ks_shopify_id=partner_json.get("id", 0),
                                                                           ks_model="res.partner",
                                                                           ks_layer_model="ks.shopify.partner",
                                                                           ks_status="success",
                                                                           ks_shopify_instance=instance,
                                                                           ks_record_id=shopify_partner.id,
                                                                           ks_message="Customer import update success",
                                                                           ks_type="customer",
                                                                           ks_operation_flow="shopify_to_odoo")
                except Exception as e:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                           ks_shopify_id=partner_json.get("id", 0),
                                                                           ks_model="res.partner",
                                                                           ks_layer_model="ks.shopify.partner",
                                                                           ks_status="failed",
                                                                           ks_shopify_instance=instance,
                                                                           ks_record_id=0,
                                                                           ks_message=str(e),
                                                                           ks_type="customer",
                                                                           ks_operation_flow="shopify_to_odoo")
                return odoo_partner

            else:
                try:
                    main_partner_data = self.env['res.partner'].ks_map_shopify_odoo_partner_data_to_create(partner_json,
                                                                                                   instance=instance)
                    odoo_partner = self.env['res.partner'].ks_odoo_customer_create(main_partner_data)
                    shopify_partner = self.create_layer_partner(odoo_partner, instance, partner_json)
                    self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(partner_json,
                                                                                             shopify_partner,
                                                                                             'ks_shopify_partner_id')
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                           ks_shopify_id=partner_json.get("id", 0),
                                                                           ks_model="res.partner",
                                                                           ks_layer_model="ks.shopify.partner",
                                                                           ks_status="success",
                                                                           ks_shopify_instance=instance,
                                                                           ks_record_id=shopify_partner.id,
                                                                           ks_message="Customer import create success",
                                                                           ks_type="customer",
                                                                           ks_operation_flow="shopify_to_odoo")
                except Exception as e:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                           ks_shopify_id=partner_json.get("id", 0),
                                                                           ks_model="res.partner",
                                                                           ks_layer_model="ks.shopify.partner",
                                                                           ks_status="failed",
                                                                           ks_shopify_instance=instance,
                                                                           ks_record_id=0,
                                                                           ks_message=str(e),
                                                                           ks_type="customer",
                                                                           ks_operation_flow="shopify_to_odoo")

                return odoo_partner

        except Exception as e:
            if queue_record:
                queue_record.ks_update_failed_state()
            raise e

    def ks_manage_shopify_customer_export(self, queue_record=False):
        """
        :param queue_record: Boolean Trigger for queue jobs
        :return: partner json response
        """
        try:
            shopify_customer_data_response = None
            odoo_base_partner = self.ks_res_partner
            instance = self.ks_shopify_instance
            if self.ks_shopify_partner_id and instance and odoo_base_partner and self.ks_type =='customer':
                try:
                    data = odoo_base_partner.ks_prepare_data_to_export_put(self)
                    shopify_customer_data_response = self.ks_shopify_update_customer(self.ks_shopify_partner_id,
                                                                                     data,
                                                                                     instance)
                    for rec in odoo_base_partner.child_ids:
                        ks_partner_shopify_id = rec.ks_partner_shopify_ids.filtered(lambda x: x.ks_shopify_instance == self.ks_shopify_instance)
                        if rec.ks_partner_shopify_ids and ks_partner_shopify_id.ks_shopify_partner_id:
                            odoo_base_partner.ks_update_partner_address(odoo_base_partner, rec, instance)
                        elif rec.ks_partner_shopify_ids and not ks_partner_shopify_id.ks_shopify_partner_id:
                            all_retrieved_data = odoo_base_partner.ks_create_partner_address(odoo_base_partner, rec,
                                                                                             instance)
                            if all_retrieved_data:
                                self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(
                                    all_retrieved_data.get('customer_address'),
                                    rec.ks_partner_shopify_ids,
                                    'ks_shopify_partner_id',
                                )
                        else:
                            address_data = {
                                'ks_company_id': self.env.company.id,
                                'ks_res_partner': rec.id,
                                'ks_shopify_instance': instance.id,
                            }
                            ks_address = self.env['ks.shopify.partner'].create(address_data)
                            all_retrieved_data = odoo_base_partner.ks_create_partner_address(odoo_base_partner, rec, instance)
                            if all_retrieved_data:
                                self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(
                                    all_retrieved_data.get('customer_address'),
                                    ks_address,
                                    'ks_shopify_partner_id',
                                )
                    if shopify_customer_data_response:
                        self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(
                            shopify_customer_data_response,
                            self,
                            'ks_shopify_partner_id')
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                               ks_shopify_id=shopify_customer_data_response.get(
                                                                                   "id", 0),
                                                                               ks_model="res.partner",
                                                                               ks_layer_model="ks.shopify.partner",
                                                                               ks_status="success",
                                                                               ks_shopify_instance=instance,
                                                                               ks_message="Customer Export update success",
                                                                               ks_record_id=self.id,
                                                                               ks_type="customer",
                                                                               ks_operation_flow="odoo_to_shopify")
                except Exception as e:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="update",
                                                                           ks_shopify_id=0,
                                                                           ks_model="res.partner",
                                                                           ks_layer_model="ks.shopify.partner",
                                                                           ks_status="failed",
                                                                           ks_shopify_instance=instance,
                                                                           ks_record_id=self.id,
                                                                           ks_message=str(e),
                                                                           ks_type="customer",
                                                                           ks_operation_flow="odoo_to_shopify")

            elif not self.ks_shopify_partner_id and instance and odoo_base_partner and self.ks_type=='customer':
                try:
                    data = odoo_base_partner.ks_prepare_data_to_export_post(self)
                    shopify_customer_data_response = self.ks_shopify_post_customer(data, instance)
                    if shopify_customer_data_response:
                        self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(
                            shopify_customer_data_response,
                            self,
                            'ks_shopify_partner_id',
                        )
                        for rec in shopify_customer_data_response.get('addresses'):
                            ks_response = self.ks_partner_data_exists_on_odoo(rec, instance)
                            self.env['ks.shopify.connector.instance'].ks_shopify_update_the_response(
                                rec,
                                ks_response,
                                'ks_shopify_partner_id',
                            )
                        self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                               ks_shopify_id=shopify_customer_data_response.get(
                                                                                   "id", 0),
                                                                               ks_model="res.partner",
                                                                               ks_layer_model="ks.shopify.partner",
                                                                               ks_status="success",
                                                                               ks_shopify_instance=instance,
                                                                               ks_record_id=self.id,
                                                                               ks_message="Customer export create success",
                                                                               ks_type="customer",
                                                                               ks_operation_flow="odoo_to_shopify")
                except Exception as e:
                    self.env['ks.shopify.logger'].ks_create_odoo_log_param(ks_operation_performed="create",
                                                                           ks_shopify_id=0,
                                                                           ks_model="res.partner",
                                                                           ks_layer_model="ks.shopify.partner",
                                                                           ks_status="failed",
                                                                           ks_shopify_instance=instance,
                                                                           ks_record_id=self.id,
                                                                           ks_message=str(e),
                                                                           ks_type="customer",
                                                                           ks_operation_flow="odoo_to_shopify")

            return shopify_customer_data_response

        except Exception as e:
            if queue_record:
                queue_record.ks_update_failed_state()
            raise e

    def ks_partner_data_exists_on_odoo(self, address, instance):
        address_data_exists = self.ks_res_partner.search([('name', '=', str(
            address.get('first_name').replace(" ", "")) + str(
            address.get('last_name').replace(" ", ""))),
                                                          ('street', '=',
                                                           address.get('address1')),
                                                          ('street2', '=',
                                                           address.get('address2')),
                                                          ('city', '=', address.get('city')), (
                                                              'country_id.code', '=',
                                                              address.get('country_code')), (
                                                              'state_id.code', '=',
                                                              address.get('province_code'))])
        if not address_data_exists.ks_partner_shopify_ids:
            ks_layer_data = {
                "ks_shopify_instance": instance.id,
                "ks_res_partner": address_data_exists.id,
                "ks_shopify_partner_id": address.get('id'),
                "ks_type": 'address',
            }
            address_data_exists.ks_partner_shopify_ids.sudo().create(ks_layer_data)
        return address_data_exists

    def ks_get_first_last_name(self, name):
        """
        :param name: str
        :return: str
        """
        first_name = last_name = ""
        list_name = []
        if name:
            list_name = name.split()
        if len(list_name):
            if len(list_name) == 1:
                first_name = ''.join(list_name[0])
                last_name = ""
                return first_name, last_name
            else:
                first_name = ' '.join(list_name[0:-1])
                last_name = ''.join(list_name[-1])
                return first_name, last_name
        return first_name, last_name

    def ks_prepare_export_json_data(self, customer=False):
        """
        Use: This will prepare the Shopify Partner Layer Model data for Shopify
        :return: dict of prepared data
        """
        odoo_partner = self.ks_res_partner if not customer else customer
        first_name, last_name = self.ks_get_first_last_name(odoo_partner.name)
        data = {
            "email": odoo_partner.email or '',
            "first_name": first_name,
            "last_name": last_name,
        }
        # address_dict = self.ks_res_partner.address_get(['invoice', 'delivery'])
        address_dict = odoo_partner.address_get(['invoice', 'delivery'])
        if address_dict.get("invoice"):
            # invoice_partner = self.ks_res_partner.browse(address_dict.get("invoice"))
            invoice_partner = odoo_partner.browse(address_dict.get("invoice"))
            first_name, last_name = self.ks_get_first_last_name(invoice_partner.name)
            billing = {
                "billing": {
                    'first_name': first_name,
                    'last_name': last_name,
                    'address1': invoice_partner.street or '',
                    'phone': invoice_partner.phone or '',
                    'city': invoice_partner.city or '',
                    'province': invoice_partner.state_id.name if invoice_partner.state_id else '',
                    'country': invoice_partner.country_id.code if invoice_partner.country_id else '',
                    'zip': invoice_partner.zip or ''
                }
            }
            data.update(billing)
        if address_dict.get("delivery"):
            # delivery_partner = self.ks_res_partner.browse(address_dict.get("delivery"))
            delivery_partner = odoo_partner.browse(address_dict.get("delivery"))
            first_name, last_name = self.ks_get_first_last_name(delivery_partner.name)
            shipping = {
                "shipping": {
                    'first_name': first_name,
                    'last_name': last_name,
                    'address1': delivery_partner.street or '',
                    'phone': delivery_partner.phone or '',
                    'city': delivery_partner.city or '',
                    'province': delivery_partner.state_id.name if delivery_partner.state_id else '',
                    'country': delivery_partner.country_id.code if delivery_partner.country_id else '',
                    'zip': delivery_partner.zip or ''
                }
            }
            data.update(shipping)
        return data

    def ks_shopify_get_all_customers(self, instance,
                                     include=False):

        """
            Use: This function will get all the customers from Shopify API
            :param instance: ks.shopify.instance() record
            :return: Dictionary of Created shopify customer
        """

        try:
            if include:
                all_retrieved_data = self.env['ks.api.handler'].ks_get_all_data(instance, 'customers', include)
            else:
                all_retrieved_data = self.env['ks.api.handler'].ks_get_all_data(instance, 'customers')

            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                   status="success",
                                                                   type="customer",
                                                                   operation_flow="shopify_to_odoo",
                                                                   instance=instance,
                                                                   shopify_id=0,
                                                                   layer_model="ks.shopify.partner",
                                                                   message="Fetch of Customer successful")
            return all_retrieved_data
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                   status="failed",
                                                                   type="customer",
                                                                   instance=instance,
                                                                   operation_flow="shopify_to_odoo",
                                                                   shopify_id=0,
                                                                   layer_model="ks.shopify.partner",
                                                                   message=str(e))

    def ks_shopify_get_customer(self, customer_id, instance):
        """
         Use: Retrieve the data of any specific customer from shopify to odoo
           :param customer_id: The id of customer whose data to be retrieved
           :return: Dictionary of Created shopify customer
         """
        try:
            customer_data = self.env['ks.api.handler'].ks_get_specific_data(instance, 'customers', customer_id)
            if customer_data:
                customer_data = customer_data.get('customer')
                self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                       status="success",
                                                                       type="customer",
                                                                       operation_flow="shopify_to_odoo",
                                                                       instance=instance,
                                                                       shopify_id=customer_data.get("id", 0),
                                                                       layer_model="ks.shopify.partner",
                                                                       message="Fetch of Customer successful")
                return customer_data
            else:
                self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                       status="failed",
                                                                       type="customer",
                                                                       operation_flow="shopify_to_odoo",
                                                                       instance=instance,
                                                                       shopify_id=0,
                                                                       layer_model="ks.shopify.partner",
                                                                       message=str('Custmoer might not exist or any other issue'))

        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                                   status="failed",
                                                                   type="customer",
                                                                   instance=instance,
                                                                   operation_flow="shopify_to_odoo",
                                                                   shopify_id=0,
                                                                   layer_model="ks.shopify.partner",
                                                                   message=str(e))

    def ks_shopify_post_customer(self, data, instance):
        """
        Use: Post the data to Shopify API for creating New Customers
            :param data: The json data to be created on shopify
            :param instance: ks.shopify.instance() record
            :return: Dictionary of Created shopify customer
        """
        try:
            customer_data = self.env['ks.api.handler'].ks_post_data(instance, 'customers', data)
            if customer_data:
                customer_data = customer_data.get('customer')
                self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="create",
                                                                       status="success",
                                                                       type="customer",
                                                                       operation_flow="odoo_to_shopify",
                                                                       instance=instance,
                                                                       shopify_id=customer_data.get("id", 0),
                                                                       layer_model="ks.shopify.partner",
                                                                       message="Create of Customer successful")
            return customer_data

        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="create",
                                                                   status="failed",
                                                                   type="customer",
                                                                   instance=instance,
                                                                   operation_flow="odoo_to_shopify",
                                                                   shopify_id=0,
                                                                   layer_model="ks.shopify.partner",
                                                                   message=str(e))

    def ks_shopify_update_customer(self, customer_id, data, instance):
        """
        Use: Post the data to Shopify API for creating New Customers
            :param customer_id: The customer shopify id to be updated on shopify
            :param data: The json data to be updated on shopify
            :param instance: ks.shopify.instance() record
            :return: Dictionary of Updated shopify customer
                """
        customer_data = False
        try:
            customer_data = self.env['ks.api.handler'].ks_put_data(instance, 'customers', data, customer_id)
            if customer_data:
                customer_data = customer_data.get('customer')
            # shopify_api = instance.ks_shopify_api_authentication()
            # shopify_customer_response = shopify_api.put("customers/%s" % customer_id, data)
            # if shopify_customer_response.status_code in [200, 201]:
            #     customer_data = shopify_customer_response.json()
                self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="update",
                                                                       status="success",
                                                                       type="customer",
                                                                       operation_flow="odoo_to_shopify",
                                                                       instance=instance,
                                                                       shopify_id=customer_data.get("id", 0),
                                                                       layer_model="ks.shopify.partner",
                                                                       message="Update of Customer successful")
            return customer_data

        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="update",
                                                                   status="failed",
                                                                   type="customer",
                                                                   instance=instance,
                                                                   operation_flow="odoo_to_shopify",
                                                                   shopify_id=0,
                                                                   layer_model="ks.shopify.partner",
                                                                   message=str(e))

    def ks_convert_shopify_odoo_compatible_data(self, data, type=False, customer=False):
        """
        :param data: json data for shopify
        :return: odoo compatible data
        """
        ks_data = []
        if data:
            country = self.env['res.partner'].ks_fetch_country(data.get('country') or False)
            state = self.env['res.partner'].ks_fetch_state(data.get('province') or False, country)
            ks_data = {
                "name": "%s %s" % (data.get('first_name'), data.get('last_name') or '') or '',
                "street": data.get('address1') or '',
                "street2": data.get('address2') or '',
                "city": data.get('city') or '',
                "zip": data.get('zip') or '',
                "state_id": state.id,
                "country_id": country.id,
                "phone": data.get('phone') or '',
            }
            if customer:
                ks_data.update({
                    "email": customer.get('email') or '',
                })
            if type == "billing":
                ks_data.update({
                    "type": 'invoice'
                })
            if type == "shipping":
                ks_data.update({
                    "type": "delivery"
                })
        return ks_data
