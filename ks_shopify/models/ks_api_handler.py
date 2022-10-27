from odoo import api, fields, models
import requests
from odoo.exceptions import ValidationError
import json


class KsShopifyApiHandler(models.Model):
    _name = "ks.api.handler"
    _description = "Generic API data handlings"

    """
    
        * Each function will have instance as params
        * In case of domains there end url required
        * In case of specific operation take that parameter and make an end url inside this func. and hit the api
        * return an exception if occured, else return data
        * In case of create take data (shopify compatible) as parameter + instance
        * In case of update take data (shopify compatible) as parameter + instance + ID
        
        Total 5 function can be created here :- 
        
            ^ To generate generic link based on requirement
            ^ Get Specific data
            ^ Get All data
            ^ POST DATA
            ^ PUT DATA
            
    """

    def _ks_generate_generic_url(self, instance, domain, o_type, id=None, additional_id=None, model=None):
        """
        :param instance: Shopify instance ks.shopify.connector.instance()
        :param domain: like products/orders/customers etc type:string
        :param type: o_type of operation ['get_all', 'get', 'put', 'post']
        :param id:  id if required
        :return: generic url
        """
        url = instance.ks_shopify_url + '/admin/api/2021-07/' + domain
        if o_type == 'get_all':
            url = url + '.json' + '?limit=250'
        elif o_type in ['get'] and type(id) == str:
            ids = len(id.split(",")) > 1
            if ids:
                url = url + '.json' + "?ids=" + id
            else:
                url = url + '/%s' % str(id) + '.json'
            return url
        elif o_type in ['get', 'put', 'del'] and id:
            if domain == 'addresses':
                url = instance.ks_shopify_url + '/admin/api/2021-07/customers/%s/addresses/%s' % (
                    str(id), str(additional_id)) + '.json'
            elif domain == 'variants':
                url = instance.ks_shopify_url + '/admin/api/2021-07/products/%s/variants' % (
                    str(id)) + '.json'
            elif domain == 'transactions':
                url = instance.ks_shopify_url + '/admin/api/2021-07/orders/%s/transactions' % (
                    str(id)) + '.json'
            elif domain == 'discount_codes':
                url = instance.ks_shopify_url + '/admin/api/2021-07/price_rules/%s/discount_codes' % (
                    str(id)) + '.json'
            elif domain == 'images':
                url = instance.ks_shopify_url + '/admin/api/2021-07/products/%s/images/%s' % (
                    str(id), str(additional_id)) + '.json'
            elif domain == 'collects':
                url = url + '.json'
            elif domain == 'collections':
                url = instance.ks_shopify_url + '/admin/api/2021-07/collections/%s/products' % (
                        str(id)) + '.json'
            elif domain == 'metafields':
                if model == 'products':
                    url = instance.ks_shopify_url + '/admin/api/2021-07/products/%s/metafields' % (
                        str(id)) + '.json'
                if model == 'variants':
                    url = instance.ks_shopify_url + '/admin/api/2021-07/products/%s/variants/%s/metafields' % (
                        str(additional_id), str(id)) + '.json'
                if model == 'customers':
                    url = instance.ks_shopify_url + '/admin/api/2021-07/customers/%s/metafields' % (
                        str(id)) + '.json'
                if model == 'orders':
                    url = instance.ks_shopify_url + '/admin/api/2021-07/orders/%s/metafields' % (
                        str(id)) + '.json'
                if model == 'collections':
                    url = instance.ks_shopify_url + '/admin/api/2021-07/collections/%s/metafields' % (
                        str(id)) + '.json'

            else:
                url = url + '/%s' % str(id) + '.json'
        else:
            if domain == "images" and id:
                url = instance.ks_shopify_url + '/admin/api/2021-07/products/%s/images' % (str(id)) + ".json"
            elif domain == "addresses" and id:
                url = instance.ks_shopify_url + '/admin/api/2021-07/customers/%s/addresses' % (str(id)) + ".json"
            elif domain == 'discount_codes':
                url = instance.ks_shopify_url + '/admin/api/2021-07/price_rules/%s/discount_codes' % (
                    str(id)) + '.json'
            elif domain == 'cancel':
                url = instance.ks_shopify_url + '/admin/api/2021-07/orders/%s/cancel' % (
                    str(id)) + '.json'
            elif domain == 'inventory_levels':
                url = instance.ks_shopify_url + '/admin/api/2021-07/inventory_levels/set.json'

            else:
                url = url + '.json'
        return url

    def ks_get_all_data(self, instance, domain, ids=False, additional_id=False, date_before=False, date_after=False, model=False):
        """
        :param instance: Shopify instance ks.shopify.connector.instance()
        :param domain: like products/orders/customers etc type:string
        :return: list of json data

        """
        try:
            if not ids:
                ks_generic_url = self._ks_generate_generic_url(instance, domain, "get_all")
            elif domain in ['discount_codes', 'variants', 'transactions']:
                ks_generic_url = self._ks_generate_generic_url(instance, domain, "get", ids)
            elif domain == 'images':
                ks_generic_url = self._ks_generate_generic_url(instance, domain, "get", ids,
                                                               additional_id=additional_id)
            elif domain == 'metafields':
                ks_generic_url = self._ks_generate_generic_url(instance, domain, "get", ids,
                                                               additional_id=additional_id, model=model)
            else:
                ks_generic_url = self._ks_generate_generic_url(instance, domain, "get", ids)
            all_json_data = []
            if ks_generic_url:
                domain = 'products' if 'collections' in ks_generic_url and 'products' in ks_generic_url else domain
                ks_response = requests.get(ks_generic_url)
                if ks_response.status_code in [200, 201]:
                    ks_json_data = ks_response.json()
                    if ks_json_data.get(domain):
                        all_json_data.extend(ks_json_data.get(domain))
                    elif ks_json_data.get(domain[:-1]):
                        all_json_data.append(ks_json_data.get(domain[:-1]))
                    while ks_response.links.get('next', False):
                        ks_api_endpoint = ks_response.links.get('next').get('url').split(instance.ks_store_url)[1]
                        ks_api_endpoint = instance.ks_shopify_url + ks_api_endpoint
                        ks_response = requests.get(ks_api_endpoint)
                        if ks_response.status_code in [200, 201]:
                            ks_json_data = ks_response.json()
                            all_json_data.extend(ks_json_data.get(domain))
                else:
                    self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='fetch',
                                                                           status='failed',
                                                                           operation_flow='shopify_to_wl',
                                                                           type='api_data_handling',
                                                                           instance=instance,
                                                                           shopify_id='',
                                                                           message="Fetch of all the %s Failed due to %s" % (
                                                                               domain, ks_response.text))
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='fetch',
                                                                   status='failed',
                                                                   operation_flow='shopify_to_wl',
                                                                   type='api_data_handling',
                                                                   instance=instance,
                                                                   shopify_id='',
                                                                   message="Fetch of all the %s Failed due to %s" % (
                                                                       domain, str(e)))
        else:
            if all_json_data:
                self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='fetch',
                                                                       status='success',
                                                                       operation_flow='shopify_to_wl',
                                                                       type='api_data_handling',
                                                                       instance=instance,
                                                                       shopify_id='',
                                                                       message="Fetch of all the %s Successful" % domain, )
            return all_json_data

    def ks_get_specific_data(self, instance, domain, id):
        """
        :param instance: Shopify instance ks.shopify.connector.instance()
        :param domain: like products/orders/customers etc type:string
        :param id: specific domain if type:int
        :return: json data
        """
        try:
            json_response = None
            ks_generic_url = self._ks_generate_generic_url(instance, domain, "get", id)
            if ks_generic_url:
                ks_response = requests.get(ks_generic_url)
                if ks_response.status_code in [200, 201]:
                    json_response = ks_response.json()
                    self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='fetch',
                                                                           status='success',
                                                                           operation_flow='shopify_to_wl',
                                                                           type='api_data_handling',
                                                                           instance=instance,
                                                                           shopify_id=str(id),
                                                                           message="Fetch of Specific %s Successful" % domain, )
                else:
                    self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='fetch',
                                                                           status='failed',
                                                                           operation_flow='shopify_to_wl',
                                                                           type='api_data_handling',
                                                                           instance=instance,
                                                                           shopify_id=str(id),
                                                                           message="Fetch of specific %s Failed due to %s" % (
                                                                               domain, ks_response.text))
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='fetch',
                                                                   status='failed',
                                                                   operation_flow='shopify_to_wl',
                                                                   type='api_data_handling',
                                                                   instance=instance,
                                                                   shopify_id=' ',
                                                                   message="Fetch of specific %s Failed due to %s" % (
                                                                       domain, str(e)))
        else:
            return json_response

    def ks_post_data(self, instance, domain, data, additional_data=False):
        """
        :param instance: Shopify instance ks.shopify.connector.instance()
        :param domain: like products/orders/customers etc type:string
        :param data: shopify compatible data
        :return: json response
        """
        try:
            json_response = None
            ks_generic_url = self._ks_generate_generic_url(instance, domain, "post", id=additional_data)
            if ks_generic_url:
                ks_response = requests.post(ks_generic_url, json=data)
                if ks_response.status_code in [200, 201]:
                    json_response = ks_response.json()
                    self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='create',
                                                                           status='success',
                                                                           operation_flow='wl_to_shopify',
                                                                           type='api_data_handling',
                                                                           instance=instance,
                                                                           shopify_id='',
                                                                           message="Create of Specific %s Successful" % domain)
                else:
                    self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='create',
                                                                           status='failed',
                                                                           operation_flow='wl_to_shopify',
                                                                           type='api_data_handling',
                                                                           instance=instance,
                                                                           shopify_id='',
                                                                           message="Create of Specific %s failed because %s" % (
                                                                               domain, ks_response.text))
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='create',
                                                                   status='failed',
                                                                   operation_flow='wl_to_shopify',
                                                                   type='api_data_handling',
                                                                   instance=instance,
                                                                   shopify_id='',
                                                                   message="Create of Specific %s failed because %s" % (
                                                                       domain, str(e)))
        else:
            return json_response

    def ks_put_data(self, instance, domain, data, id, additional_id=False):
        """
        :param instance: Shopify instance ks.shopify.connector.instance()
        :param domain: like products/orders/customers etc type:string
        :param data: shopify compatible data
        :param id: domain id on which we have to update data type:int
        :return: json response
        """
        try:
            json_response = None
            ks_generic_url = self._ks_generate_generic_url(instance, domain, "put", id, additional_id)
            if ks_generic_url:
                ks_response = requests.put(ks_generic_url, json=data)
                if ks_response.status_code in [200, 201]:
                    json_response = ks_response.json()
                    self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='update',
                                                                           status='success',
                                                                           operation_flow='wl_to_shopify',
                                                                           type='api_data_handling',
                                                                           instance=instance,
                                                                           shopify_id='',
                                                                           message="Update of Specific %s Successful" % domain)
                else:
                    self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='update',
                                                                           status='failed',
                                                                           operation_flow='wl_to_shopify',
                                                                           type='api_data_handling',
                                                                           instance=instance,
                                                                           shopify_id='',
                                                                           message="Update of Specific %s failed because %s" % (
                                                                               domain, ks_response.text))
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='update',
                                                                   status='failed',
                                                                   operation_flow='wl_to_shopify',
                                                                   type='api_data_handling',
                                                                   instance=instance,
                                                                   shopify_id='',
                                                                   message="Update of Specific %s failed because %s" % (
                                                                       domain, str(e)))
        else:
            return json_response

    def ks_del_data(self, instance, domain, id, additional_id=False):
        """
        :param instance: Shopify instance ks.shopify.connector.instance()
        :param domain: like products/orders/customers etc type:string
        :param data: shopify compatible data
        :param id: domain id on which we have to update data type:int
        :return: json response
        """
        try:
            json_response = None
            ks_generic_url = self._ks_generate_generic_url(instance, domain, "del", id, additional_id)
            if ks_generic_url:
                ks_response = requests.delete(ks_generic_url)
                if ks_response.status_code in [200, 201]:
                    json_response = ks_response.json()
                    self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='delete',
                                                                           status='success',
                                                                           operation_flow='wl_to_shopify',
                                                                           type='api_data_handling',
                                                                           instance=instance,
                                                                           shopify_id='',
                                                                           message="Delete of Specific %s Successful" % domain)
                else:
                    self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='delete',
                                                                           status='failed',
                                                                           operation_flow='wl_to_shopify',
                                                                           type='api_data_handling',
                                                                           instance=instance,
                                                                           shopify_id='',
                                                                           message="Delete of Specific %s failed because %s" % (
                                                                               domain, ks_response.text))
        except Exception as e:
            self.env['ks.shopify.logger'].ks_create_api_log_params(operation_performed='delete',
                                                                   status='failed',
                                                                   operation_flow='wl_to_shopify',
                                                                   type='api_data_handling',
                                                                   instance=instance,
                                                                   shopify_id='',
                                                                   message="Delete of Specific %s failed because %s" % (
                                                                       domain, str(e)))
        else:
            return json_response
