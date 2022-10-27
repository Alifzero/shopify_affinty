# -*- coding: utf-8 -*-

import logging
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class KsShopifyIRCronInherit(models.Model):
    _inherit = 'ir.cron'

    ks_shopify_instance = fields.Many2one('ks.shopify.connector.instance', string='Instance', readonly=True,
                                     ondelete='cascade')

    def cron_initiate(self):
        try:
            cron_record = self.env.ref('ks_shopify.ks_ir_cron_job_process')
            if cron_record:
                next_exc_time = datetime.now()
                cron_record.sudo().write({'nextcall': next_exc_time, 'active': True})
        except UserError as e:
            _logger.warning("Cron Initiate error: %s", e)