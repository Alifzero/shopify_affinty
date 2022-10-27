import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class KsResPartnerInherit(models.Model):
    _inherit = "res.partner"

    ks_partner_shopify_ids = fields.One2many("ks.shopify.partner", "ks_res_partner", string="Partners")

    # type = fields.Selection(selection_add=[('default', 'Default Address')])

    def ks_shopify_handle_customer_address(self, odoo_customer, data, type):
        """
        :param odoo_customer: res.partner()
        :param data: odoo compatible data
        :return: res.partner()
        """
        address_found = odoo_customer.child_ids.search([('parent_id', '=', odoo_customer.id),
                                                        ("name", '=ilike', data.get("name")),
                                                        ("street", '=ilike', data.get("street")),
                                                        ("street2", '=ilike', data.get("street2")),
                                                        ("city", "=ilike", data.get("city")),
                                                        ("zip", "=ilike", data.get("zip")),
                                                        ("state_id", '=', data.get("state_id")),
                                                        ("country_id", '=', data.get("country_id")),
                                                        ("email", '=ilike', data.get("email")),
                                                        ("phone", '=ilike', data.get("phone")),
                                                        ("type", '=', type)])
        if address_found:
            ##Run update command here
            odoo_customer.child_ids = [(4,address_found.id)]
            child_customer = address_found
        else:
            data.update({
                'parent_id': odoo_customer.id
            })
            child_customer = odoo_customer.create(data)

        return odoo_customer, child_customer

    def action_shopify_layer_customers(self):
        """
        Open action.act_window  for shopify layer partner
        :return: action
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("ks_shopify.action_ks_shopify_partner")
        action['domain'] = [('id', 'in', self.ks_partner_shopify_ids.ids)]
        return action

    def check_empty_dict(self, dictionary):
        """
        :param dictionary: json data
        :return: Boolean
        """
        for _, values in dictionary.items():
            if values:
                return False
        else:
            return True

    def ks_map_shopify_odoo_partner_data_to_create(self, json_data, odoo_partner=False, instance=False):
        """
        Maps odoo partner data to create on shopify layer model
        :param json_data: api response json data format
        :return: data
        """
        data = {}
        partner_addresses = []
        for rec in json_data.get('addresses'):
            address_data = rec
            exist_address = self.env['ks.shopify.partner'].search(
                [('ks_shopify_partner_id', '=', address_data.get('id'))], limit=1)
            country = self.env['res.partner'].ks_fetch_country(address_data.get('country_code') or False)
            state = self.env['res.partner'].ks_fetch_state(address_data.get('province') or False, country)
            partner_address = {
                "name": "%s %s" % (address_data.get('first_name'), address_data.get('last_name') or '') or '',
                "street": address_data.get('address1') or '',
                "street2": address_data.get('address2') or '',
                "city": address_data.get('city') or '',
                "state_id": state.id,
                "zip": address_data.get('zip') or '',
                "country_id": country.id,
                "email": json_data.get('email') or '',
                "phone": address_data.get('phone') or '',
                "type": 'delivery' if address_data.get('default') else 'invoice',
                "company_id": instance.ks_company_id.id,
            }
            if not exist_address:
                partner_address = self.ks_odoo_customer_create(partner_address)
                partner_addresses.append(partner_address.id)
                ks_layer_data = {
                    "ks_shopify_instance": instance.id,
                    "ks_res_partner": partner_address.id,
                    "ks_shopify_partner_id": address_data.get('id'),
                    "ks_type": 'address',
                }
                layer_customer_address = self.env['ks.shopify.partner'].create(ks_layer_data)
            else:
                if exist_address.ks_res_partner:
                    partner_address = self.ks_odoo_customer_update(exist_address.ks_res_partner, partner_address)
                else:
                    partner_address = self.ks_odoo_customer_create(partner_address)
                partner_addresses.append(partner_address.id if partner_address else False)
        if json_data.get('first_name') or json_data.get('last_name'):
            data = {
                "name": "%s %s" % (json_data.get('first_name'), json_data.get('last_name') or '') if json_data.get(
                    'first_name') or json_data.get('last_name') else json_data.get('username'),
                "email": json_data.get('email') or '',
                "phone": json_data.get('phone') or '',
                "child_ids": partner_addresses,
                "company_id": instance.ks_company_id.id,
            }

        if instance.ks_meta_fields_map:
            meta_data = self.env['ks.shopify.meta.mapping'].get_meta_fields_data(instance=instance,
                                                                                 model='customers',
                                                                                 ids=json_data.get('id'),
                                                                                 ks_model='res.partner')
            data.update(meta_data)

        return data

    def ks_get_names(self, name):
        name = name.split()
        if name:
            if len(name) == 1:
                first_name = ''.join(name[0])
                last_name = ''
                return first_name, last_name
            else:
                first_name = ''.join(name[0:-1])
                last_name = "".join(name[-1])
                return first_name, last_name
        return None, None

    def ks_update_partner_address(self, customer_data, address, instance):
        try:
            address_data = self.ks_manage_address_export(address, instance)
            ks_customer_shopify_id = customer_data.ks_partner_shopify_ids.filtered(lambda x: x.ks_shopify_instance == instance)
            ks_address_shopify_id = address.ks_partner_shopify_ids.filtered(lambda x: x.ks_shopify_instance == instance)
            all_retrieved_data = self.env['ks.api.handler'].ks_put_data(instance,
                                                                        'addresses', {'address': address_data},
                                                                        ks_customer_shopify_id.ks_shopify_partner_id,
                                                                        ks_address_shopify_id.ks_shopify_partner_id)
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

    def ks_create_partner_address(self, customer_data, address, instance):
        try:
            address_data = self.ks_manage_address_export(address)
            customer_data = customer_data.ks_partner_shopify_ids.filtered(lambda x: x.ks_shopify_instance == instance)
            all_retrieved_data = self.env['ks.api.handler'].ks_post_data(instance,
                                                                        'addresses', {'address': address_data},
                                                                        customer_data.ks_shopify_partner_id)
            return all_retrieved_data
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

    def ks_prepare_data_to_export_put(self, layer_partner):
        """
        :param layer_partner: ks.shopify.partner()
        :return: shopify json data
        """
        first_name, last_name = self.ks_get_names(layer_partner.ks_res_partner.name)
        data = {
            "order_counts": layer_partner.ks_order_count or 0,
            "note": layer_partner.ks_note or '',
            "tags": layer_partner.ks_tags or '',
            "total_spent": layer_partner.ks_total_spent or 0.0,
            "email": layer_partner.ks_res_partner.email or '',
            "phone": layer_partner.ks_res_partner.phone or '',
            "first_name": first_name or '',
            "last_name": last_name or '',
        }
        return {'customer': data}

    def ks_prepare_data_to_export_post(self, layer_partner):
        """
        :param layer_partner: ks.shopify.partner()
        :return: shopify json data
        """
        first_name, last_name = self.ks_get_names(layer_partner.ks_res_partner.name)
        data = {
            "order_counts": layer_partner.ks_order_count or 0,
            "note": layer_partner.ks_note or '',
            "tags": layer_partner.ks_tags or '',
            "total_spent": layer_partner.ks_total_spent or 0.0,
            "email": layer_partner.ks_res_partner.email or '',
            "phone": layer_partner.ks_res_partner.phone or '',
            "first_name": first_name or '',
            "last_name": last_name or '',
        }
        address_collection = []
        for rec in layer_partner.ks_res_partner.child_ids:
            address_data = self.ks_manage_address_export(rec)
            address_collection.append(address_data)
        data.update({
            'addresses': address_collection,
        })
        return {'customer': data}

    def ks_manage_address_export(self, address, instance=False):
        """
        :param billing: res.partner() type="invoice"
        :return: billing json
        """
        first_name, last_name = self.ks_get_names(address.name)
        address_data = {
            # "customer_id": rec.parent_id[0].ks_partner_shopify_ids[0].ks_shopify_partner_id,
            "name": address.name,
            "first_name": first_name or '',
            "last_name": last_name or '',
            "address1": address.street or '',
            "address2": address.street2 or '',
            "city": address.city or '',
            # "province": address.state_id.display_name or '',
            "province": address.state_id.name or address.state_id.code or '',
            "zip": address.zip or '',
            "country": address.country_id.code or '',
            "phone": address.phone or address.phone_sanitized or address.mobile or '',
            "default": True if address.type == 'delivery' else False
        }
        ks_shopify_partner_id = address.ks_partner_shopify_ids.filtered(lambda x: x.ks_shopify_instance == instance)
        if address.ks_partner_shopify_ids and ks_shopify_partner_id.ks_shopify_partner_id:
            address_data.update({
                "id": ks_shopify_partner_id.ks_shopify_partner_id,
            })
        return address_data

    def ks_push_to_shopify(self):
        if self:
            active_ids = self.ids
        else:
            active_ids = self.env.context.get("active_ids")
        records = active_ids
        context = {'default_ks_domain': 'res.partner',
                   'ks_id': records,
                   'default_ks_multi_record': True if len(records) > 1 else False
                   }
        if len(records) <= 1 and len(self.browse(records).ks_partner_shopify_ids) <= 1:
            context.update({
                'default_ks_note': self.browse(records).ks_partner_shopify_ids.ks_note,
                'default_ks_tags': self.browse(records).ks_partner_shopify_ids.ks_tags,
            })
        return {
            'name': 'Customer Data Wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
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
                data_prepared = self.ks_partner_shopify_ids.filtered(lambda x: x.ks_shopify_instance.id == instance_counts.id)
                if data_prepared and data_prepared.ks_shopify_partner_id:
                    ##Handle shopify import here
                    shopify_id = data_prepared.ks_shopify_partner_id
                    json_data = self.env['ks.shopify.partner'].ks_shopify_get_customer(shopify_id,
                                                                                       instance=instance_counts)
                    if json_data:
                        partner = self.env['ks.shopify.partner'].ks_manage_shopify_customer_import(instance_counts,
                                                                                                   json_data)
                    else:
                        _logger.info("Fatal Error in Syncing Customer from Shopify")

                else:
                    _logger.info("Layer record must have shopify id")
        else:
            active_ids = self.env.context.get("active_ids")
            instances = self.env['ks.shopify.connector.instance'].search([('ks_instance_state', 'in', ['active'])])
            if len(instances) > 1:
                action = self.sudo().env.ref('ks_shopify.ks_instance_selection_action_pull').read()[0]
                action['context'] = {'pull_from_shopify': True, 'active_ids': active_ids, 'active_model': 'res.partner'}
                return action
            else:
                records = self.browse(active_ids)
                if len(records) == 1:
                    data_prepared = records.ks_partner_shopify_ids.filtered(lambda x: x.ks_shopify_instance.id == instances.id)
                    if data_prepared and data_prepared.ks_shopify_partner_id:
                        ##Handle shopify import here
                        shopify_id = data_prepared.ks_shopify_partner_id
                        json_data = self.env['ks.shopify.partner'].ks_shopify_get_customer(shopify_id,
                                                                                           instance=instances)
                        if json_data:
                            partner = self.env['ks.shopify.partner'].ks_manage_shopify_customer_import(instances,
                                                                                                       json_data)
                        else:
                            _logger.info("Fatal Error in Syncing Customer from Shopify")
                else:
                    for rec in records:
                        data_prepared = rec.ks_partner_shopify_ids.filtered(
                            lambda x: x.ks_shopify_instance.id == instances.id)
                        shopify_id = data_prepared.ks_shopify_partner_id
                        json_data = self.env['ks.shopify.partner'].ks_shopify_get_customer(shopify_id,
                                                                                           instance=instances)
                        if json_data:
                            self.env['ks.shopify.queue.jobs'].ks_create_customer_record_in_queue(instance=instances,
                                                                                                 data=[json_data])

    def ks_manage_shopify_direct_syncing(self, record, instance_ids, push=False, pull=False, generic_wizard=False):
        try:
            if len(record) == 1:
                for instance in instance_ids:
                    if push:
                        data_prepared = record.ks_partner_shopify_ids.filtered(
                            lambda x: x.ks_shopify_instance.id == instance.id)
                        if data_prepared:
                            ##Run update shopify record command here
                            self.env['ks.shopify.partner'].update_shopify_record(instance, record,
                                                                                 generic_wizard=generic_wizard,
                                                                                 update_to_shopify=True)
                        else:
                            self.env['ks.shopify.partner'].create_shopify_record(instance, record,
                                                                                 generic_wizard=generic_wizard,
                                                                                 export_to_shopify=True)

                    elif pull:
                        ##Handling of pull ther records from shopifycommerce here
                        data_prepared = record.ks_partner_shopify_ids.filtered(
                            lambda x: x.ks_shopify_instance.id == instance.id)
                        if data_prepared and data_prepared.ks_shopify_partner_id:
                            ##Handle shopify import here
                            shopify_id = data_prepared.ks_shopify_partner_id
                            json_data = self.env['ks.shopify.partner'].ks_shopify_get_customer(shopify_id,
                                                                                               instance=instance)
                            if json_data:
                                partner = self.env['ks.shopify.partner'].ks_manage_shopify_customer_import(instance,
                                                                                                           json_data)
                            else:
                                _logger.info("Fatal Error in Syncing Customer from Shopify")

                        else:
                            _logger.info("Layer record must have shopify id")
            else:
                for instance in instance_ids:
                    if push:
                        for rec in record:
                            data_prepared = rec.ks_partner_shopify_ids.filtered(
                                lambda x: x.ks_shopify_instance.id == instance.id)
                            if data_prepared:
                                self.env['ks.shopify.queue.jobs'].ks_create_prepare_record_in_queue(instance,
                                                                                                    'ks.shopify.partner',
                                                                                                    'res.partner',
                                                                                                    rec.id,
                                                                                                    'update', True,
                                                                                                    True)
                            else:
                                self.env['ks.shopify.queue.jobs'].ks_create_prepare_record_in_queue(instance,
                                                                                                    'ks.shopify.partner',
                                                                                                    'res.partner',
                                                                                                    rec.id,
                                                                                                    'create', True,
                                                                                                    True)
                    elif pull:
                        for rec in record:
                            data_prepared = rec.ks_partner_shopify_ids.filtered(
                                lambda x: x.ks_shopify_instance.id == instance.id)
                            shopify_id = data_prepared.ks_shopify_partner_id
                            json_data = self.env['ks.shopify.partner'].ks_shopify_get_customer(shopify_id,
                                                                                               instance=instance)
                            if json_data:
                                self.env['ks.shopify.queue.jobs'].ks_create_customer_record_in_queue(instance=instance,
                                                                                                     data=[json_data])

        except Exception as e:
            _logger.info(str(e))

    def open_shopify_mapper(self):
        """
        Open customer mapping wizard
        :return: mapped
        """
        active_records = self._context.get("active_ids", False)
        model = self.env['ir.model'].search([('model', '=', self._name)])
        mapped = self.env['ks.shopify.global.record.mapping'].action_open_mapping_wizard(model,
                                                                                 active_records,
                                                                                 "Customers Record Mapping")
        return mapped
