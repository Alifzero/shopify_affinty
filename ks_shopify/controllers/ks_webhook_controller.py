# -*- coding: utf-8 -*-

import json
import base64
import logging

from odoo import http, SUPERUSER_ID
from odoo.http import Root, HttpRequest
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class KsShopifyWebhookHandler(http.Controller):
    @http.route(['/shopify_hook/<string:db>/<string:uid>/<int:shopify_instance>/collections/create'], auth='none',
                csrf=False, methods=['POST'])
    def create_collections_webhook(self, db, shopify_instance, uid, **post):
        try:
            encoded_db = db.strip()
            decoded_db = base64.urlsafe_b64decode(encoded_db)
            request.session.db = str(decoded_db, "utf-8")
            _logger.info("Create Collection Webhook Triggered")
            if uid:
                request.session.uid = int(uid)
                request.env.user = request.env['res.users'].browse(int(uid))
                request.env.uid = int(uid)
            data = request.httprequest.data
            if data:
                self._ks_check_user()
                if shopify_instance:
                    shopify_instance_id = request.env['ks.shopify.connector.instance'].sudo().search(
                        [('id', '=', shopify_instance)],
                        limit=1)
                    if shopify_instance_id and data:
                        request.env.company = shopify_instance_id.ks_company_id
                        request.env.companies = shopify_instance_id.ks_company_id
                        request.env['ks.shopify.queue.jobs'].ks_create_collections_record_in_queue(data=[data],
                                                                                                   instance=shopify_instance_id,
                                                                                                   option=True)
                        _logger.info('Collections enqueue start For Shopify Instance [%s -(%s)]'
                                     , shopify_instance_id.ks_instance_name, shopify_instance_id.id)
                        return '200'
            return '200'
        except Exception as e:
            _logger.info("Create of Collections failed with exception through webhook failed " + str(e))
            return request.not_found()

    @http.route(['/shopify_hook/<string:db>/<string:uid>/<int:shopify_instance>/collections/update'],
                 auth='none', csrf=False, methods=['POST'])
    def update_collections_webhook(self, db, shopify_instance, uid, **post):
        try:
            encoded_db = db.strip()
            decoded_db = base64.urlsafe_b64decode(encoded_db)
            request.session.db = str(decoded_db, "utf-8")
            _logger.info("Update Collection Webhook Triggered")
            if uid:
                request.session.uid = int(uid)
                request.env.user = request.env['res.users'].browse(int(uid))
                request.env.uid = int(uid)
            data = request.httprequest.data
            if data:
                self._ks_check_user()
                if shopify_instance:
                    shopify_instance_id = request.env['ks.shopify.connector.instance'].sudo().search(
                        [('id', '=', shopify_instance)],
                        limit=1)
                    if shopify_instance_id and data:
                        request.env.company = shopify_instance_id.ks_company_id
                        request.env.companies = shopify_instance_id.ks_company_id
                        request.env['ks.shopify.queue.jobs'].ks_create_collections_record_in_queue(data=[data],
                                                                                                   instance=shopify_instance_id,
                                                                                                   option=True)
                        _logger.info('Collections enqueue start For Shopify Instance [%s -(%s)]'
                                     , shopify_instance_id.ks_instance_name, shopify_instance_id.id)
                        return '200'
                return '200'
        except Exception as e:
            _logger.info("Update of Collections failed with exception through webhook failed " + str(e))
            return request.not_found()

    @http.route(['/shopify_hook/<string:db>/<string:uid>/<int:shopify_instance>/customers/create',
                 '/shopify_hook/<string:db>/<string:uid>/<int:shopify_instance>/customers/update'],
                auth='none', csrf=False, methods=['POST'])
    def create_update_customers_webhook(self, shopify_instance, db, uid, **post):
        try:
            encoded_db = db.strip()
            decoded_db = base64.urlsafe_b64decode(encoded_db)
            request.session.db = str(decoded_db, "utf-8")
            _logger.info("Create Customers Webhook Triggered")
            if uid:
                request.session.uid = int(uid)
                request.env.user = request.env['res.users'].browse(int(uid))
                request.env.uid = int(uid)
            data = request.httprequest.data
            if data:
                self._ks_check_user()
                if shopify_instance:
                    shopify_instance_id = request.env['ks.shopify.connector.instance'].sudo().search(
                        [('id', '=', shopify_instance)],
                        limit=1)
                    if shopify_instance_id and data:
                        request.env.company = shopify_instance_id.ks_company_id
                        request.env.companies = shopify_instance_id.ks_company_id
                        request.env['ks.shopify.queue.jobs'].ks_create_customer_record_in_queue(data=[data],
                                                                                                instance=shopify_instance_id,
                                                                                                option=True)
                        _logger.info('Customer enqueue start For Shopify Instance [%s -(%s)]'
                                     , shopify_instance_id.ks_instance_name, shopify_instance_id.id)
                        return '200'
                    return '200'
        except Exception as e:
            _logger.info("Create/Update of Customers failed through webhook failed " + str(e))
            return Response("The requested URL was not found on the server.", status=404)

    @http.route(['/shopify_hook/<string:db>/<string:uid>/<int:shopify_instance>/products/create',
                 '/shopify_hook/<string:db>/<string:uid>/<int:shopify_instance>/products/update'], auth='none',
                csrf=False, methods=['POST'])
    def create_update_product_webhook(self, shopify_instance, db, uid, **post):
        try:
            encoded_db = db.strip()
            decoded_db = base64.urlsafe_b64decode(encoded_db)
            request.session.db = str(decoded_db, "utf-8")
            _logger.info("Create Products Webhook Triggered")
            if uid:
                request.session.uid = int(uid)
                request.env.user = request.env['res.users'].browse(int(uid))
                request.env.uid = int(uid)
            data = request.httprequest.data
            if data:
                self._ks_check_user()
                if shopify_instance:
                    shopify_instance_id = request.env['ks.shopify.connector.instance'].sudo().search(
                        [('id', '=', shopify_instance)],
                        limit=1)
                    if shopify_instance_id and data:
                        request.env.company = shopify_instance_id.ks_company_id
                        request.env.companies = shopify_instance_id.ks_company_id
                        request.env['ks.shopify.queue.jobs'].ks_create_product_record_in_queue(data=[data],
                                                                                               instance=shopify_instance_id,
                                                                                               option=True)
                        _logger.info('Product enqueue start For Shopify Instance [%s -(%s)]'
                                     , shopify_instance_id.ks_instance_name, shopify_instance_id.id)
                        return '200'
                    # else:
                    #     _logger.info("Fatal Error with the wcapi()")
                return '200'
        except Exception as e:
            _logger.info("Create/Update of product failed through webhook failed " + str(e))
            return request.not_found()

    @http.route(['/shopify_hook/<string:db>/<string:uid>/<int:shopify_instance>/orders/create',
                 '/shopify_hook/<string:db>/<string:uid>/<int:shopify_instance>/orders/updated'],
                auth='none', csrf=False, methods=['POST'])
    def create_update_order_webhook(self, shopify_instance, db, uid, **post):
        try:
            encoded_db = db.strip()
            decoded_db = base64.urlsafe_b64decode(encoded_db)
            request.session.db = str(decoded_db, "utf-8")
            _logger.info("Create Order Webhook Triggered")
            if uid:
                request.session.uid = int(uid)
                request.env.user = request.env['res.users'].browse(int(uid))
                request.env.uid = int(uid)
            data = request.httprequest.data
            if data:
                self._ks_check_user()
                if shopify_instance:
                    shopify_instance_id = request.env['ks.shopify.connector.instance'].sudo().search(
                        [('id', '=', shopify_instance)],
                        limit=1)
                    if shopify_instance_id and data:
                        request.env.company = shopify_instance_id.ks_company_id
                        request.env.companies = shopify_instance_id.ks_company_id
                        request.env['ks.shopify.queue.jobs'].ks_create_order_record_in_queue(data=[data],
                                                                                             instance=shopify_instance_id,
                                                                                             option=True)
                        _logger.info('Order enqueue start For Shopify Instance [%s -(%s)]'
                                     , shopify_instance_id.ks_instance_name, shopify_instance_id.id)
            return '200'
        except Exception as e:
            _logger.info("Create/Update of order failed through webhook failed " + str(e))
            return request.not_found()

    def _ks_check_user(self):
        if request.env.user.has_group('base.group_public'):
            request.env.user = request.env['res.users'].browse(SUPERUSER_ID)
            request.env.uid = SUPERUSER_ID
        return request.env.user


old_get_request = Root.get_request


def get_request(self, httprequest):
    is_json = httprequest.args.get('jsonp') or httprequest.mimetype in ("application/json", "application/json-rpc")
    httprequest.data = {}
    shopify_hook_path = ks_match_the_url_path(httprequest.path)
    if shopify_hook_path and is_json:
        request = httprequest.get_data().decode(httprequest.charset)
        httprequest.data = json.loads(request)
        return HttpRequest(httprequest)
    return old_get_request(self, httprequest)


Root.get_request = get_request


def ks_match_the_url_path(path):
    if path:
        path_list = path.split('/')
        if path_list[1] == 'shopify_hook' and path_list[5] in ['customers', 'products', 'collections', 'orders'] and\
                path_list[6] in ['create', 'update', 'updated']:
            return True
        else:
            return False
