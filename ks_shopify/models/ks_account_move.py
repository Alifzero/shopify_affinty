# -*- coding: utf-8 -*-

from odoo import fields, models, api
import requests
import logging

_logger = logging.getLogger(__name__)


class KsAccountInvoiceInherit(models.Model):
    _inherit = 'account.move'

    ks_shopify_order_id = fields.Many2one('sale.order', string='Shopify Order',
                                          help="""Shopify Order: The Shopify Order""",
                                          readonly=1, ondelete='cascade')
    ks_shopify_order_uni_id = fields.Char(string="Shopify Unique Id", related='ks_shopify_order_id.ks_shopify_order_id')
    ks_refunded = fields.Boolean(string="Refunded")

    def ks_prepare_data_for_refund(self, instance):
        """
        :instance: shopify instance
        :return: shopify json data for refund api calling
        """
        try:
            refund_data = {}
            refund_line_items = []
            for order_line in self.ks_shopify_order_id.order_line:
                refund_line_items.append({
                            "line_item_id": order_line.ks_shopify_order_line_id,
                            "quantity": int(order_line.product_uom_qty),
                            "restock_type": "return",
                            "location_id": instance.ks_primary_locations
                            })
            reason_index = self.ref.find(',')
            reason = self.ref[reason_index + 1:] if reason_index != -1 else " "
            data = {
                "currency": instance.ks_shopify_currency.name or '',
                "notify": "true",
                "note": reason,
                "refund_line_items": refund_line_items,

                "transactions": [
                    {
                        "parent_id": self.ks_shopify_order_id.ks_shopify_transaction_id,
                        "amount": float(self.amount_total),
                        "kind": "refund",
                        "gateway": self.ks_shopify_order_id.ks_shopify_payment_gateway.ks_name or ''
                    }
                ]
            }
            refund_data['refund'] = data
            return refund_data
        except Exception as e:
            raise e

    def ks_call_refund_api(self, instance, order_id, json_data):
        """
        :param instance: shopify connector instance
        :param order_id: shopify order id
        :param json_data: refund shopify api compatible data
        :return: json response
        """
        try:
            refund_json = {}
            generic_url = instance.ks_shopify_url + '/admin/api/2021-07/' + "orders/%s/refunds.json" % order_id
            if instance and json_data:
                refund_json_response = requests.post(generic_url, json=json_data)
                if refund_json_response.status_code in [200, 201]:
                    refund_json = refund_json_response.json()['refund']
                    self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='refund',
                                                                           status='success',
                                                                           operation_flow='wl_to_shopify',
                                                                           type='order',
                                                                           instance=instance,
                                                                           shopify_id=refund_json.get('id'),
                                                                           message="Refund of Orders Successful")
                else:
                    self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='refund',
                                                                           status='failed',
                                                                           operation_flow='wl_to_shopify',
                                                                           type='order',
                                                                           instance=instance,
                                                                           shopify_id='',
                                                                           message="Refund of Orders Failed because %s" % str(
                                                                               refund_json_response.text))
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='refund',
                                                                   status='failed',
                                                                   operation_flow='wl_to_shopify',
                                                                   type='order',
                                                                   instance=instance,
                                                                   shopify_id='',
                                                                   message="Refund of Orders Failed because %s" % str(
                                                                       e))
        else:
            return refund_json

    def refund_in_shopify(self):
        try:
            ks_shopify_instance = self.ks_shopify_order_id.ks_shopify_instance
            if ks_shopify_instance:
                prepared_data = self.ks_prepare_data_for_refund(ks_shopify_instance)
                if prepared_data and ks_shopify_instance.ks_instance_state == 'active':
                    ks_shopify_order_id = self.ks_shopify_order_id.ks_shopify_order_id
                    refund_response = self.ks_call_refund_api(ks_shopify_instance, ks_shopify_order_id, prepared_data)
                    if refund_response:
                        self.write({"ks_refunded": True})
                        self.message_post(body=('''Refund for the invoice: %s with order: %s, 
                        having shopify order id: %s successful where amount refunded: %s''' % (self.display_name,
                                                                                               self.ks_shopify_order_id.display_name,
                                                                                               self.ks_shopify_order_id.ks_shopify_order_id,
                                                                                               str(self.amount_total))))
                        _logger.info("Refund for the order with shopify id: %s successful" % ks_shopify_order_id)
                    else:
                        _logger.warning("Refund for order with shopify id: %s failed" % ks_shopify_order_id)

        except Exception as e:
            _logger.error("Refund failed due to : %s" % str(e))


class KsAccountMoveLine(models.Model):
    _inherit = "account.move.line"

    ks_discount_amount_value = fields.Float(string='Discount Amount', digits=(16, 4))

    @api.model_create_multi
    def create(self, vals_list):
        # OVERRIDE
        ACCOUNTING_FIELDS = ('debit', 'credit', 'amount_currency')
        BUSINESS_FIELDS = ('price_unit', 'quantity', 'discount', 'tax_ids')

        for vals in vals_list:
            move = self.env['account.move'].browse(vals['move_id'])
            vals.setdefault('company_currency_id',
                            move.company_id.currency_id.id)  # important to bypass the ORM limitation where monetary fields are not rounded; more info in the commit message

            # Ensure balance == amount_currency in case of missing currency or same currency as the one from the
            # company.
            currency_id = vals.get('currency_id') or move.company_id.currency_id.id
            if currency_id == move.company_id.currency_id.id:
                balance = vals.get('debit', 0.0) - vals.get('credit', 0.0)
                vals.update({
                    'currency_id': currency_id,
                    'amount_currency': balance,
                })
            else:
                vals['amount_currency'] = vals.get('amount_currency', 0.0)

            if move.is_invoice(include_receipts=True):
                currency = move.currency_id
                partner = self.env['res.partner'].browse(vals.get('partner_id'))
                taxes = self.new({'tax_ids': vals.get('tax_ids', [])}).tax_ids
                tax_ids = set(taxes.ids)
                taxes = self.env['account.tax'].browse(tax_ids)

                # Ensure consistency between accounting & business fields.
                # As we can't express such synchronization as computed fields without cycling, we need to do it both
                # in onchange and in create/write. So, if something changed in accounting [resp. business] fields,
                # business [resp. accounting] fields are recomputed.
                if any(vals.get(field) for field in ACCOUNTING_FIELDS):
                    price_subtotal = self._get_price_total_and_subtotal_model(
                        vals.get('price_unit', 0.0),
                        vals.get('quantity', 0.0),
                        vals.get('discount', 0.0),
                        currency,
                        self.env['product.product'].browse(vals.get('product_id')),
                        partner,
                        taxes,
                        move.move_type,
                    ).get('price_subtotal', 0.0)
                    vals.update(self._get_fields_onchange_balance_model(
                        vals.get('quantity', 0.0),
                        vals.get('discount', 0.0),
                        vals['amount_currency'],
                        move.move_type,
                        currency,
                        taxes,
                        price_subtotal
                    ))
                    vals.update(self._get_price_total_and_subtotal_model(
                        vals.get('price_unit', 0.0),
                        vals.get('quantity', 0.0),
                        vals.get('discount', 0.0),
                        currency,
                        self.env['product.product'].browse(vals.get('product_id')),
                        partner,
                        taxes,
                        move.move_type,
                    ))
                elif any(vals.get(field) for field in BUSINESS_FIELDS):
                    vals.update(self._get_price_total_and_subtotal_model(
                        vals.get('price_unit', 0.0),
                        vals.get('quantity', 0.0),
                        vals.get('discount', 0.0),
                        currency,
                        self.env['product.product'].browse(vals.get('product_id')),
                        partner,
                        taxes,
                        move.move_type,
                    ))
                    vals.update(self._get_fields_onchange_subtotal_model(
                        vals['price_subtotal'],
                        move.move_type,
                        currency,
                        move.company_id,
                        move.date,
                    ))
        for rec in vals_list:
            if rec.get('tax_repartition_line_id'):
                ks_data = True if rec.get('credit') else False
                if self.env['account.move'].search([('id', '=', rec.get('move_id'))]).line_ids and self.env['account.move'].search([('id', '=', rec.get('move_id'))]).line_ids[0].sale_line_ids and self.env['account.move'].search([('id', '=', rec.get('move_id'))]).line_ids[0].sale_line_ids[0].order_id.ks_shopify_instance:
                    if ks_data:
                        if self.env['account.move'].search(
                                [('id', '=', rec.get('move_id'))]).line_ids[0].sale_line_ids[0].order_id.ks_shopify_instance.ks_invoice_tax_account:
                            rec.update({
                                'account_id': self.env['account.move'].search(
                                    [('id', '=', rec.get('move_id'))]).line_ids[0].sale_line_ids[0].order_id.ks_shopify_instance.ks_invoice_tax_account.id
                            })
                    else:
                        if self.env['account.move'].search(
                                [('id', '=', rec.get('move_id'))]).line_ids[0].sale_line_ids[0].order_id.ks_shopify_instance.ks_credit_tax_account:
                            rec.update({
                                'account_id': self.env['account.move'].search(
                                    [('id', '=', rec.get('move_id'))]).line_ids[0].sale_line_ids[
                                    0].order_id.ks_shopify_instance.ks_credit_tax_account.id
                            })
                elif self.env['account.move'].search([('id', '=', rec.get('move_id'))]).ks_shopify_order_id and self.env['account.move'].search([('id', '=', rec.get('move_id'))]).ks_shopify_order_id.ks_shopify_instance:
                    if ks_data:
                        if self.env['account.move'].search([('id', '=', rec.get('move_id'))]).ks_shopify_order_id.ks_shopify_instance.ks_invoice_tax_account:
                            rec.update({
                            'account_id': self.env['account.move'].search([('id', '=', rec.get(
                                'move_id'))]).ks_shopify_order_id.ks_shopify_instance.ks_invoice_tax_account.id})
                    else:
                        if self.env['account.move'].search([('id', '=',
                                                             rec.get('move_id'))]).ks_shopify_order_id.ks_shopify_instance.ks_credit_tax_account:
                            rec.update({
                                'account_id': self.env['account.move'].search([('id', '=', rec.get(
                                    'move_id'))]).ks_shopify_order_id.ks_shopify_instance.ks_credit_tax_account.id})

        lines = super(KsAccountMoveLine, self).create(vals_list)

        moves = lines.mapped('move_id')
        if self._context.get('check_move_validity', True):
            moves._check_balanced()
        moves._check_fiscalyear_lock_date()
        lines._check_tax_lock_date()
        moves._synchronize_business_models({'line_ids'})
        return lines