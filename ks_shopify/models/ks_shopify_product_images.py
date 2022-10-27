# -*- coding: utf-8 -*-

import base64

from odoo import models, fields, api
from odoo.http import request


class KsShopifyProductImage(models.Model):
    _name = 'ks.shopify.product.images'
    _description = 'Shopify Gallery Product Images'
    _order = 'sequence, id'

    ks_name = fields.Char("Name")
    ks_shopify_image_id = fields.Char('Shopify Image ID')
    ks_image_name = fields.Char("Images", readonly=True)
    ks_image_id = fields.Many2one('ks.common.product.images', "Odoo Image", ondelete="cascade")
    ks_shopify_variant_id = fields.Many2one('ks.shopify.product.variant', string='Product template', ondelete='cascade')
    ks_shopify_template_id = fields.Many2one('ks.shopify.product.template', string='Product variant',
                                             ondelete='cascade')
    ks_image = fields.Image('Image')
    ks_url = fields.Char(string="Image URL", help="External URL of image")
    sequence = fields.Integer(help="Sequence of images.", index=True, default=10)

    @api.model
    def create(self, values):
        record = super(KsShopifyProductImage, self).create(values)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        rec_id = str(record.id)
        if not record.ks_shopify_image_id:
            image_name = record.ks_name.replace(' ', '_') if record.ks_name else ''
            record.ks_image_name = "{image_name}_{image_id}.png".format(image_name=image_name,
                                                                        image_id=rec_id)
            image_url = base_url + '/ks_shopify_image/%s/%s/%s/%s' % (
                self.env.cr.dbname,
                str(self.env.user.id),
                rec_id,
                record.ks_image_name)
            record.write({'ks_url': image_url})

        return record

    def ks_odoo_prepare_image_data(self, image, template_id=False, variant_id=False):
        image_exist = self.search([('ks_image_id', '=', image.id),
                                   ('ks_shopify_template_id', '=', template_id)])
        if image_exist:
            image_exist.write({
                'ks_image': image.ks_image,
                'ks_name': image.ks_name
            })
        else:
            values = {
                "ks_image": image.ks_image,
                'ks_name': image.ks_name,
                'ks_image_id': image.id,
                'ks_shopify_template_id': template_id,
                'ks_shopify_variant_id': variant_id,
            }
            image_exist = self.create(values)
        return image_exist

    def ks_prepare_images_for_shopify(self, layer_product=False):
        if len(self) <= 1:
            values = {}
            values = {
                "src": self.ks_url,
                "position": 1 if self.ks_image_id.ks_profile_image else '',
            }
            if self.ks_shopify_variant_id:
                values.update({"variant_ids": [self.ks_shopify_variant_id.ks_shopify_variant_id]})
            if self.ks_shopify_image_id:
                values.update({
                    "id": int(self.ks_shopify_image_id)
                })
            return values
        else:
            images = []
            if layer_product:
                values = {
                    "src": layer_product.profile_image.ks_url,
                }
                if layer_product.profile_image.ks_shopify_image_id:
                    values.update({
                        "id": int(layer_product.profile_image.ks_shopify_image_id),
                        "product_id": layer_product.ks_shopify_product_id,
                    })
                images.append(values)
                self = self.filtered(lambda x: x.id != layer_product.profile_image.id)
            for rec in self:
                values = {
                    "src": rec.ks_url,
                }
                if rec.ks_shopify_image_id:
                    values.update({
                        "id": int(rec.ks_shopify_image_id),
                        "product_id": rec.ks_shopify_template_id.ks_shopify_product_id if rec.ks_shopify_template_id else rec.ks_shopify_variant_id.ks_shopify_product_tmpl_id.ks_shopify_product_id,
                    })
                images.append(values)
            return images

    def ks_shopify_update_images(self, instance, images):
        try:
            for rec in images:
                image_data = self.env['ks.api.handler'].ks_post_data(instance, 'images', {'image': rec},
                                                                     )
                if image_data:
                    image_data = image_data.get(
                        'image')
            # return image_data
        except ConnectionError:
            raise Exception("Couldn't Connect the Instance at time of Customer Syncing !! Please check the network "
                            "connectivity or the configuration parameters are not correctly set")
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed="update",
                                                                   status="failed",
                                                                   type="product",
                                                                   instance=instance,
                                                                   operation_flow="shopify_to_odoo",
                                                                   shopify_id=0,
                                                                   layer_model="ks.shopify.product.template",
                                                                   message=str(e))

    def ks_shopify_update_images_for_odoo(self, images, image, product=False, variant=False):
        for index, image_data in enumerate(images):
            image_src = image_data.get('src')
            ks_image = self.env['ks.common.product.images'].get_image_from_url(image_src)
            image_record = self.search([('ks_shopify_image_id', '=', image_data.get('id')),
                                        ('ks_shopify_template_id', '=', product)], limit=1)
            if not image_record:
                image_record = self.search([('ks_url', '=', image_src)], limit=1)

            if image_record:
                image_record.write({
                    "ks_shopify_image_id": image_data.get('id'),
                    "ks_image": ks_image if not image_data.get('variant_ids') else image_record.ks_image,
                    "ks_url": image_data.get('src'),
                    "ks_name": image_data.get('name')
                })
            else:
                if not image_data.get('variant_ids'):
                    product_template = self.env["ks.shopify.product.template"].browse(product)
                    main_image = self.env['ks.common.product.images'].create({
                        "ks_name": image_data.get('name'),
                        "ks_template_id": product_template.ks_shopify_product_template.id,
                        "ks_image": ks_image,
                        "ks_url": image_data.get('src'),
                    })
                self.create({
                    "ks_shopify_image_id": image_data.get('id'),
                    "ks_image": ks_image,
                    "ks_image_id": main_image.id if not image_data.get('variant_ids') else False,
                    "ks_url": image_data.get('src'),
                    "ks_shopify_variant_id": variant,
                    "ks_shopify_template_id": product,
                    "ks_name": image_data.get('name')
                })
            if image.get('id') == image_data.get('id'):
                product_template = self.env["ks.shopify.product.template"].browse(product)
                odoo_product = product_template.ks_shopify_product_template
                if ks_image and odoo_product.image_1920 != ks_image:
                    odoo_product.with_context(woo_sync=True).write({'image_1920': ks_image})

    def ks_manage_shopify_variant_images_for_odoo(self, product_json, instance, product):
        """
        :param variations: list of Shopify variant ids
        :param product: ks.shopify.product.template()
        :return:
        """
        variation = product_json.get('variants')
        if variation:
            for id in variation:
                product_json_data = self.env['ks.shopify.product.template'].ks_shopify_get_product(id.get('product_id'), instance)
                if product_json_data:
                    images = product_json_data[0].get("images")
                    variant = product.ks_shopify_variant_ids.filtered(
                        lambda x: (x.ks_shopify_instance.id == instance.id) and (x.ks_shopify_product_tmpl_id.id == product.id)
                                  and (x.ks_shopify_variant_id == str(id.get('id'))))
                    var_image_data = [i for i in images if i.get('variant_ids') == [id.get('id')]]
                    image_data = var_image_data[0] if len(var_image_data) else False
                    if image_data:
                        image_src = image_data.get('src')
                        ks_var_images = self.search([('ks_shopify_variant_id', '=', variant.id), ('ks_shopify_variant_id.ks_shopify_instance', '=', instance.id)])
                        for image in ks_var_images:
                            image.ks_shopify_variant_id = False
                        image = self.env['ks.common.product.images'].get_image_from_url(image_src)
                        image_record = self.search([('ks_shopify_image_id', '=', image_data.get('id')),
                                                        ('ks_shopify_template_id', '=', product.id),
                                                        ('ks_shopify_variant_id', '=', variant.id)], limit=1)
                        if not image_record:
                            image_record = self.search([('ks_url', '=', image_src)], limit=1)

                        if image_record:
                            image_record.write({
                                "ks_shopify_image_id": id.get('image_id'),
                                "ks_image": image,
                                "ks_url": image_src,
                                "ks_shopify_variant_id": variant,
                                "ks_shopify_template_id": product,
                                "ks_name": image_data.get('name')
                            })
                            variant.ks_shopify_product_variant.with_context(woo_sync=True).write(
                                {"image_1920": image_record.ks_image,
                                 })