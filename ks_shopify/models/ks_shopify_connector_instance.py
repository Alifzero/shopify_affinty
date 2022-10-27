# -*- coding: utf-8 -*-
import base64
import logging
from datetime import datetime
import pytz
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from requests.exceptions import ConnectionError
import requests

_logger = logging.getLogger(__name__)


class KsShopifyCommerceConnectorInstance(models.Model):
    _name = "ks.shopify.connector.instance"
    _rec_name = 'ks_instance_name'
    _description = "Shopify Connector Instance"

    ks_instance_name = fields.Char(string='Connector Instance  Name ', required=True, translate=True,
                                   help="Displays Shopify Instance Name")
    ks_shopify_instance = fields.Char(string='Connector Instance Name', related="ks_instance_name", store=True,
                                      translate=True)
    ks_instance_state = fields.Selection([('draft', 'Draft'), ('connected', 'Connected'), ('active', 'Active'),
                                          ('deactivate', 'Deactivate')], string="Instance State", default="draft")
    ks_company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company.id,
                                    required=True, readonly=True, help=" Shows the name of the company", copy=False)
    ks_instance_connected = fields.Boolean(default=False, string="Instance Connected")
    # Instance Configuration Details
    ks_store_url = fields.Char('Store URL', required=True, help="Displays the Shopify Store URL")
    ks_customer_key = fields.Char('Customer Key', required=True,
                                  help="Customer Key of the Shopify, not visible by default")
    ks_customer_password = fields.Char('Customer Password', required=True,
                                       help="Customer Password of the Shopify, not visible by default")
    ks_shared_secret = fields.Char('Shared Secret', required=True,
                                   help="Shared Secret of the Shopify, not visible by default")
    ks_shopify_url = fields.Char("Shopify URL")
    ks_shopify_shop_id = fields.Char("Shop ID", readonly=True)
    ks_shopify_shop_name = fields.Char("Shop Name", readonly=True)
    sequence = fields.Integer(string='Sequence', default=10)
    # General Information
    ks_warehouse = fields.Many2one('stock.warehouse', 'Warehouse', domain="[('company_id', '=', ks_company_id)]",
                                   help=_("Shows the location of the warehouse"))
    ks_language = fields.Many2one('res.lang', string='Language', help=_("Select language for your Shopify Instance"))
    ks_shopify_currency = fields.Many2one('res.currency', 'Main Currency', help="Shows the main currency in use")
    ks_shopify_regular_pricelist = fields.Many2one('product.pricelist', string='Regular Main Pricelist',
                                                   help=" Manages regular sale price of the product from Shopify instance.")
    ks_shopify_compare_pricelist = fields.Many2one('product.pricelist', string='Compare Main Pricelist',
                                                   help="Manages on sale price/discounted price of the product from Shopify instance.")
    # Multi Currency
    ks_shopify_multi_currency = fields.Many2many('res.currency', string='Multi-Currency',
                                                 help="Shows the multiple currency to select from")
    ks_shopify_pricelist_ids = fields.Many2many('product.pricelist', string='Multi-Pricelist', readonly=True)
    # Order Management Fields
    ks_sale_workflow_ids = fields.One2many('ks.auto.sale.workflow.configuration', 'ks_shopify_instance',
                                           string="Sale Workflow IDs",
                                           help="Shows the flow of the order when imported to the odoo")
    ks_order_status = fields.Many2many("ks.order.status", string="Order Status",
                                       help="Shows the configuration of the imported order status")
    ks_order_import_type = fields.Selection([('status', 'Status')], default="status",
                                            string="Import Orders through",
                                            help="Shows the status of orders imported portal")
    ks_custom_order_prefix = fields.Char(string="Order Prefix", default='SC',
                                         help="Prefix added on orders imported from shopify to odoo is shown here")
    ks_default_order_prefix = fields.Boolean(string="Default Order Prefix",
                                             help="Enables/disables - default order prefix of the Odoo")
    ks_sales_team = fields.Many2one('crm.team', string="Sales Team", help="Shows the location of the sales team")
    ks_sales_person = fields.Many2one('res.users', string="Sales Person", help="Displays the name of the sales person")
    ks_dashboard_id = fields.Many2one('ks.shopify.dashboard', string="Dashboard id")
    ks_email_ids = fields.One2many('ks.email.entry', 'ks_shopify_instance', string="Email Ids")
    ks_payment_term_id = fields.Many2one('account.payment.term', string='Payment Term',
                                         help="Shows the payment term/mechanism")
    ks_auto_order_status_update_to_shopify = fields.Boolean(string="Auto Order Status Update to Shopify",
                                                            help="Enables/disables - automatically order status synchronisation with Shopify")

    # Product Information
    ks_sync_images = fields.Boolean('Shopify Sync/Import Images?',
                                    help=_("If checked, it will automatically Import Product"
                                           "image while import product process, else not"))
    ks_sync_price = fields.Boolean('Shopify Sync/Import Price?',
                                   help=_("If checked, it will configure the Pricelist and set"
                                          " price into it for the Instance, else not."))
    # ks_locations = fields.Many2one('ks.shopify.locations', 'Shopify Stock Location')
    ks_primary_locations = fields.Char('Shopify Primary Location Id')
    ks_stock_field_type = fields.Many2one('ir.model.fields', 'Stock Field Type',
                                          domain="[('model_id', '=', 'product.product'),"
                                                 "('name', 'in', ['free_qty','virtual_available'])]",
                                          help="Choose the field by which you want to update the stock in Shopify "
                                               "based on Free To Use(Quantity On Hand - Outgoing + Incoming) or "
                                               "Forecasted Quantity (Quantity On Hand - Reserved quantity).")

    ks_webhook_conf = fields.One2many('ks.shopify.webhooks.configuration', 'ks_instance_id', string="Webhooks")
    ks_customers_count = fields.Integer(string="Customer Counts", compute='_compute_counts_for_domains')
    ks_coupons_count = fields.Integer(string="Coupons Counts", compute='_compute_counts_for_domains')
    ks_products_count = fields.Integer(string="Products Counts", compute='_compute_counts_for_domains')
    ks_orders_count = fields.Integer(string="Orders Count", compute='_compute_counts_for_domains')

    ks_exported_counts = fields.Integer(string="Exported Counts", compute="_compute_counts_for_status")
    ks_ready_exported_counts = fields.Integer(string="Ready to Export", compute="_compute_counts_for_status")
    ks_published_counts = fields.Integer(string="Published", compute="_compute_counts_for_status")
    ks_unpublished_counts = fields.Integer(string="Unpubished", compute="_compute_counts_for_status")
    ks_quotation_counts = fields.Integer(string="Quotations", compute="_compute_counts_for_status")
    ks_orders_counts = fields.Integer(string="orders", compute="_compute_counts_for_status")
    ks_waiting_available_count = fields.Integer(string="Waiting Available", compute="_compute_counts_for_status")
    ks_partially_available_count = fields.Integer(string="Partially Available", compute="_compute_counts_for_status")
    ks_ready_transfer_count = fields.Integer(string="Ready Transfer", compute="_compute_counts_for_status")
    ks_transferred_count = fields.Integer(string="Transferred", compute="_compute_counts_for_status")
    ks_open_count = fields.Integer(string="Open Invoices", compute="_compute_counts_for_status")
    ks_paid_count = fields.Integer(string="Paid Count", compute="_compute_counts_for_status")
    ks_refund_count = fields.Integer(string="Refund Counts", compute="_compute_counts_for_status")

    ks_aip_cron_id = fields.Many2one('ir.cron', readonly=1, string="Auto Import Product Cron")
    ks_aio_cron_id = fields.Many2one('ir.cron', readonly=1, string="Auto Import Order Cron")
    ks_aep_cron_id = fields.Many2one('ir.cron', readonly=1, string="Auto Export Product Cron")
    ks_aic_cron_id = fields.Many2one('ir.cron', readonly=1, string="AUto Import Customer Cron")
    ks_aps_cron_id = fields.Many2one('ir.cron', readonly=1, string="Product Auto Sync Cron")

    ks_invoice_tax_account = fields.Many2one('account.account', string="Invoice TAX Account",
                                             help="Show the tax account which will be used for invoice tax default account")
    ks_credit_tax_account = fields.Many2one('account.account', string="Credit Note TAX Account",
                                            help="Show the tax account which will be used for Credit Note/Refund tax default account")

    ks_meta_fields_map = fields.Boolean(string="Require Meta Mapping ?", help="If you turn this on, you can initiate the excellent meta mapping feature")
    ks_meta_mapping_ids = fields.One2many("ks.shopify.meta.mapping", "ks_shopify_instance_id", string="Meta Mappings")

    def _compute_counts_for_status(self):
        for rec in self:
            rec.ks_exported_counts = rec.env['ks.shopify.product.template'].search_count([
                ('ks_shopify_instance', '=', rec.id), ('ks_shopify_product_id', 'not in', [False, 0])])
            rec.ks_ready_exported_counts = rec.env['ks.shopify.product.template'].search_count([
                ('ks_shopify_instance', '=', rec.id), ('ks_shopify_product_id', 'in', [False, 0])])
            rec.ks_published_counts = rec.env['ks.shopify.product.template'].search_count([
                ('ks_shopify_instance', '=', rec.id), ('ks_shopify_product_template', '!=', False),
                ('ks_published', '=', True)])
            rec.ks_unpublished_counts = rec.env['ks.shopify.product.template'].search_count([
                ('ks_shopify_instance', '=', rec.id), ('ks_shopify_product_template', '!=', False),
                ('ks_published', '=', False)])
            rec.ks_quotation_counts = rec.env['sale.order'].search_count([
                ('ks_shopify_instance', '=', rec.id), ('state', '=', 'draft')])
            rec.ks_orders_counts = rec.env['sale.order'].search_count([
                ('ks_shopify_instance', '=', rec.id), ('state', '=', 'sale')])
            rec.ks_waiting_available_count = rec.env['stock.picking'].search_count([
                ('state', '=', 'waiting'), ('sale_id.ks_shopify_instance', '=', rec.id),
                ('sale_id.ks_shopify_order_id', 'not in', [0, False])])
            rec.ks_partially_available_count = rec.env['stock.picking'].search_count(
                [('state', '=', 'confirmed'), ('sale_id.ks_shopify_instance', '=', rec.id),
                 ('sale_id.ks_shopify_order_id', 'not in', [0, False])])
            rec.ks_ready_transfer_count = rec.env['stock.picking'].search_count(
                [('state', '=', 'assigned'), ('sale_id.ks_shopify_instance', '=', rec.id),
                 ('sale_id.ks_shopify_order_id', 'not in', [0, False])])
            rec.ks_transferred_count = rec.env['stock.picking'].search_count([
                ('state', '=', 'done'), ('sale_id.ks_shopify_instance', '=', rec.id),
                ('sale_id.ks_shopify_order_id', 'not in', [0, False])])
            rec.ks_open_count = rec.env['account.move'].search_count([
                ('state', '=', 'draft'), ('ks_shopify_order_id.ks_shopify_instance', '=', rec.id),
                ('ks_shopify_order_uni_id', 'not in', [0, False])])
            rec.ks_paid_count = rec.env['account.move'].search_count([
                ('payment_state', '=', 'paid'), ('ks_shopify_order_id.ks_shopify_instance', '=', rec.id),
                ('ks_shopify_order_uni_id', 'not in', [0, False])])
            rec.ks_refund_count = rec.env['account.move'].search_count([
                ('payment_state', '=', 'reversed'), ('ks_shopify_order_id.ks_shopify_instance', '=', rec.id),
                ('ks_shopify_order_uni_id', 'not in', [0, False])])

    def _compute_counts_for_domains(self):
        for rec in self:
            domain = [('ks_shopify_instance', '=', rec.id)]
            rec.ks_customers_count = rec.env['ks.shopify.partner'].search_count([('ks_shopify_instance', '=', rec.id),
                                                                                 ('ks_type', '=', 'customer')])
            rec.ks_coupons_count = rec.env['ks.shopify.discounts'].search_count(domain)
            rec.ks_products_count = rec.env['ks.shopify.product.template'].search_count(domain)
            rec.ks_orders_count = rec.env['sale.order'].search_count(domain)

    def ks_open_shopify_products(self):
        action = self.sudo().env.ref('ks_shopify.action_ks_shopify_product_template_').read()[0]
        action['domain'] = [('ks_shopify_instance', '=', self.id)]
        return action

    def ks_open_shopify_coupons(self):
        action = self.sudo().env.ref('ks_shopify.ks_shopify_discounts_action').read()[0]
        action['domain'] = [('ks_shopify_instance', '=', self.id)]
        return action

    def ks_open_shopify_customers(self):
        action = self.sudo().env.ref('ks_shopify.action_ks_shopify_partner').read()[0]
        action['domain'] = [('ks_shopify_instance', '=', self.id)]
        return action

    def ks_open_shopify_orders(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_sale_order_quote').read()[0]
        action['domain'] = [('ks_shopify_instance', '=', self.id)]
        return action

    def open_exported(self):
        action = self.sudo().env.ref('ks_shopify.action_ks_shopify_product_template_').read()[0]
        action['domain'] = [('ks_shopify_instance', '=', self.id), ('ks_shopify_product_id', 'not in', [False, 0])]
        return action

    def open_ready_to_export(self):
        action = self.sudo().env.ref('ks_shopify.action_ks_shopify_product_template_').read()[0]
        action['domain'] = [('ks_shopify_instance', '=', self.id), ('ks_shopify_product_id', 'in', [False, 0])]
        return action

    def open_published(self):
        action = self.sudo().env.ref('ks_shopify.action_ks_shopify_product_template_').read()[0]
        action['domain'] = [('ks_shopify_instance', '=', self.id), ('ks_published', '=', True)]
        return action

    def open_unpublished(self):
        action = self.sudo().env.ref('ks_shopify.action_ks_shopify_product_template_').read()[0]
        action['domain'] = [('ks_shopify_instance', '=', self.id), ('ks_published', '=', False)]
        return action

    def open_quotations(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_sale_order_quote').read()[0]
        action['domain'] = [('ks_shopify_instance', '=', self.id), ('state', '=', 'draft')]
        return action

    def open_orders(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_sale_order_quote').read()[0]
        action['domain'] = [('ks_shopify_instance', '=', self.id), ('state', '=', 'sale')]
        return action

    def open_sales_analysis(self):
        action = self.sudo().env.ref('ks_shopify.shopify_action_sales_report_all').read()[0]
        action['domain'] = [('ks_shopify_instance', '=', self.id)]
        return action

    def open_payment_method(self):
        action = self.sudo().env.ref('ks_shopify.ks_shopify_payment_view_action').read()[0]
        action['domain'] = [('ks_shopify_instance', '=', self.id)]
        return action

    def open_waiting_available(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_deliveries').read()[0]
        action['domain'] = [('sale_id.ks_shopify_instance', '=', self.id),
                            ('sale_id.ks_shopify_order_id', 'not in', [False, 0]), ('state', '=', 'waiting')]
        return action

    def open_partially_available(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_deliveries').read()[0]
        action['domain'] = [('sale_id.ks_shopify_instance', '=', self.id),
                            ('sale_id.ks_shopify_order_id', 'not in', [False, 0]), ('state', '=', 'confirmed')]
        return action

    def open_ready_transfer(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_deliveries').read()[0]
        action['domain'] = [('sale_id.ks_shopify_instance', '=', self.id),
                            ('sale_id.ks_shopify_order_id', 'not in', [False, 0]), ('state', '=', 'assigned')]
        return action

    def open_transferred(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_deliveries').read()[0]
        action['domain'] = [('sale_id.ks_shopify_instance', '=', self.id),
                            ('sale_id.ks_shopify_order_id', 'not in', [False, 0]), ('state', '=', 'done')]
        return action

    def open_invoice(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_invoices').read()[0]
        action['domain'] = [('state', '=', 'draft'), ('ks_shopify_order_uni_id', 'not in', [False, 0]),
                            ('ks_shopify_order_id.ks_shopify_instance', '=', self.id)]
        return action

    def open_paid_invoice(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_invoices').read()[0]
        action['domain'] = [('payment_state', '=', 'paid'), ('ks_shopify_order_uni_id', 'not in', [False, 0]),
                            ('ks_shopify_order_id.ks_shopify_instance', '=', self.id)]
        return action

    def open_refund_invoice(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_invoices').read()[0]
        action['domain'] = [('payment_state', '=', 'reversed'), ('ks_shopify_order_uni_id', 'not in', [False, 0]),
                            ('ks_shopify_order_id.ks_shopify_instance', '=', self.id)]
        return action

    def ks_manage_priclists(self):
        """
        Manages the pricelist based on single and multiple currencies
        :return: None
        """
        # Manages all the pricelists
        self.ensure_one()
        pricelists = self.env['product.pricelist']
        if self.ks_shopify_currency:
            main_regular_price_list, main_sale_price_list = self.ks_check_for_pricelists(self.ks_shopify_currency)
            self.ks_shopify_regular_pricelist = main_regular_price_list
            pricelists += main_regular_price_list
            self.ks_shopify_compare_pricelist = main_sale_price_list
            pricelists += main_sale_price_list
        for currency in self.ks_shopify_multi_currency:
            main_regular_price_list, main_sale_price_list = self.ks_check_for_pricelists(currency)
            pricelists += main_regular_price_list
            pricelists += main_sale_price_list
        self.ks_shopify_pricelist_ids = [(6, 0, pricelists.ids)]

    def ks_check_for_pricelists(self, currency):

        """
        Check if pricelist is available or not
        :param currency: currency model many2one domain
        :return: pricelists domain regular and sale
        """
        self.ensure_one()
        regular_price_list = self.env['product.pricelist'].search([('ks_shopify_instance', '=', self.id),
                                                                   ('ks_shopify_regular_pricelist', '=', True),
                                                                   ('currency_id', '=', currency.id)])
        compare_price_list = self.env['product.pricelist'].search([('ks_shopify_instance', '=', self.id),
                                                                   ('ks_shopify_compare_pricelist', '=', True),
                                                                   ('currency_id', '=', currency.id)])
        if not regular_price_list:
            regular_price_list = self.env['product.pricelist'].create({
                'name': '[ ' + self.ks_instance_name + ' ] ' + currency.name + ' Regular Pricelist',
                'currency_id': currency.id,
                'company_id': self.ks_company_id.id,
                'ks_shopify_instance': self.id,
                'ks_shopify_regular_pricelist': True
            })
        if not compare_price_list:
            compare_price_list = self.env['product.pricelist'].create({
                'name': '[ ' + self.ks_instance_name + ' ] ' + currency.name + ' Compare Pricelist',
                'currency_id': currency.id,
                'company_id': self.ks_company_id.id,
                'ks_shopify_instance': self.id,
                'ks_shopify_compare_pricelist': True
            })
        return regular_price_list, compare_price_list

    @api.model
    def create(self, values):

        """
        creates one time usable dashboard kanban
        :param values: create method vals
        :return: current domain
        """
        if values.get('ks_store_url') and values.get('ks_customer_key') and values.get('ks_customer_password'):
            ks_url = values.get('ks_store_url').split("//")
            if len(ks_url)>1:
                ks_host = ks_url[0] + "//" + str(values.get('ks_customer_key')) + ":" + str(
                    values.get('ks_customer_password')) + "@" + ks_url[
                              1]
                values.update({
                    'ks_shopify_url': ks_host,
                })
        res = super(KsShopifyCommerceConnectorInstance, self).create(values)
        res.ks_manage_auto_job()
        # values.update({
        #     'ks_dashboard_id': self.env.ref("ks_shopify.ks_shopify_dashboard_1").id
        # })
        if values.get('ks_shopify_currency') or values.get('ks_shopify_multi_currency'):
            res.ks_manage_priclists()
        return res

    def write(self, values):
        """
        Updates the pricelist
        :param values: The updated data
        :return: Boolean value
        """
        # Write method overwritten
        ks_host = self.ks_shopify_url
        ks_url = self.ks_store_url.split('//') if self.ks_store_url else False
        ks_customer_key = values.get('ks_customer_key') if values.get('ks_customer_key') and values.get('ks_customer_key') != self.ks_customer_key else self.ks_customer_key
        ks_customer_password = values.get('ks_customer_password') if values.get('ks_customer_password') and values.get('ks_customer_password') != self.ks_customer_password else self.ks_customer_password
        ks_last_url = ks_url[1] if ks_url and len(ks_url)>1 else False
        if values.get('ks_store_url') and values.get('ks_store_url') != self.ks_store_url:
            ks_url = values.get('ks_store_url').split("//")
            if len(ks_url)>1:
                ks_last_url = ks_url[1]
                ks_host = ks_url[0] + "//" + str(ks_customer_key) + ":" + str(ks_customer_password) + "@" + ks_url[1]
        if ks_url and ks_last_url:
            if values.get('ks_customer_key') and values.get('ks_customer_key') != self.ks_customer_key:
                ks_host = ks_url[0] + "//" + str(values.get('ks_customer_key')) + ":" + str(
                        ks_customer_password) + "@" + ks_last_url
            if values.get('ks_customer_password') and values.get('ks_customer_password') != self.ks_customer_password:
                ks_host = ks_url[0] + "//" + str(ks_customer_key) + ":" + str(
                    values.get('ks_customer_password')) + "@" + ks_last_url
        values.update({
            'ks_shopify_url': ks_host,
        })
        res = super(KsShopifyCommerceConnectorInstance, self).write(values)
        if values.get('ks_shopify_currency') or values.get('ks_shopify_multi_currency'):
            # manage the price lists according to the currency selected
            self.ks_manage_priclists()
        return res

    def ks_manage_auto_job(self):
        # Manages auto job for stocks, order, updates etc
        if not self.ks_aic_cron_id:
            auto_import_customer_values = {
                'name': '[' + str(
                    self.id) + '] - ' + self.ks_instance_name + ': ' + 'Shopify Auto Customer Import from Shopify to Odoo (Do Not Delete)',
                'interval_number': 1,
                'interval_type': 'days',
                'user_id': self.env.user.id,
                'model_id': self.env.ref('ks_shopify.model_ks_shopify_partner').id,
                'state': 'code',
                'active': False,
                'numbercall': -1,
                'ks_shopify_instance': self.id,
            }
            self.ks_aic_cron_id = self.sudo().env['ir.cron'].create(auto_import_customer_values)
            self.sudo().ks_aic_cron_id.code = 'model.ks_auto_import_shopify_customer(' + str(self.ks_aic_cron_id.id) + ')'
        if not self.ks_aep_cron_id:
            auto_export_product_values = {
                'name': '[' + str(
                    self.id) + '] - ' + self.ks_instance_name + ': ' + 'Shopify Auto Product Export from Oddoo to Shopify (Do Not Delete)',
                'interval_number': 1,
                'interval_type': 'days',
                'user_id': self.env.user.id,
                'model_id': self.env.ref('ks_shopify.model_ks_shopify_product_template').id,
                'state': 'code',
                'active': False,
                'numbercall': -1,
                'ks_shopify_instance': self.id,
            }
            self.ks_aep_cron_id = self.sudo().env['ir.cron'].create(auto_export_product_values)
            self.sudo().ks_aep_cron_id.code = 'model.ks_product_list_for_cron(' + str(self.ks_aep_cron_id.id) + ')'
        if not self.ks_aip_cron_id:
            auto_import_product_values = {
                'name': '[' + str(
                    self.id) + '] - ' + self.ks_instance_name + ': ' + 'Shopify Auto Product Import from Shopify to Odoo (Do Not Delete)',
                'interval_number': 1,
                'interval_type': 'days',
                'user_id': self.env.user.id,
                'model_id': self.env.ref('ks_shopify.model_ks_shopify_product_template').id,
                'state': 'code',
                'active': False,
                'numbercall': -1,
                'ks_shopify_instance': self.id,
            }
            self.ks_aip_cron_id = self.sudo().env['ir.cron'].create(auto_import_product_values)
            self.sudo().ks_aip_cron_id.code = 'model.ks_auto_import_shopify_product(' + str(self.ks_aip_cron_id.id) + ')'
        if not self.ks_aio_cron_id:
            auto_import_order_values = {
                'name': '[' + str(
                    self.id) + '] - ' + self.ks_instance_name + ': ' + 'Shopify Auto Order Import from Shopify to Odoo (Do Not Delete)',
                'interval_number': 1,
                'interval_type': 'days',
                'user_id': self.env.user.id,
                'model_id': self.env.ref('ks_shopify.model_sale_order').id,
                'state': 'code',
                'active': False,
                'numbercall': -1,
                'ks_shopify_instance': self.id,
            }
            self.ks_aio_cron_id = self.sudo().env['ir.cron'].create(auto_import_order_values)
            self.sudo().ks_aio_cron_id.code = 'model.ks_auto_import_shopify_order(' + str(self.ks_aio_cron_id.id) + ')'

        if not self.ks_aps_cron_id:
            auto_product_sync_values = {
                'name': '[' + str(
                    self.id) + '] - ' + self.ks_instance_name + ': ' + 'Shopify Auto Product Sync from Shopify to Odoo (Do Not Delete)',
                'interval_number': 1,
                'interval_type': 'days',
                'user_id': self.env.user.id,
                'model_id': self.env.ref('ks_shopify.model_ks_shopify_auto_product_syncing_configuration').id,
                'state': 'code',
                'active': False,
                'numbercall': -1,
                'ks_shopify_instance': self.id,
            }
            self.ks_aps_cron_id = self.sudo().env['ir.cron'].create(auto_product_sync_values)
            self.sudo().ks_aps_cron_id.code = 'model.ks_auto_product_syncing(' + str(self.ks_aps_cron_id.id) + ')'

    def get_all_cron_ids(self):
        # Fetches all the active cron ids
        self.ks_manage_auto_job()
        cron_list = []
        if self.ks_aic_cron_id:
            cron_list.append(self.ks_aic_cron_id.id)
        if self.ks_aep_cron_id:
            cron_list.append(self.ks_aep_cron_id.id)
        if self.ks_aip_cron_id:
            cron_list.append(self.ks_aip_cron_id.id)
        if self.ks_aio_cron_id:
            cron_list.append(self.ks_aio_cron_id.id)
        if self.ks_aps_cron_id:
            cron_list.append(self.ks_aps_cron_id.id)
        if self.ks_aic_cron_id.search([('name', '=', 'KS: Shopify Sales Report')]):
            cron_list.append(self.ks_aic_cron_id.search([('name', '=', 'KS: Shopify Sales Report')]).id)
        return cron_list

    def action_all_crons(self):
        # action window returns all the crons
        all_cron_ids = self.get_all_cron_ids()
        action = {
            'domain': [('id', 'in', all_cron_ids), ('active', 'in', (True, False))],
            'name': 'Shopify Schedulers',
            'view_mode': 'tree,form',
            'res_model': 'ir.cron',
            'type': 'ir.actions.act_window',
        }
        return action

    def action_active_crons(self):
        # action window returns all the active crons
        all_cron_ids = self.get_all_cron_ids()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Shopify Schedulers',
            'res_model': 'ir.cron',
            'domain': [('id', 'in', all_cron_ids), ('active', '=', True)],
            'view_mode': 'tree,form',
        }

    def action_all_pricelists(self):
        """
        Pricelist wizard for the current instance
        :return: the wizard data
        """
        # action window returns for pricelists
        return {
            'type': 'ir.actions.act_window',
            'name': 'Shopify Price Lists',
            'res_model': 'product.pricelist',
            'domain': [('id', 'in', self.ks_shopify_pricelist_ids.ids), ('ks_shopify_instance', '=', self.id)],
            'view_mode': 'tree,form',
            'help': """<p class="o_view_nocontent_empty_folder">{}</p>""".format(_('All the pricelist created for '
                                                                                   'Shopify Instances will appear '
                                                                                   'here'))
        }

    def ks_shopify_activate_instance(self):
        """
        Activates the Instance based on the information required
        :return: Success Wizard
        """
        if self.ks_instance_connected and self.ks_instance_state == 'connected':
            self.ks_instance_state = 'active'
            return self.env["ks.message.wizard"].ks_pop_up_message("Active",
                                                                   "Instance  Activated")

    def ks_shopify_deactivate_instance(self):
        """
        DeActivates the Instance based on the information required
        :return: Success Wizard
        """
        if self.ks_instance_connected and self.ks_instance_state == 'active':
            self.ks_instance_state = 'deactivate'
            return self.env["ks.message.wizard"].ks_pop_up_message("Deactivated",
                                                                   "Instance  Deactivated")

    def ks_shopify_connect_to_instance(self):
        """
        This will Connect the Odoo Instance to Shopify and Return the Pop-up window
        with the Response
        :return: ks.message.wizard() Action window with response message or Validation Error Pop-up
        """
        try:
            ks_url = self.ks_store_url.split("//")
            if len(ks_url) > 1:
                ks_shopify_url = self.env['ks.api.handler']._ks_generate_generic_url(self, 'shop', 'shop')
                shopify_api = requests.get(ks_shopify_url)
                if shopify_api.status_code in [200, 201]:
                    json_data = shopify_api.json()
                    message = 'Connection Successful'
                    names = 'Success'
                    self.ks_instance_connected = True
                    self.ks_instance_state = 'connected'
                    self.ks_shopify_shop_id = json_data.get('shop').get('id')
                    self.ks_shopify_shop_name = json_data.get('shop').get('name')
                    self.ks_primary_locations = json_data.get('shop').get('primary_location_id')
                    ks_currency = self.env['res.currency'].sudo().search(
                        [('name', '=', json_data.get('shop').get('currency')), ('active', 'in', [True, False])],
                        limit=1) if json_data.get('shop').get('currency') else False
                    if ks_currency:
                        ks_currency.active = True
                        self.sudo().ks_shopify_currency = ks_currency.id
                    if len(self.ks_webhook_conf) == 0:
                        self.ks_manage_webhooks()
                else:
                    message = (str(shopify_api.status_code) + ': ' + eval(shopify_api.text.split(":")[1].split("}")[0]))
                    names = 'Error'
                return self.env["ks.message.wizard"].ks_pop_up_message(names, message)
            else:
                raise ValidationError("Please check credential or URL")
        except (ConnectionError, ValueError):
            raise ValidationError(
                "Couldn't Connect the instance !! Please check the network connectivity or the configuration or Store "
                "URL "
                " parameters are "
                "correctly set.")
        except Exception as e:
            raise ValidationError(_(e))

    def ks_open_shopify_configuration(self):
        """
        Action window to open configurations
        :return: The form view for the configuration
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Shopify Operations',
            'view': 'form',
            'res_id': self.id,
            'res_model': 'ks.shopify.connector.instance',
            'view_mode': 'form',
        }

    def open_specific_operation_form_action(self):
        # Opens operations wizard with current instance in context
        view = self.env.ref('ks_shopify.ks_specific_operations_form_view')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Shopify Operations',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'res_model': 'ks.instance.operations',
            'view_mode': 'form',
            'context': {'default_ks_instances': [(6, 0, [self.id])], 'default_shopify_instance': True,
                        "default_ks_check_multi_operation": False},
            'target': 'new',
        }

    def ks_open_instance_logs(self):
        # Action window to open logs
        action = self.sudo().env.ref('ks_shopify.ks_shopify_logs_action').read()[0]
        action['domain'] = [('ks_shopify_instance.id', '=', self.id)]
        return action

    def open_multiple_operation_form_action(self):
        # Opens operations wizard with current instance in context
        view = self.env.ref('ks_shopify.ks_multiple_operations_form_view')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Shopify Operations',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'res_model': 'ks.instance.operations',
            'view_mode': 'form',
            'context': {'default_ks_instances': [(6, 0, [self.id])], 'default_shopify_instance': True,
                        "default_ks_check_multi_operation": True},
            'target': 'new',
        }

    def ks_shopify_update_variants_response(self, json_data, odoo_records):

        """
        Updates any extra data from shopify to layer models
        :param json_data: api response json data
        :param odoo_record: layer model domain
        :param shopify_id_field: shopify unique id storage field
        :param other_data: dict(of extra data)
        """
        for odoo_variants in odoo_records:
            for shopify_variants in json_data.get('variants'):
                if (odoo_variants.ks_option1 or None) == shopify_variants.get('option1') and (
                        odoo_variants.ks_option2 or None) == shopify_variants.get('option2') and (
                        odoo_variants.ks_option3 or None) == shopify_variants.get('option3'):
                    data = {'ks_shopify_variant_id': shopify_variants.get('id') or "",
                            'ks_shopify_inventory_id': shopify_variants.get('inventory_item_id')}
            if json_data.get('updated_at'):
                data.update({
                    "ks_date_updated": self.ks_convert_datetime({'update_date': json_data.get('updated_at')}).get(
                        'update_date')
                })
            if json_data.get('created_at'):
                data.update({
                    "ks_date_created": self.ks_convert_datetime({'create_date': json_data.get('created_at')}).get(
                        'create_date')
                })
            if odoo_variants:
                odoo_variants.write(data)

    def ks_shopify_update_the_response(self, json_data, odoo_record, shopify_id_field, other_data=False):

        """
        Updates any extra data from shopify to layer models
        :param json_data: api response json data
        :param odoo_record: layer model domain
        :param shopify_id_field: shopify unique id storage field
        :param other_data: dict(of extra data)
        """
        data = {shopify_id_field: (json_data.get("order_id") if json_data.get('order_id') else json_data.get('id')) or ""}
        if shopify_id_field == "ks_shopify_order_id":
            data.update({'ks_order_name': json_data.get('name')})
        if shopify_id_field == "ks_shopify_product_variant_id":
            data.update({shopify_id_field: json_data.get("variants")[0].get("id") or ""})
        if shopify_id_field == "ks_shopify_product_id":
            data.update({"ks_shopify_inventory_id": json_data.get("variants")[0].get("inventory_item_id") or ""})
            odoo_record.ks_shopify_rp_pricelist.fixed_price = float(json_data.get("variants")[0].get('price') or 0.0)
            odoo_record.ks_shopify_cp_pricelist.fixed_price = float(json_data.get("variants")[0].get('compare_at_price') or 0.0)
        if json_data.get('updated_at'):
            data.update({
                "ks_date_updated": self.ks_convert_datetime({'update_date': json_data.get('updated_at')}).get(
                    'update_date')
            })
        if json_data.get('created_at'):
            data.update({
                "ks_date_created": self.ks_convert_datetime({'create_date': json_data.get('created_at')}).get(
                    'create_date')
            })
        if json_data.get('addresses') and odoo_record.ks_res_partner.child_ids:
            for i in range(len(json_data.get('addresses'))):
                ks_partner_shopify = odoo_record.ks_res_partner.child_ids[i].ks_partner_shopify_ids.filtered(
                                    lambda x: x.ks_shopify_instance == odoo_record.ks_shopify_instance)
                ks_partner_shopify.ks_shopify_partner_id = json_data.get('addresses')[i].get('id')

        if other_data:
            data.update(other_data)
        if odoo_record and not odoo_record._name == 'res.partner':
            odoo_record.write(data)

        if odoo_record._name == 'sale.order':
            self.ks_update_sale_order_lines(odoo_record, json_data)

    def ks_update_sale_order_lines(self, sale_order, json_data):
        if sale_order:
            for line in json_data.get('line_items'):
                ks_product_layer = self.env['ks.shopify.product.template'].search(
                    ['|', ('ks_shopify_product_id', '=', line.get('product_id')),
                     ('ks_shopify_product_variant_id', '=', line.get('product_id')),
                     ('ks_shopify_instance', '=', sale_order.ks_shopify_instance.id)], limit=1)
                if ks_product_layer.ks_shopify_product_type == 'variable':
                    ks_product_product = ks_product_layer.ks_shopify_variant_ids.filtered(
                        lambda x: x.ks_shopify_variant_id == str(
                            line.get('variant_id'))).ks_shopify_product_variant
                else:
                    ks_product_product = ks_product_layer.ks_product_product if ks_product_layer.ks_product_product else False
                if ks_product_product:
                    sale_order_line = sale_order.order_line.search([('product_id', '=', ks_product_product.id),
                                                                    ('ks_shopify_order_line_id', '=', False),
                                                                    ('order_id', '=', sale_order.id)], limit=1)
                    if sale_order_line:
                        sale_order_line.write({'ks_shopify_order_line_id': line.get('id')})

    def ks_convert_datetime(self, times):
        """
        :param times: json datetimes
        :return: datetime.datetime()
        """
        try:
            date_time = {}
            for index, time in times.items():
                if time:
                    value = datetime.fromisoformat(time)
                    value = value.astimezone(pytz.timezone(self.env.user.tz or 'UTC')).isoformat()
                    value = datetime.strptime(value.replace("T", ' ').split("+")[0], "%Y-%m-%d %H:%M:%S")
                    date_time[index] = value
            return date_time
        except Exception as e:
            raise e

    def ks_sync_webhooks(self):
        for rec in self:
            all_webhooks_data = rec.env['ks.api.handler'].ks_get_all_data(rec, "webhooks")
            allowed_domain = ['orders/create', 'orders/updated', 'products/create', 'products/update', 'customers/create',
                              'customers/update', 'collections/create', 'collections/update']
            filtered_data = list(filter(lambda x: x['topic'] in allowed_domain, all_webhooks_data))
            for data in filtered_data:
                rec_data = {
                    'name': '-'.join(data.get('topic').split('/')),
                    'operations': data.get("topic"),
                    'base_url': data.get("address"),
                    'ks_shopify_id': str(data.get("id"))
                }
                webhook_exist = rec.env['ks.shopify.webhooks.configuration'].search(
                    [('ks_shopify_id', '=', data.get('id'))])
                if webhook_exist:
                    rec.ks_webhook_conf = [(1, webhook_exist.id, rec_data)]
                # else:
                #     rec.ks_webhook_conf = [(0, 0, rec_data)]

    def ks_manage_webhooks(self):
        """
        Manages the webhook on the Odoo side
        :return: None
        """
        try:
            # Order Create Webhook
            base_url = self.ks_compute_base_url('orders/create')
            # data = self.ks_woocommerce_webhook_data("order_create", base_url)
            # response_data = self.env['ks.shopify.webhooks.configuration'].ks_create_webhook(self, data)
            vals = self.ks_odoo_webhook_data('orders/create', base_url)
            self.env['ks.shopify.webhooks.configuration'].create(vals)

            # Order Update Webhook
            base_url = self.ks_compute_base_url('orders/updated')
            # data = self.ks_woocommerce_webhook_data("order_update", base_url)
            # response_data = self.env['ks.shopify.webhooks.configuration'].ks_create_webhook(self, data)
            vals = self.ks_odoo_webhook_data('orders/updated', base_url)
            self.env['ks.shopify.webhooks.configuration'].create(vals)

            # Product Create Webhook
            base_url = self.ks_compute_base_url('products/create')
            # data = self.ks_woocommerce_webhook_data("product_create", base_url)
            # response_data = self.env['ks.shopify.webhooks.configuration'].ks_create_webhook(self, data)
            vals = self.ks_odoo_webhook_data('products/create', base_url)
            self.env['ks.shopify.webhooks.configuration'].create(vals)

            # Product Update Webhook
            base_url = self.ks_compute_base_url('products/update')
            # data = self.ks_woocommerce_webhook_data("product_update", base_url)
            # response_data = self.env['ks.shopify.webhooks.configuration'].ks_create_webhook(self, data)
            vals = self.ks_odoo_webhook_data('products/update', base_url)
            self.env['ks.shopify.webhooks.configuration'].create(vals)

            # Customer Create Webhook
            base_url = self.ks_compute_base_url('customers/create')
            # data = self.ks_woocommerce_webhook_data("customer_create", base_url)
            # response_data = self.env['ks.shopify.webhooks.configuration'].ks_create_webhook(self, data)
            vals = self.ks_odoo_webhook_data('customers/create', base_url)
            self.env['ks.shopify.webhooks.configuration'].create(vals)

            # Customer Update Webhook
            base_url = self.ks_compute_base_url('customers/update')
            # data = self.ks_woocommerce_webhook_data("customer_update", base_url)
            # response_data = self.env['ks.shopify.webhooks.configuration'].ks_create_webhook(self, data)
            vals = self.ks_odoo_webhook_data('customers/update', base_url)
            self.env['ks.shopify.webhooks.configuration'].create(vals)

            # Coupon Create Webhook
            base_url = self.ks_compute_base_url('collections/create')
            # data = self.ks_woocommerce_webhook_data("coupon_create", base_url)
            # response_data = self.env['ks.shopify.webhooks.configuration'].ks_create_webhook(self, data)
            vals = self.ks_odoo_webhook_data('collections/create', base_url)
            self.env['ks.shopify.webhooks.configuration'].create(vals)

            # Coupon Update Webhook
            base_url = self.ks_compute_base_url('collections/update')
            # data = self.ks_woocommerce_webhook_data("coupon_update", base_url)
            # response_data = self.env['ks.shopify.webhooks.configuration'].ks_create_webhook(self, data)
            vals = self.ks_odoo_webhook_data('collections/update', base_url)
            self.env['ks.shopify.webhooks.configuration'].create(vals)
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                               status="failed",
                                                               type="webhook",
                                                               instance=self,
                                                               operation_flow="shopify_to_odoo",
                                                               layer_model="ks.shopify.webhooks.configuration",
                                                               shopify_id=0,
                                                               message=str(e))

        else:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="fetch",
                                                               status="success",
                                                               type="webhook",
                                                               operation_flow="shopify_to_odoo",
                                                               instance=self,
                                                               layer_model="ks.shopify.webhooks.configuration",
                                                               shopify_id=0,
                                                               message="Fetch of Webhooks successful")

    def ks_odoo_webhook_data(self, name, base_url):
        """
        Creates dictionary data for the odoo side
        :param name: Name of the Webhook
        :param base_url: Base URL of the webhook
        :return: Dictionary
        """
        return {
            'name': " ".join(name.split("_")).title(),
            'operations': name,
            'status': 'disabled',
            'ks_instance_id': self.id,
            'base_url': base_url,
        }

    def ks_compute_base_url(self, operations):
        """
        Computes URL for controllers webhook to request data
        :return:
        """
        for rec in self:
            if rec.ks_instance_state in ['active', 'connected']:
                ks_base = rec.env['ir.config_parameter'].sudo().get_param('web.base.url')
                ks_base_updated = ks_base.split("//")
                if len(ks_base_updated) > 1:
                    ks_base = 'https://' + ks_base_updated[1]
                if operations:
                    selection_list = operations.split('/')
                    base_url = '%s/shopify_hook/%s/%s/%s/%s/%s' % (ks_base,
                                                                       base64.urlsafe_b64encode(
                                                                           self.env.cr.dbname.encode("utf-8")).decode(
                                                                           "utf-8"),
                                                                       str(self.env.user.id),
                                                                       self.id,
                                                                       selection_list[0],
                                                                       selection_list[1])
                else:
                    base_url = ''
            else:
                base_url = ''
                _logger.info("Instance should be Active or Connected")
            return base_url