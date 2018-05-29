# -*- coding: utf-8 -*-
# Copyright 2016 Open Permissions Platform Coalition
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License. You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed under the License is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under the License.

"""Resolve an asset from parameters"""
import logging

import urllib

from chub import API
from koi import base, exceptions
from koi.configure import ssl_server_options
from tornado import httpclient, httputil
from tornado.gen import coroutine, Return
from tornado.options import options, define
from tornado.web import RedirectHandler

from hub_key_handler import redirectToAsset, _get_provider_by_name
from memoize import MemoizeCoroutine

define('redirect_to_website', default='http://openpermissions.org/',
       help='The website to which the resolution service redirects for unknown requests')

@MemoizeCoroutine
@coroutine
def _get_providers_by_type_and_id(source_id_type, source_id):
    """ get the matching providers for a given source_id_type and source_id

    :param source_id_type: str
    :param source_id: str        
    :returns: list of organisations
    :raises: koi.exceptsion.HTTPError
    """
    client = API(options.url_query, ssl_options=ssl_server_options())

    try:
        res = yield client.query.licensors.get(source_id_type=source_id_type, source_id=source_id)
        raise Return(res['data'])
    except httpclient.HTTPError as exc:
        if exc.code == 404:
            msg = 'No matching providers found'
        else:
            msg = 'Unexpected error ' + exc.message

        raise exceptions.HTTPError(exc.code, msg, source='query')


def _getHostSubDomain(cls):
    """
    returns the subdomain portion of the request hostname

    eg something.copyrighthub.org would return "something"
    """
    subDomain = ""

    host = cls.request.headers.get('Host')

    host, port = httputil.split_host_and_port(host)

    # get the subdomain part
    hostparts = host.split('.')

    # match subdomain, but only if not in list of ignore_subdomains
    if len(hostparts) == 3:
        if not hostparts[0] in options.ignored_subdomains   \
                and hostparts[1] == 'copyrighthub'          \
                and hostparts[2] == 'org':
            subDomain = hostparts[0]

    return subDomain

class RedirectHandler(base.BaseHandler):
    def initialize(self, **kwargs):
        try:
            self.version = kwargs['version']
        except KeyError:
            raise KeyError('App version is required')

    @coroutine
    def get(self):
        """
        Resolve an asset from querystring parameters:
            . hubpid = provider id
            . hubidt = asset id type
            . hubaid = asset id
        """
        providerId = self.get_query_argument('hubpid', None)
        assetIdType = self.get_query_argument('hubidt', None)
        assetId = self.get_query_argument('hubaid', None)
        
        global showJson
        showJson = self.get_query_argument('hubjson', None)

        # get the subdomain from the request
        hostProvider = _getHostSubDomain(self)
        
        # if hostname provider is specified then use it, but check it doesn't
        # conflict with any provider passed in the queryString
        if hostProvider:
            if not providerId:
                providerId = hostProvider
            else:
                if hostProvider.lower() != providerId.lower():
                    self.render('error.html', errors=['hostname contradicts querystring provider'])
                    raise Return()

        # if our parameters are all missing redirect to default page 
        if not providerId and not assetIdType and not assetId:
            logging.debug("A : redirect to options.redirect_to_website")
            self.redirect(options.redirect_to_website)
            raise Return()

        # if providerId is missing but other two are there then look for multiple providers for asset
        if not providerId and assetIdType and assetId:
            logging.debug("C : lookup asset")

            # search for providers by assetId and assetIdType
            providers = yield _get_providers_by_type_and_id(assetIdType, assetId)

            if len(providers) == 1:
                yield redirectToAsset(self, providers[0], assetIdType, assetId, showJson)
                raise Return()
            else:
                self.render('multiple_providers_template.html', providers=providers, assetIdType=urllib.quote_plus(assetIdType), assetId=urllib.quote_plus(assetId))
                raise Return()

        # look for just providerId specified
        if providerId and not assetIdType and not assetId:
            logging.debug("D : show provider landing page")
            # get provider info
            provider = yield _get_provider_by_name(providerId)

            # show the provider's special branded landing page
            self.render('provider_template.html', data=provider)
            raise Return()

        # look for all three parameters specified
        if providerId and assetIdType and assetId:
            logging.debug("B : all specified")
            # look up reference links stuff and redirect
            provider = yield _get_provider_by_name(providerId)
            logging.debug ('prov ' + str(provider))
            yield redirectToAsset(self, provider, assetIdType, assetId, showJson)
        else:
            # this should never happen so return error if it does
            self.render('error.html', errors=['unable to find matching asset from provided identifiers'])
            raise Return()

    
