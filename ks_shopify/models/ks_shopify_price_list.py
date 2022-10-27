# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class KsShopifyProductPricelistInherit(models.Model):
    _inherit = 'product.pricelist'

    ks_shopify_instance = fields.Many2one('ks.shopify.connector.instance', string='Shopify Instance ID',
                                     help="""Shopify Instance: The Instance which will used this price list to update the price""",
                                     ondelete='cascade')
    ks_shopify_regular_pricelist = fields.Boolean("Is Regular pricelist?")
    ks_shopify_compare_pricelist = fields.Boolean("Is Compare pricelist?")
