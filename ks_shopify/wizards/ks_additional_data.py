# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class KsAdditionalData(models.TransientModel):
    _name = 'ks.additional.data'
    _description = 'Stores additional data'

    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Instance ids",
                                          domain=[('ks_instance_state', '=', 'active')], readonly=True)
    ks_product_product = fields.Boolean("Product Variants")
    ks_shopify_description = fields.Html("Description")
    ks_shopify_tags = fields.Char('Tags')
    ks_barcode = fields.Char("Barcode", invisible=True)
    ks_shopify_type_product = fields.Char('Product Type')
    ks_shopify_vendor = fields.Char('Vendor')
    ks_update_image = fields.Boolean("Set Image in Shopify")
    ks_update_price = fields.Boolean("Set Price in Shopify")
    ks_update_stock = fields.Boolean("Set Stock in Shopify")
    ks_price = fields.Float("Price in Shopify")
    ks_compare_at_price = fields.Float("Compare Price in Shopify")
    ks_update_website_status = fields.Selection([("published", "Active"),
                                                 ("unpublished", "Draft")], "Product Status", default="published")
    ks_data = fields.Many2one('ks.generic.configuration')
    ks_product_variant_id = fields.Many2one('product.product', string='Product Variant')
    ks_inventory_policy = fields.Selection([('continue', 'Continue'), ('deny', 'Deny')], 'Inventory Policy', default='deny')

    def ks_save_additional_data(self):
        return {
            'name': 'Product Data Wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.ks_data.id,
            'res_model': 'ks.generic.configuration',
            'target': 'new',
            'context': self.env.context,
        }
