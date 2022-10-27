# -*- coding: utf-8 -*-

from odoo import api, fields, models


class KsShopifyLogs(models.Model):
    _name = "ks.shopify.logger"
    _rec_name = "ks_log_id"
    _order = 'create_date desc'
    _description = "Used to maintain logging of all kind of shopify operations"

    ks_name = fields.Char("Name", default="Not Available")
    ks_log_id = fields.Char(string="Log Id", readonly=True, default=lambda self: 'New')
    ks_operation_performed = fields.Selection([('create', 'Create'), ('prepare_create', 'Prepare Create'),
                                               ('prepare_update', 'Prepare Update'),
                                               ('cancel', 'Cancel'), ('update', 'Update'),
                                               ('fetch', 'Fetch'), ('import', 'Import'),
                                               ('export', 'Export'), ('refund', 'Refund'), ('conn', 'Connection'), ('map','Map'),
                                               ('delete', 'Delete'), ('create_in_queue', 'Added in Queue')],
                                              string="Operation Performed", help="Displays operation type which is performed")
    ks_type = fields.Selection([('order', 'Orders'), ('product', 'Product'), ('product_variant', 'Product Variant'),
                                ('stock', 'Stock'), ('price', 'Price'), ('category', 'Category'), ('tags', 'Tags'),
                                ('customer', 'Customer'), ('payment_gateway', 'Payment Gateway'), ('discount', 'Discount'),
                                ('attribute', 'Attribute'), ('attribute_value', 'Attribute Values'), ('locations', 'Location'), ('tax', 'Tax'),
                                ('api_data_handling', 'API Data Handlings'), ('product_status', 'Product Status'),
                                ('system_status', 'System Status'), ('webhook', "Webhook"),('collection', 'Collections')],
                               string="Domain", help="Shows name of the model")
    ks_shopify_instance = fields.Many2one("ks.shopify.connector.instance", string="Shopify Instance", help="Displays Shopify Instance Name")
    ks_record_id = fields.Integer(string="Odoo Record ID", help="Displays the odoo record ID")
    ks_message = fields.Text(string="Logs Message", help="Displays the Summary of the Logs")
    ks_model = fields.Many2one("ir.model", string="Odoo Model Associated", help="Displays the odoo default model which is associated")
    ks_layer_model = fields.Many2one("ir.model", string="Layer Model Associated", help="Displays the layer model which is associated")
    ks_shopify_id = fields.Char(string="Shopify ID")
    ks_operation_flow = fields.Selection([('odoo_to_wl', "Odoo to Shopify Layer"),
                                          ('odoo_to_shopify', "Odoo to Shopify"),
                                          ('wl_to_odoo', "Shopify Layer to Odoo"),
                                          ('shopify_to_wl', "Shopify to Shopify Layer"),
                                          ('wl_to_shopify', "Shopify Layer to Shopify"),
                                          ('shopify_to_odoo', "Shopify to Odoo")],
                                         string="Operation Flow", help="Shows the flow of the operation either from Shopify to Odoo or Odoo to Shopify")
    ks_status = fields.Selection([('success', 'Success'), ('failed', 'Failed')], string="Operation Status", help="Displays the status of the operation Success/Failed")
    ks_prepare = fields.Boolean(string="Prepare Operation")
    ks_api = fields.Boolean(string="API Operation")
    ks_company_id = fields.Many2one("res.company", string="Company", compute="_compute_company", store=True,
                                    help="Displays Company Name")

    @api.depends('ks_shopify_instance')
    def _compute_company(self):
        """
        Computes company for the Shopify Logger
        :return:
        """
        for rec in self:
            if rec.ks_shopify_instance.ks_company_id:
                rec.ks_company_id = rec.ks_shopify_instance.ks_company_id.id
            else:
                rec.ks_company_id = self._context.get('company_id', self.env.company.id)

    @api.model
    def create(self, vals):
        """
        Creates log records with auto unique sequence
        :param vals: creation data
        :return: super
        """
        seq = self.env['ir.sequence'].next_by_code('increment_your_field') or ('New')
        vals['ks_log_id'] = seq
        return super(KsShopifyLogs, self).create(vals)

    def ks_create_prepare_log_params(self, operation_performed, status, instance, id, message, odoo_model=False,
                                     layer_model=False, type=False):
        """
        :param operation_performed: type of operation performed
        :param status: status of operation (failed/success)
        :param type: Domain on which operation performed
        :param instance: ks.shopify.connector.instance()
        :param odoo_model: ir.model()
        :param layer_model: ir.model()
        :param id:
        :param message:
        :return:
        """
        ks_model = ks_layer_model = False
        if odoo_model:
            ks_model = self.env['ir.model']._get(odoo_model).id
        if layer_model:
            ks_layer_model = self.env['ir.model']._get(layer_model).id
        params = {
            "ks_operation_performed": operation_performed,
            "ks_status": status,
            "ks_type": type,
            "ks_operation_flow": "odoo_to_shopify",
            "ks_shopify_instance": instance.id if instance else False,
            "ks_model": ks_model,
            "ks_layer_model": ks_layer_model,
            "ks_record_id": id,
            "ks_message": message,
        }
        # params = self.ks_assign_record_with_record(type, id or 0, params)
        self.create(params)

    def ks_create_api_log_params(self, operation_performed, status, operation_flow, type, instance, shopify_id, message,
                                 layer_model=False):
        """
        :param operation_performed: type of operation performed
        :param status: status of operation (failed/success)
        :param operation_flow: flow (shopify_to_odoo/odoo_to_shopify)
        :param type: Domain on which operation performed
        :param instance: ks.shopify.connector.instance()
        :param shopify_id: Shopify id
        :param layer_model:
        :return:
        """
        ks_layer_model = False
        if layer_model:
            ks_layer_model = self.env['ir.model']._get(layer_model).id

        params = {
            "ks_operation_performed": operation_performed,
            "ks_status": status,
            "ks_operation_flow": operation_flow,
            "ks_type": type,
            "ks_shopify_instance": instance.id if instance else False,
            "ks_shopify_id": shopify_id or 0,
            "ks_layer_model": ks_layer_model,
            "ks_message": message
        }
        # params = self.ks_assign_record_with_shopify_id(type, instance, shopify_id or 0, params)
        self.create(params)

    def ks_create_odoo_log_param(self, ks_operation_performed, ks_status, ks_operation_flow, ks_type, ks_shopify_instance,
                                 ks_shopify_id, ks_record_id, ks_message, ks_model=False, ks_layer_model=False):
        """
        Generic method to create logs
        :param ks_operation_performed: type of operation
        :param ks_type: domain name
        :param ks_shopify_instance: Shopify instance
        :param ks_record_id: odoo record id
        :param ks_message: process conclusion message
        :param ks_shopify_id: shopify unique id
        :param ks_operation_flow: operation flow
        :param ks_status: operation status
        :param ks_model: model id
        :param ks_layer_model: layer model id
        :param ks_error: error
        :return:
        """
        if ks_model:
            ks_model = self.env['ir.model']._get(ks_model).id
        if ks_layer_model:
            ks_layer_model = self.env['ir.model']._get(ks_layer_model).id
        params = {
            'ks_operation_performed': ks_operation_performed,
            'ks_type': ks_type,
            'ks_shopify_instance': ks_shopify_instance.id if ks_shopify_instance else False,
            'ks_record_id': ks_record_id,
            'ks_message': ks_message,
            'ks_model': ks_model,
            'ks_shopify_id': ks_shopify_id if ks_shopify_id else 0,
            'ks_layer_model': ks_layer_model,
            'ks_operation_flow': ks_operation_flow,
            'ks_status': ks_status
        }
        # params = self.ks_assign_record_with_shopify_id(ks_type, ks_shopify_instance, ks_shopify_id or 0, params)
        self.create(params)

    def ks_create_log_param(self, ks_operation_performed, ks_type, ks_shopify_instance, ks_record_id, ks_message,
                            ks_shopify_id, ks_operation_flow, ks_status, ks_model=False, ks_layer_model=False,
                            ks_error=False):
        """
        Generic method to create logs
        :param ks_operation_performed: type of operation
        :param ks_type: domain name
        :param ks_shopify_instance: Shopify instance
        :param ks_record_id: odoo record id
        :param ks_message: process conclusion message
        :param ks_shopify_id: shopify unique id
        :param ks_operation_flow: operation flow
        :param ks_status: operation status
        :param ks_model: model id
        :param ks_layer_model: layer model id
        :param ks_error: error
        :return:
        """
        if ks_model:
            ks_model = self.env['ir.model']._get(ks_model).id
        if ks_layer_model:
            ks_layer_model = self.env['ir.model']._get(ks_layer_model).id
        params = {
            'ks_operation_performed': ks_operation_performed,
            'ks_type': ks_type,
            'ks_shopify_instance': ks_shopify_instance.id if ks_shopify_instance else False,
            'ks_record_id': ks_record_id,
            'ks_message': ks_message if not (ks_error) else (ks_message + " " + str(ks_error)),
            'ks_model': ks_model,
            'ks_shopify_id': ks_shopify_id if ks_shopify_id else 0,
            'ks_layer_model': ks_layer_model,
            'ks_operation_flow': ks_operation_flow,
            'ks_status': ks_status
        }
        # params = self.ks_assign_record_with_shopify_id(ks_type, ks_shopify_instance, ks_shopify_id or 0, params)
        self.create(params)
