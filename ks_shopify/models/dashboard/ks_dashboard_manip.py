import json

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class KsDashboard(models.Model):
    _name = 'ks.shopify.dashboard'
    _description = "Shopify Dashboard"

    ks_shopify_instance = fields.One2many("ks.shopify.connector.instance", 'ks_dashboard_id',
                                     string="Instance", readonly=True,
                                     help=("Shopify Connector Instance reference"))
    name = fields.Char(string='Name', default='dashboard')
    ks_chart_data = fields.Text(string="Chart Data", default=0, compute='_fetch_graph_data')
    ks_chart_data_pie = fields.Text(string="Pie Chart Data", default=0, compute='_fetch_graph_data')
    ks_graph_view = fields.Integer(string="Graph view", default=1)
    ks_customer_counts = fields.Integer(compute='_compute_count')
    search_domain = fields.Text()
    ks_instance_counts = fields.Integer(compute='_compute_count_instance')

    ks_product_counts = fields.Integer(compute='_compute_count')
    ks_order_counts = fields.Integer(compute='_compute_count')
    ks_invoice_counts = fields.Integer(compute='_compute_count')
    ks_variant_counts = fields.Integer(compute='_compute_count')
    ks_attribute_counts = fields.Integer(compute='_compute_count')
    ks_refund_counts = fields.Integer(compute='_compute_count')
    # ks_tag_counts = fields.Integer(compute='_compute_count')
    ks_delivery_counts = fields.Integer(compute='_compute_count')
    ks_collection_counts = fields.Integer(compute='_compute_count')
    ks_gateway_counts = fields.Integer(compute='_compute_count')
    ks_discount_counts = fields.Integer(compute='_compute_count')
    ks_inventory_counts = fields.Integer(compute='_compute_count')

    @api.model
    def fields_get(self, fields=None):
        fields_to_hide = ['id', 'create_uid', 'ks_graph_view', 'name', 'create_date', 'write_uid',
                          'write_date', 'search_domain']
        res = super(KsDashboard, self).fields_get()
        for field in fields_to_hide:
            res[field]['searchable'] = False
            res[field]['sortable'] = False
        return res

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        rec = super(KsDashboard, self).search_read()
        if domain:
            self = self.env['ks.shopify.dashboard'].search([])
            if len(self) > 1:
                raise ValidationError("Fatal Error on Dashboard Records")
            self.write({
                'search_domain': domain
            })
            ks_customer_counts, ks_product_counts, ks_order_counts, ks_invoice_counts, ks_variant_counts, \
            ks_attribute_counts, ks_refund_counts, ks_delivery_counts, \
            ks_collection_counts, ks_gateway_counts, ks_discount_counts, ks_inventory_counts = self._compute_count(domain)

            ks_instance_counts = self._compute_count_instance(domain)
            rec[0].update({
                'ks_customer_counts': ks_customer_counts,
                'ks_instance_counts': ks_instance_counts,
                'ks_product_counts': ks_product_counts,
                'ks_order_counts': ks_order_counts,
                'ks_invoice_counts': ks_invoice_counts,
                'ks_variant_counts': ks_variant_counts,
                'ks_attribute_counts': ks_attribute_counts,
                'ks_refund_counts': ks_refund_counts,
                'ks_delivery_counts': ks_delivery_counts,
                'ks_collection_counts': ks_collection_counts,
                'ks_gateway_counts': ks_gateway_counts,
                'ks_discount_counts': ks_discount_counts,
                'ks_inventory_counts': ks_inventory_counts
            })
        return rec

    def _fetch_graph_data(self):
        '''
        {"labels": ["20 February 2019", "23 February 2019", "09 March 2019", "23 March 2019", "23 April 2019",
        "27 April 2019", "14 May 2019", "25 May 2019", "19 June 2019", "29 June 2019", "20 July 2019", "25 July 2019",
        "11 August 2019", "17 August 2019", "07 September 2019", "21 September 2019", "18 October 2019",
        "23 October 2019", "13 November 2019", "22 November 2019", "10 December 2019", "19 December 2019",
        "15 January 2020", "24 January 2020", "11 February 2020", "25 February 2020", "25 March 2020", "07 April 2020",
        "11 December 2020", "12 December 2020", "13 December 2020", "14 December 2020", "15 December 2020",
        "16 December 2020", "17 December 2020"],
        "datasets": [{"data": [320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0,
        320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 640.0, 320.0, 4800.0, 6400.0,
        640.0, 320.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "label": "E-COM07 Large Cabinet/Previous"},
        {"data": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1913.1751759196936, 864.3191866560376, 467.88584237179487,
        619.9715699757315, 707.7056399383516, 688.6838666990753, 670.7339998648316],
        "label": "E-COM07 Large Cabinet/Forecast"}]}'''

        ks_raw_data = {}
        labels = {"labels": ['Products', 'Collections', 'Coupons', 'Customers',
                             'Orders']}
        labels_pie = {"labels": []}
        ks_raw_data_pie = {}
        ks_raw_data_pie.update(labels_pie)
        ks_raw_data.update(labels)
        datasets = {"datasets": []}
        new_points = []
        progress_points = []
        done_points = []
        failed_points = []
        new_data = {}
        progress_data = {}
        done_data = {}
        failed_data = {}
        # For Product
        ks_product_new_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'product_template'), ('state', '=', 'new')])
        ks_product_progress_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'product_template'), ('state', '=', 'progress')])
        ks_product_done_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'product_template'), ('state', '=', 'done')])
        ks_product_failed_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'product_template'), ('state', '=', 'failed')])

        # For Category
        ks_collection_new_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'collection'), ('state', '=', 'new')])
        ks_collection_progress_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'collection'), ('state', '=', 'progress')])
        ks_collection_done_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'collection'), ('state', '=', 'done')])
        ks_collection_failed_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'collection'), ('state', '=', 'failed')])

        # For Coupons
        ks_discount_new_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'discount'), ('state', '=', 'new')])
        ks_discount_progress_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'discount'), ('state', '=', 'progress')])
        ks_discount_done_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'discount'), ('state', '=', 'done')])
        ks_discount_failed_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'discount'), ('state', '=', 'failed')])

        # For Customers
        ks_customer_new_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'customer'), ('state', '=', 'new')])
        ks_customer_progress_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'customer'), ('state', '=', 'progress')])
        ks_customer_done_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'customer'), ('state', '=', 'done')])
        ks_customer_failed_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'customer'), ('state', '=', 'failed')])

        # For Orders
        ks_order_new_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'sale_order'), ('state', '=', 'new')])
        ks_order_progress_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'sale_order'), ('state', '=', 'progress')])
        ks_order_done_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'sale_order'), ('state', '=', 'done')])
        ks_order_failed_count = self.env['ks.shopify.queue.jobs'].search_count(
            [('ks_model', '=', 'sale_order'), ('state', '=', 'failed')])

        new_points.extend([ks_product_new_count, ks_collection_new_count,
                           ks_discount_new_count, ks_customer_new_count, ks_order_new_count
                        ])
        progress_points.extend([ks_product_progress_count,
                                ks_collection_progress_count,
                                ks_discount_progress_count, ks_customer_progress_count,
                                ks_order_progress_count])
        done_points.extend(
            [ks_product_done_count, ks_collection_done_count,
              ks_discount_done_count, ks_customer_done_count, ks_order_done_count
             ])
        failed_points.extend(
            [ks_product_failed_count, ks_collection_failed_count,
              ks_discount_failed_count, ks_customer_failed_count, ks_order_failed_count])

        new_data.update({"data": new_points, "label": "New State"})
        datasets['datasets'].append(new_data)
        progress_data.update({"data": progress_points, "label": "Progress State"})
        datasets['datasets'].append(progress_data)
        done_data.update({"data": done_points, "label": "Completed State"})
        datasets['datasets'].append(done_data)
        failed_data.update({"data": failed_points, "label": "Failed State"})
        datasets['datasets'].append(failed_data)

        ks_raw_data.update(datasets)
        ks_raw_data_pie.update(datasets)
        json_dump_for_pie = json.dumps(ks_raw_data_pie)
        self.ks_chart_data_pie = json_dump_for_pie
        json_dump = json.dumps(ks_raw_data)
        self.ks_chart_data = json_dump
        y = self.ks_chart_data

    def _compute_count_instance(self, domain=False):
        search_domain = domain
        if not domain:
            self.ks_instance_counts = self.ks_shopify_instance.search_count([])
        else:
            if len(search_domain) == 1 and search_domain[0][0] == 'ks_shopify_instance' and not search_domain[0][2]:
                search_domain = []
            self.ks_instance_counts = self.ks_shopify_instance.search_count(search_domain)
        return self.ks_instance_counts

    def _compute_count(self, domain=False):
        if not self:
            self = self.env['ks.shopify.dashboard'].search([])
            if len(self) > 1:
                raise ValidationError("Fatal Error on Dashboard Records")
        if not domain:
            domain = []
            self.search_domain = False
        customer_domain = [('ks_type', '=', 'customer')]
        self.ks_customer_counts = self.env['ks.shopify.partner'].search_count(customer_domain)
        self.ks_product_counts = self.env['ks.shopify.product.template'].search_count(domain)
        self.ks_order_counts = self.env['sale.order'].search_count(domain)
        invoice_domain = [('ks_shopify_order_uni_id', 'not in', ['0',0,False]),
                          ('move_type', '=', 'out_invoice')] if domain else []
        self.ks_invoice_counts = self.env['account.move'].search_count(invoice_domain)
        self.ks_variant_counts = self.env['ks.shopify.product.variant'].search_count(domain)
        self.ks_attribute_counts = self.env['ks.shopify.product.attribute'].search_count(domain)
        refund_domain = [('move_type', '=', 'out_refund'), ('ks_shopify_order_uni_id', 'not in', ['0',0,False])] if domain else []
        self.ks_refund_counts = self.env['account.move'].search_count(refund_domain)
        delivery_domain = [('sale_id.ks_shopify_order_id', 'not in', ['0',0,False])] if domain else []
        self.ks_delivery_counts = self.env['stock.picking'].search_count(delivery_domain)
        self.ks_collection_counts = self.env['ks.shopify.custom.collections'].search_count(domain)
        self.ks_gateway_counts = self.env['ks.shopify.payment.gateway'].search_count(domain)
        self.ks_discount_counts = self.env['ks.shopify.discounts'].search_count(domain)
        inventory_domain = [('for_shopify', '=', True)] if domain else []
        self.ks_inventory_counts = self.env['stock.inventory'].search_count(inventory_domain)
        return self.ks_customer_counts, self.ks_product_counts, self.ks_order_counts, self.ks_invoice_counts, \
               self.ks_variant_counts, self.ks_attribute_counts, self.ks_refund_counts, \
               self.ks_delivery_counts, self.ks_collection_counts, self.ks_gateway_counts, self.ks_discount_counts, self.ks_inventory_counts

    def ks_get_domain_parse(self, domain=False):
        domain_parse = []
        if self.search_domain:
            domain = eval(self.search_domain)
            for li in domain:
                if type(li) == list:
                    domain_parse.append(tuple(li))
                else:
                    domain_parse.append(li)
        else:
            domain_parse = domain
        return domain_parse

    def get_ks_instances(self):
        domain_parse = []
        if self.sudo().search_domain:
            domain = eval(self.search_domain)
            for li in domain:
                if type(li) == list:
                    domain_parse.append(tuple(li))
                else:
                    domain_parse.append(li)
            if domain_parse:
                for i in range(len(domain_parse)):
                    if isinstance(domain_parse[i], tuple):
                        temp = list(domain_parse[i])
                        temp[0] = 'ks_instance_name'
                        temp = tuple(temp)
                        domain_parse[i] = temp
        action = self.sudo().env.ref('ks_shopify.action_ks_shopify_connector_instance').read()[0]
        action['domain'] = domain_parse
        return action

    def get_ks_customers(self):
        action = self.sudo().env.ref('ks_shopify.action_ks_shopify_partner').read()[0]
        action['domain'] = self.ks_get_domain_parse(action['domain'])
        return action

    def get_ks_products(self):
        action = self.sudo().env.ref('ks_shopify.action_ks_shopify_product_template_').read()[0]
        action['domain'] = self.ks_get_domain_parse(action['domain'])
        return action

    def get_ks_variants(self):
        action = self.sudo().env.ref('ks_shopify.action_ks_shopify_product_variants_').read()[0]
        action['domain'] = self.ks_get_domain_parse(action['domain'])
        return action

    def get_ks_attributes(self):
        action = self.sudo().env.ref('ks_shopify.action_ks_shopify_product_attribute').read()[0]
        action['domain'] = self.ks_get_domain_parse(action['domain'])
        return action

    def get_ks_refunds(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_refund').read()[0]
        action['domain'] = [('move_type', '=', 'out_refund'), ('ks_shopify_order_uni_id', 'not in', ['0',0,False])]
        return action

    def get_ks_categories(self):
        action = self.sudo().env.ref('ks_shopify.ks_shopify_collection_actions').read()[0]
        action['domain'] = self.ks_get_domain_parse(action['domain'])
        return action

    def get_ks_orders(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_sale_order_quote').read()[0]
        action['domain'] = self.ks_get_domain_parse(action['domain'])
        return action

    def get_ks_coupons(self):
        action = self.sudo().env.ref('ks_shopify.ks_shopify_discounts_action').read()[0]
        action['domain'] = self.ks_get_domain_parse(action['domain'])
        return action

    def get_ks_invoices(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_invoices').read()[0]
        action['domain'] = [('ks_shopify_order_uni_id', 'not in', ['0',0,False]), ('move_type', '=', 'out_invoice')]
        return action

    def get_ks_payment_gateways(self):
        action = self.sudo().env.ref('ks_shopify.ks_shopify_payment_view_action').read()[0]
        action['domain'] = self.ks_get_domain_parse(action['domain'])
        return action

    def get_ks_delivery(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_deliveries').read()[0]
        action['domain'] = [('sale_id.ks_shopify_order_id', 'not in', ['0',0,False])]
        return action

    def get_inventory(self):
        action = self.sudo().env.ref('ks_shopify.action_shopify_inventory_adjustments').read()[0]
        action['domain'] = [('for_shopify', '=', True)]
        return action
