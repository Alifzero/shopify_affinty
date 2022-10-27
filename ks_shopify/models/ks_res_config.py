import logging
from odoo import models, fields, _

_logger = logging.getLogger(__name__)


class KsSettings(models.Model):
    _name = "ks.settings"
    _rec_name = "ks_shopify_instance"
    _description = 'Shopify Settings'

    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Select Instance",
                                          help=_("Shopify Connector Instance reference"), ondelete='cascade')
    ks_to_export = fields.Boolean(string="Enable Automatic Product Export", default=False)