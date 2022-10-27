# -*- coding: utf-8 -*-

import base64
import logging

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import ensure_db, Home

_logger = logging.getLogger(__name__)


class KsShopifyCommerceImageUrl(Home):
    @http.route('/ks_shopify_image/<string:db_name>/<string:uid>/<string:image_id>/<string:image_name>',
                type='http', auth='public', csrf=False, methods=['GET', 'POST'])
    def get_image_from_url(self, db_name='', uid='', image_id='', **kwargs):
        if db_name and uid and image_id:
            db_name, uid, image_id = db_name.strip(), uid.strip(), image_id.strip()
            request.session.db = db_name
            request.session.uid = int(uid)
            try:
                status, response_headers, content = request.env['ir.http'].sudo().binary_content(
                    model='ks.shopify.product.images', id=image_id,
                    field='ks_image')
                image_content_base64 = base64.b64decode(content) if content else ''
                _logger.info("Image found with status %s", str(status))
                response_headers.append(('Content-Length', len(image_content_base64)))
                return request.make_response(image_content_base64, response_headers)
            except Exception:
                return request.not_found()
        return request.not_found()