# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class KsQueueManager(models.TransientModel):
    _name = 'ks.generic.configuration'
    _description = 'Update Generic Information'

    ks_shopify_instance = fields.Many2many("ks.shopify.connector.instance", string="Instance ids",
                                           domain=[('ks_instance_state', '=', 'active')])
    ks_domain = fields.Char(string="Domain")
    ks_id = fields.Char(string="ID")
    ks_push_additional_data = fields.Boolean("Push Additional Data ?")
    ks_multi_record = fields.Boolean("Multiple Records")
    ks_is_variant = fields.Boolean("Is Variable")

    # Customer
    ks_note = fields.Char("Note")
    ks_tags = fields.Char("Tags")

    # Product Template
    ks_product_product = fields.Boolean("Product Variants")
    ks_shopify_description = fields.Html("Description")
    ks_shopify_tags = fields.Char('Tags')
    ks_shopify_type_product = fields.Char('Product Type')
    ks_shopify_vendor = fields.Char('Vendor')
    ks_update_image = fields.Boolean("Set Image in Shopify")
    ks_update_price = fields.Boolean("Set Price in Shopify")
    ks_update_stock = fields.Boolean("Set Stock in Shopify")
    ks_price = fields.Float("Price in Shopify")
    ks_barcode = fields.Char("Barcode", invisible=True)
    ks_compare_at_price = fields.Float("Compare Price in Shopify")
    ks_inventory_policy = fields.Selection([('continue', 'Continue'), ('deny', 'Deny')], 'Inventory Policy', default='deny')
    ks_update_website_status = fields.Selection([("published", "Active"),
                                                 ("unpublished", "Draft")], "Product Status", default="published")

    ks_shopify_product_template = fields.Many2many('product.template', string='Product Template')
    ks_product_variant_id = fields.Many2one('product.product', string='Product Variant')
    ks_product_additional_data = fields.One2many('ks.additional.data', 'ks_data')

    @api.onchange('ks_shopify_instance', 'ks_push_additional_data')
    def ks_onchange_instance(self):
        if self.ks_shopify_product_template:
            if self.ks_shopify_instance:
                for rec in self.ks_shopify_instance:
                    if self.ks_shopify_product_template.ks_shopify_product_template.filtered(lambda x:x.ks_shopify_instance == rec.browse(rec.ids[0])) and self.ks_shopify_product_template.ks_shopify_product_template.\
                            filtered(lambda x:x.ks_shopify_instance == rec.browse(rec.ids[0])).ks_shopify_instance.id in self.ks_shopify_instance.ids:
                        for data in self.ks_shopify_product_template.ks_shopify_product_template:
                            data = data.browse(data.ids[0])
                            instance_list = []
                            for instance in self.ks_product_additional_data:
                                instance_list.append(instance.ks_shopify_instance.id)
                            if data.ks_shopify_instance.id not in instance_list and rec.ids[0] not in instance_list:
                                dict_data = {
                                    'ks_inventory_policy': data.ks_inventory_policy,
                                    'ks_barcode': data.ks_barcode,
                                    'ks_shopify_description': data.ks_shopify_description,
                                    'ks_shopify_tags': data.ks_shopify_tags,
                                    'ks_shopify_type_product': data.ks_shopify_type_product,
                                    'ks_shopify_vendor': data.ks_shopify_vendor,
                                    'ks_price': data.ks_shopify_rp_pricelist.fixed_price,
                                    'ks_compare_at_price': data.ks_shopify_cp_pricelist.fixed_price,
                                    'ks_product_product': True if len(
                                        data.ks_shopify_variant_ids) > 1 else False,
                                    # 'ks_data': self.browse(self.ids[0]),
                                    'ks_shopify_instance': data.ks_shopify_instance.id,
                                }
                                additional_data = self.env['ks.additional.data'].create(dict_data)
                                self.update({'ks_product_additional_data': [(4, additional_data.id)]})
                            if data.ks_shopify_variant_ids:
                                for variant in data.ks_shopify_variant_ids:
                                    if variant and rec.ids[
                                        0] not in instance_list and data.ks_shopify_instance.id not in instance_list:
                                        dict_data = {
                                            'ks_barcode': variant.ks_barcode,
                                            'ks_inventory_policy': variant.ks_inventory_policy,
                                            'ks_shopify_description': variant.ks_shopify_description,
                                            'ks_price': self.env['product.pricelist.item'].search(
                                                [('product_id', '=', variant.ks_shopify_product_variant.id), ('pricelist_id', '=',
                                                                                                      variant.ks_shopify_instance.ks_shopify_regular_pricelist.id)]).filtered(
                                                lambda x: x.fixed_price > 0)[0].fixed_price if self.env['product.pricelist.item'].search(
                                                [('product_id', '=', variant.ks_shopify_product_variant.id), ('pricelist_id', '=',
                                                                                                      variant.ks_shopify_instance.ks_shopify_regular_pricelist.id)]).filtered(
                                                lambda x: x.fixed_price > 0) else 0.0,
                                            'ks_compare_at_price': self.env['product.pricelist.item'].search(
                                                [('product_id', '=', variant.ks_shopify_product_variant.id), ('pricelist_id', '=',
                                                                                                      variant.ks_shopify_instance.ks_shopify_compare_pricelist.id)]).filtered(
                                                lambda x: x.fixed_price > 0)[0].fixed_price if self.env['product.pricelist.item'].search(
                                                [('product_id', '=', variant.ks_shopify_product_variant.id), ('pricelist_id', '=',
                                                                                                      variant.ks_shopify_instance.ks_shopify_compare_pricelist.id)]).filtered(
                                                lambda x: x.fixed_price > 0) else 0.0,
                                            # 'ks_data': self.browse(self.ids[0]),
                                            'ks_shopify_instance': variant.ks_shopify_instance.id,
                                            'ks_product_variant_id': variant.ks_shopify_product_variant.id,
                                        }
                                        additional_data = self.env['ks.additional.data'].create(dict_data)
                                        self.update({'ks_product_additional_data': [(4, additional_data.id)]})
                            else:
                                for data in self.ks_shopify_product_template.product_variant_ids:
                                    if data.product_template_attribute_value_ids and rec.ids[0] not in instance_list:
                                        dict_data = {
                                            # 'ks_data': self.id,
                                            'ks_shopify_instance': rec.ids[0],
                                            'ks_product_variant_id': data.ids[0],
                                        }
                                        additional_data = self.env['ks.additional.data'].create(dict_data)
                                        self.update({'ks_product_additional_data': [(4, additional_data.id)]})
                                # else:
                                #     data = data.browse(data.ids[0])
                                #     if data.ks_shopify_instance.id == rec.ids[0] and not self.ks_product_additional_data.filtered(lambda x:x.ks_shopify_instance == self.env['ks.shopify.connector.instance'].browse(rec.ids[0])):
                                #         dict_data = {
                                #             'ks_barcode': data.ks_barcode,
                                #             'ks_shopify_description': data.ks_shopify_description,
                                #             'ks_shopify_tags': data.ks_shopify_tags,
                                #             'ks_shopify_type_product': data.ks_shopify_type_product,
                                #             'ks_shopify_vendor': data.ks_shopify_vendor,
                                #             'ks_price': data.ks_shopify_rp_pricelist.fixed_price,
                                #             'ks_compare_at_price': data.ks_shopify_cp_pricelist.fixed_price,
                                #             'ks_product_product': True if len(
                                #                 data.ks_shopify_variant_ids) > 1 else False,
                                #             # 'ks_data': self.browse(self.ids[0]),
                                #             'ks_shopify_instance': data.ks_shopify_instance.id,
                                #         }
                                #         additional_data = self.env['ks.additional.data'].create(dict_data)
                                #         self.update({'ks_product_additional_data': [(4, additional_data.id)]})
                    else:
                        instance_list = []
                        for data in self.ks_product_additional_data:
                            instance_list.append(data.ks_shopify_instance.id)
                        if rec.ids[0] not in instance_list:
                            dict_data = {
                                # 'ks_data': self.id,
                                'ks_shopify_instance': rec.ids[0],
                            }
                            additional_data = self.env['ks.additional.data'].create(dict_data)
                            self.update({'ks_product_additional_data': [(4, additional_data.id)]})
                        for data in self.ks_shopify_product_template.product_variant_ids:
                            if data.product_template_attribute_value_ids and rec.ids[0] not in instance_list:
                                dict_data = {
                                    # 'ks_data': self.id,
                                    'ks_shopify_instance': rec.ids[0],
                                    'ks_product_variant_id': data.ids[0],
                                }
                                additional_data = self.env['ks.additional.data'].create(dict_data)
                                self.update({'ks_product_additional_data': [(4, additional_data.id)]})
                    self.browse(self.ids[0]).update({
                        'ks_shopify_instance': self.ks_shopify_instance.ids,
                        'ks_push_additional_data': self.ks_push_additional_data,
                    })
                    list = []
                    for additional in self.browse(self.ids[0]).ks_product_additional_data:
                        for instance_id in self.ks_shopify_instance:
                            if additional.ks_shopify_instance.id == instance_id.ids[0]:
                                list.append(additional.id)
                    for additional in self.browse(self.ids[0]).ks_product_additional_data:
                        if additional.id not in list:
                            self.browse(self.ids[0]).update({'ks_product_additional_data': [(2, additional.id)]})
                    self.browse(self.ids[0]).ks_product_additional_data = list
            else:
                self.browse(self.ids[0]).update({
                    'ks_shopify_instance': [(6,0,self.ks_shopify_instance.ids)],
                    'ks_push_additional_data': self.ks_push_additional_data,
                })
                for additional in self.browse(self.ids[0]).ks_product_additional_data:
                    self.browse(self.ids[0]).update({'ks_product_additional_data': [(2, additional.id)]})

    def ks_update_generic(self):
        if self.ks_domain == 'res.partner':
            if self.env.context.get('ks_id'):
                ks_res_partner = self.env[self.ks_domain].browse(self.env.context.get('ks_id'))
                self.env[self.ks_domain].ks_manage_shopify_direct_syncing(ks_res_partner, self.ks_shopify_instance, push=True,
                                                                  generic_wizard=self)
            elif self.env.context.get('active_ids'):
                for rec in self.env.context.get('active_ids'):
                    ks_res_partner = self.env[self.ks_domain].browse(rec)
                    self.env[self.ks_domain].ks_manage_shopify_direct_syncing(ks_res_partner, self.ks_shopify_instance,
                                                                      push=True,
                                                                      generic_wizard=self)
        if self.ks_domain == 'product.template':
            if self.ks_product_additional_data:
                for shopify_product in self.ks_shopify_product_template:
                    for data in self.ks_product_additional_data:
                        dict_data = {
                            'ks_push_additional_data': self.ks_push_additional_data,
                            'ks_shopify_instance': [data.ks_shopify_instance.id],
                            'ks_domain': self.ks_domain,
                            'ks_id': shopify_product.id,
                            'ks_barcode': data.ks_barcode,
                            'ks_shopify_description': data.ks_shopify_description,
                            'ks_shopify_tags': data.ks_shopify_tags,
                            'ks_shopify_type_product': data.ks_shopify_type_product,
                            'ks_shopify_vendor': data.ks_shopify_vendor,
                            'ks_price': data.ks_price,
                            'ks_compare_at_price': data.ks_compare_at_price,
                            'ks_product_product': data.ks_product_product,
                            'ks_update_image': data.ks_update_image,
                            'ks_update_price': data.ks_update_price,
                            'ks_update_stock': data.ks_update_stock,
                            'ks_update_website_status': data.ks_update_website_status,
                            'ks_inventory_policy': data.ks_inventory_policy,
                        }
                        if data.ks_product_variant_id:
                            dict_data.update({
                                'ks_product_variant_id': data.ks_product_variant_id.id
                            })
                            ks_regular_pricelist_items = False
                            ks_compare_pricelist_items = False
                            if not self.ks_shopify_product_template.ks_shopify_product_template.filtered(
                                    lambda x: x.ks_shopify_instance == data.ks_shopify_instance).ks_shopify_rp_pricelist.search(
                                [("product_tmpl_id", '=', shopify_product.id),
                                 ("product_id", '=', data.ks_product_variant_id.id),
                                 ("pricelist_id", '=', data.ks_shopify_instance.ks_shopify_regular_pricelist.id)], limit=1):
                                ks_regular_pricelist_items = data.ks_shopify_instance.ks_shopify_regular_pricelist.item_ids.create(
                                    {
                                        "product_tmpl_id": shopify_product.id,
                                        "product_id": shopify_product.product_variant_id.id,
                                        "pricelist_id": data.ks_shopify_instance.ks_shopify_regular_pricelist.id,
                                        "fixed_price": data.ks_price,
                                        "name": shopify_product.name,
                                    })
                            else:
                                self.ks_shopify_product_template.ks_shopify_product_template.filtered(
                                    lambda
                                        x: x.ks_shopify_instance == data.ks_shopify_instance).ks_shopify_rp_pricelist.search(
                                    [("product_tmpl_id", '=', shopify_product.id),
                                     ("product_id", '=', data.ks_product_variant_id.id),
                                     ("pricelist_id", '=', data.ks_shopify_instance.ks_shopify_regular_pricelist.id)],
                                    limit=1).fixed_price = data.ks_price
                            if not self.ks_shopify_product_template.ks_shopify_product_template.filtered(
                                    lambda x: x.ks_shopify_instance == data.ks_shopify_instance).ks_shopify_cp_pricelist.search(
                                [("product_tmpl_id", '=', shopify_product.id),
                                 ("product_id", '=', data.ks_product_variant_id.id),
                                 ("pricelist_id", '=', data.ks_shopify_instance.ks_shopify_compare_pricelist.id)], limit=1):
                                ks_compare_pricelist_items = data.ks_shopify_instance.ks_shopify_compare_pricelist.item_ids.create(
                                    {
                                        "product_tmpl_id": shopify_product.id,
                                        "product_id": data.ks_product_variant_id.id,
                                        "pricelist_id": data.ks_shopify_instance.ks_shopify_compare_pricelist.id,
                                        "fixed_price": data.ks_compare_at_price,
                                        "name": shopify_product.name,
                                    })
                            else:
                                self.ks_shopify_product_template.ks_shopify_product_template.filtered(
                                    lambda
                                        x: x.ks_shopify_instance == data.ks_shopify_instance).ks_shopify_cp_pricelist.search(
                                    [("product_tmpl_id", '=', shopify_product.id),
                                     ("product_id", '=', data.ks_product_variant_id.id),
                                     ("pricelist_id", '=', data.ks_shopify_instance.ks_shopify_compare_pricelist.id)],
                                    limit=1).fixed_price = data.ks_compare_at_price
                            product_variant = {
                                'ks_default_code': data.ks_product_variant_id.default_code,
                                'ks_barcode': data.ks_barcode,
                                'ks_shopify_rp_pricelist': ks_regular_pricelist_items,
                                'ks_shopify_cp_pricelist': ks_compare_pricelist_items,
                            }
                            variant_exists = self.env['ks.shopify.product.variant'].search(
                                [('ks_shopify_instance', '=', data.ks_shopify_instance.id),
                                 ('ks_shopify_product_variant', '=', data.ks_product_variant_id.id),
                                 ('ks_shopify_product_tmpl_id', '=',
                                  self.ks_shopify_product_template.ks_shopify_product_template.filtered(
                                      lambda x: x.ks_shopify_instance == data.ks_shopify_instance and x.ks_shopify_product_template == shopify_product).id)])
                            if variant_exists:
                                variant_exists.update(product_variant)
                            else:
                                product_variant.update({
                                    'ks_shopify_product_variant': data.ks_product_variant_id.id,
                                    'ks_shopify_product_tmpl_id': self.ks_shopify_product_template.ks_shopify_product_template.filtered(
                                        lambda x: x.ks_shopify_instance == data.ks_shopify_instance and x.ks_shopify_product_template == shopify_product).id,
                                    'ks_shopify_instance': data.ks_shopify_instance.id
                                })
                        else:
                            generic_data = self.create(dict_data)
                            # if self.env.context.get('ks_id'):
                            #     ks_res_product = self.env[self.ks_domain].browse(self.env.context.get('ks_id'))
                            #     self.env[self.ks_domain].ks_manage_direct_syncing(ks_res_product, self.ks_shopify_instance, push=True,
                            #                                                       generic_wizard=generic_data)
                            # elif self.env.context.get('active_ids'):
                            #     ks_res_product = self.env[self.ks_domain].browse(self.ks_id)
                            self.env[self.ks_domain].ks_manage_shopify_direct_syncing(shopify_product,
                                                                              data.ks_shopify_instance,
                                                                              push=True,
                                                                              generic_wizard=generic_data)
            elif self.env.context.get('active_ids'):
                ks_res_product = self.env[self.ks_domain].browse(self.env.context.get('active_ids'))
                self.env[self.ks_domain].ks_manage_shopify_direct_syncing(ks_res_product,
                                                                  self.ks_shopify_instance,
                                                                  push=True, )
        if self.ks_domain == 'ks.shopify.product.template':
            self.ks_domain = 'product.template'
            if self.env.context.get('ks_id'):
                ks_res_product = self.env['ks.shopify.product.template'].browse(
                    self.env.context.get('ks_id')).ks_shopify_product_template
                self.env['ks.shopify.product.template'].ks_manage_shopify_direct_syncing(ks_res_product,
                                                                                 self.ks_shopify_instance, push=True,
                                                                                 generic_wizard=self)
            elif self.env.context.get('active_ids'):
                ks_res_product = self.env['ks.shopify.product.template'].browse(
                    self.env.context.get('active_ids')).ks_shopify_product_template
                self.env['product.template'].ks_manage_shopify_direct_syncing(ks_res_product, self.ks_shopify_instance,
                                                                      push=True,)
