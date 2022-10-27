# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class KsMapResPartnerWizard(models.TransientModel):
    _name = "map.shopify.res.partner.wizard"
    _description = "Shopify Partner Mapping"

    res_partner_line_ids = fields.One2many("map.shopify.wizard.line", "res_partner_wizard_id", string="Customers")
    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Instance id",
                                          domain=[('ks_instance_state', '=', 'active')])
    ks_sync_operation = fields.Selection(
        [('push_to_shopify', 'Push to Shopify'), ('pull_from_shopify', 'Pull from Shopify')],
        string="Sync operation", default=False)

    @api.onchange('ks_shopify_instance')
    @api.depends('ks_shopify_instance')
    def check_instance(self):
        self.res_partner_line_ids.update({'ks_shopify_instance': self.ks_shopify_instance.id})

    def map_customers_records(self):
        count_instance = 0
        for reco in self.res_partner_line_ids:
            if reco.ks_shopify_instance:
                count_instance += 1
        if count_instance != len(self.res_partner_line_ids):
            raise ValidationError("Cannot Map without Instance")
        for line in self.res_partner_line_ids:
            already_exist = self.env['ks.shopify.partner'].search([('ks_shopify_partner_id', '=', line.ks_record_id),
                                                                   ('ks_shopify_instance', '=',
                                                                    line.ks_shopify_instance.id)])
            if already_exist:
                raise ValidationError(
                    "Shopify Id already within given instance already exists.in record *%s* with id given: %s" % (
                        already_exist.display_name, already_exist.ks_shopify_partner_id))
            layer_record = line.ks_base_model_customer.ks_partner_shopify_ids.filtered(
                lambda x: x.ks_shopify_instance.id == line.ks_shopify_instance.id)
            if layer_record:
                layer_record = self.env['ks.shopify.partner'].update_shopify_record(line.ks_shopify_instance,
                                                                                    line.ks_base_model_customer)
            else:
                layer_record = self.env['ks.shopify.partner'].create_shopify_record(line.ks_shopify_instance,
                                                                                    line.ks_base_model_customer)
            if layer_record:
                layer_record.update({
                    'ks_shopify_partner_id': line.ks_record_id,
                    'ks_mapped': True
                })
            if self.ks_sync_operation == 'push_to_shopify':
                ##Handle export operation here
                try:
                    self.env['ks.shopify.queue.jobs'].ks_create_customer_record_in_queue(
                        instance=line.ks_shopify_instance,
                        records=layer_record)
                except Exception as e:
                    _logger.info(str(e))
            elif self.ks_sync_operation == 'pull_from_shopify':
                ##Handle import operation here
                try:
                    shopify_id = layer_record.ks_shopify_partner_id
                    json_data = self.env['ks.api.handler'].ks_get_specific_data(layer_record.ks_shopify_instance,
                                                                                "customers", shopify_id)
                    if json_data:
                        json_data = json_data.get("customer")
                    if json_data:
                        self.env['ks.shopify.queue.jobs'].ks_create_customer_record_in_queue(
                            instance=layer_record.ks_shopify_instance,
                            data=[json_data])
                except Exception as e:
                    _logger.info(str(e))


class KsMapProduct(models.TransientModel):
    _name = "map.shopify.product.wizard"
    _description = "Shopify Product Variant Mapping"

    product_line_ids = fields.One2many("map.shopify.wizard.line", "product_wizard_id", string="Product")
    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Instance id",
                                          domain=[('ks_instance_state', '=', 'active')])
    ks_sync_operation = fields.Selection(
        [('push_to_shopify', 'Push to Shopify'), ('pull_from_shopify', 'Pull from Shopify')],
        string="Sync records to Shopify", default=False)
    ks_filled = fields.Boolean(compute="_check_filled", readonly=True)

    @api.onchange('ks_shopify_instance')
    @api.depends('ks_shopify_instance')
    def check_instance(self):
        self.product_line_ids.update({'ks_shopify_instance': self.ks_shopify_instance.id})

    def map_product_records(self):
        parent = None
        product_template = []
        product_template_ids = []
        instance_ids = []
        count_instance = 0
        for reco in self.product_line_ids:
            if reco.ks_shopify_instance:
                count_instance += 1
        if count_instance != len(self.product_line_ids):
            raise ValidationError("Cannot Map without Instance")
        for line in self.product_line_ids:
            if line.ks_base_model_product:
                already_exist = self.env['ks.shopify.product.template'].search(
                    [('ks_shopify_instance', '=', line.ks_shopify_instance.id),
                     ('ks_shopify_product_id', '=', line.ks_record_id)])
                if already_exist:
                    raise ValidationError(
                        "Shopify Id already exists for the given instance in record *%s* for the id given: %s" % (
                            already_exist.display_name, already_exist.ks_shopify_product_id))
                parent = line.ks_base_model_product
                layer_record = line.ks_base_model_product.ks_shopify_product_template.filtered(
                    lambda x: x.ks_shopify_instance.id == line.ks_shopify_instance.id)
                if layer_record:
                    layer_record = self.env['ks.shopify.product.template'].update_shopify_record(
                        line.ks_shopify_instance,
                        line.ks_base_model_product)
                else:
                    layer_record = self.env['ks.shopify.product.template'].create_shopify_record(
                        line.ks_shopify_instance,
                        line.ks_base_model_product)
                if layer_record:
                    layer_record.update({
                        'ks_shopify_product_id': line.ks_record_id,
                        'ks_mapped': True
                    })
                if line.ks_base_model_product.id not in product_template_ids:
                    product_template.append(line.ks_base_model_product)
                    product_template_ids.append(line.ks_base_model_product.id)
                    instance_ids.append(line.ks_shopify_instance.id)
            elif line.ks_base_model_product_variant:
                already_exist = self.env['ks.shopify.product.variant'].search(
                    [('ks_shopify_instance', '=', line.ks_shopify_instance.id),
                     ('ks_shopify_variant_id', '=', line.ks_record_id)])
                if already_exist:
                    raise ValidationError(
                        "Shopify Id already exists for the given instance in record *%s* for the id given: %s" % (
                            already_exist.display_name, already_exist.ks_shopify_variant_id))
                template = line.ks_base_model_product_variant.product_tmpl_id
                template_instance = self.product_line_ids.filtered(
                    lambda x: x.ks_base_model_product.id == template.id).ks_shopify_instance
                if template_instance.id != line.ks_shopify_instance.id:
                    raise ValidationError("Variant instance should be same as Template instance")
                layer_variants = parent.ks_shopify_product_template.ks_shopify_variant_ids.filtered(
                    lambda x: (x.ks_shopify_instance.id == line.ks_shopify_instance.id) and (
                            x.ks_shopify_product_variant.id == line.ks_base_model_product_variant.id)
                )
                if layer_variants:
                    layer_variants.update({
                        'ks_shopify_variant_id': line.ks_record_id,
                        'ks_mapped': True
                    })
                if template.id not in product_template_ids:
                    product_template.append(template)
                    product_template_ids.append(template.id)
                    instance_ids.append(template_instance.id)
        if product_template:
            try:
                for instance, template in enumerate(product_template):
                    layer_record = template.ks_shopify_product_template.filtered(
                        lambda x: x.ks_shopify_instance.id == instance_ids[instance])
                    instance_id = self.env['ks.shopify.connector.instance'].browse(instance_ids[instance])
                    if layer_record:
                        if self.ks_sync_operation == 'push_to_shopify':
                            self.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(instance=instance_id,
                                                                                                records=layer_record)
                        if self.ks_sync_operation == 'pull_from_shopify':
                            shopify_id = layer_record.ks_shopify_product_id
                            json_data = self.env["ks.api.handler"].ks_get_specific_data(instance_id, "products",
                                                                                        shopify_id)
                            if json_data:
                                json_data = json_data.get("product")
                                self.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(
                                    instance=instance_id,
                                    data=[json_data])

            except Exception as e:
                _logger.info(str(e))


class KsMapWizardLine(models.TransientModel):
    _name = "map.shopify.wizard.line"
    _description = "Record Line for mapping"

    res_partner_wizard_id = fields.Many2one("map.shopify.res.partner.wizard")
    product_wizard_id = fields.Many2one("map.shopify.product.wizard")
    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Shopify Instance",
                                          domain=[('ks_instance_state', '=', 'active')])
    ks_id = fields.Integer(string="Odoo ID", readonly=True)
    ks_record_id = fields.Char(string="Shopify Mapping ID")
    name = fields.Char(string="Name", readonly=True)
    ks_base_model_customer = fields.Many2one("res.partner", string="Odoo Partner", readonly=True)
    ks_base_model_product = fields.Many2one("product.template", string="Odoo Product Template", readonly=True)
    ks_base_model_product_variant = fields.Many2one("product.product", string="Odoo Product Variant",
                                                    readonly=True)
