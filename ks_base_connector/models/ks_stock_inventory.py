# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class KsBaseStockInventory(models.Model):
    _inherit = "stock.inventory"

    @api.model
    def ks_create_stock_inventory_adjustment(self, product_data, location_id, auto_validate=False, queue_record = False):
        """
        This create the Inventory adjustment with the products and location
        :param product_data: list of dictionary {"product_id": 0, "product_qty": 0}
        :param location_id: stock.location() object
        :param auto_validate: If given the validate the adjustment created
        :return: stock.inventory() if created
        """
        try:
            if product_data:
                inventories = self
                while product_data:
                    inventory_lines = product_data[:100]
                    inventory_products = [line['product_id'] for line in inventory_lines]
                    inventory_name = 'product_inventory_%s' % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    inventory_values = {
                                        'name': inventory_name,
                                        'location_ids': [(6, 0, [location_id.id])] if location_id else False,
                                        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        'product_ids': [(6, 0, inventory_products)],
                                        'prefill_counted_quantity': 'zero',
                                        "company_id": location_id.company_id.id if location_id else self.env.company.id
                                    }
                    inventory = self.create(inventory_values)
                    inventory.ks_create_inventory_adjustment_lines(inventory_lines, location_id)
                    inventory.action_start()
                    if auto_validate:
                        inventory.action_validate()
                    inventories += inventory
                    del product_data[:100]

                return inventories
            return False
        except Exception as e:
            if queue_record:
                queue_record.ks_update_failed_state()
            _logger.info(str(e))
            raise e
            # self.env['ks.woo.logger'].ks_create_odoo_log_param(
            #     ks_operation_performed="create",
            #     ks_model='stock.inventory',
            #     ks_layer_model='stock.inventory',
            #     ks_message=str(e),
            #     ks_status="failed",
            #     ks_type="stock",
            #     ks_record_id=0,
            #     ks_operation_flow="odoo_to_woo",
            #     ks_woo_id=0,
            #     ks_woo_instance=False)

    @api.model
    def ks_create_inventory_adjustment_lines(self, products_data, location_id):
        """
        Create the inventory adjustment line with the product and the qty in Products data
        :param products_data: list of dictionary {"product_id": 0, "product_qty": 0}
        :param location_id: stock.location() object
        :return: True
        """
        values_list = []
        for product in products_data:
            product_id = product.get('product_id')
            product_qty = product.get('product_qty')
            if product and product_qty:
                values = {
                    'company_id': self.company_id.id,
                    'product_id': product_id,
                    'inventory_id': self.id,
                    'location_id': location_id.id,
                    'product_qty': 0 if product_qty <= 0 else product_qty,
                }
                values_list.append(values)
        self.env['stock.inventory.line'].create(values_list)
        return True
