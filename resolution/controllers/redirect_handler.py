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

from urllib import urlencode
from urlparse import urlparse, parse_qs

from chub import API
from koi import base, exceptions
from koi.configure import ssl_server_options
from tornado import httpclient, httputil
from tornado.gen import coroutine, Return
from tornado.options import options, define
from tornado.web import RedirectHandler

from hub_key_handler import _parse_hub_key, resolve_link_id_type, _redirect_url

define('redirect_to_website', default='http://openpermissions.org/',
       help='The website to which the resolution service redirects for unknown requests')

@coroutine
def _get_provider(provider_id):
    """Get a provider from the accounts service

    :param provider_id: str
    :returns: organisation resource
    :raises: koi.exceptions.HTTPError
    """
    client = API(options.url_accounts, ssl_options=ssl_server_options())

    try:
        org = yield client.accounts.organisations[provider_id].get()
        raise Return(org)
    except httpclient.HTTPError as exc:
        if exc.code == 404:
            msg = 'Unknown provider ID'
        else:
            msg = 'Unexpected error'

        raise exceptions.HTTPError(exc.code, msg, source='accounts')

@coroutine
def _get_provider_by_name(provider):
    """Get a provider from the accounts service

    :param provider: str
    :returns: organisation resource
    :raises: koi.exceptions.HTTPError
    """
    client = API(options.url_accounts, ssl_options=ssl_server_options())

    try:
        res = yield client.accounts.organisations.get(name=provider)
        raise Return(res['data'][0])
    except httpclient.HTTPError as exc:
        if exc.code == 404:
            msg = 'Unknown provider'
        else:
            msg = 'Unexpected error'

        raise exceptions.HTTPError(exc.code, msg, source='accounts')

def _getCleanQuerystring(cls):
    """
    strip our internal parameters from the querystring and return all others
    """
    cleanQs = {}

    qs = cls.request.query
    parts = parse_qs(qs)

    for x in parts:
        if x not in ['hubpid', 'hubidt', 'hubaid']:
            cleanQs[x] = parts[x]

    return urlencode(cleanQs, True)

def _getHostSubDomain(cls):
    """
    returns the subdomain portion of the request hostname

    eg something.copyrighthub.org would return "something"
    """
    subDomain = ""

    # we need to check the original header from the load balancer
    elbHostname = cls.request.headers.get('X-Forwarded-For')
    if not elbHostname:
        host = cls.request.host.lower()
    else:
        host = elbHostname.lower()

    host, port = httputil.split_host_and_port(host)

    logging.debug("host " + host)

    # get the subdomain part
    hostparts = host.split('.')

    logging.debug("hostparts " + ', '.join(hostparts))
    logging.debug("len " + str(len(hostparts)))

    if len(hostparts) == 3:
        if hostparts[1] == 'copyrighthub' and hostparts[2] == 'org':
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

        # get the subdomain from the request
        hostProvider = _getHostSubDomain(self)
        cleanQuery = _getCleanQuerystring(self)

        logging.debug("sub " + hostProvider)
        logging.debug("qs " + cleanQuery)

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

        # look for just providerId specified
        if providerId and not assetIdType and not assetId:
            logging.debug("D : show provider landing page")
            # get provider info
            provider = yield _get_provider_by_name(providerId)

            logging.debug(provider)

            # show the provider's special branded landing page
            self.render('provider_template.html', data=provider)
            raise Return()

        # look for all three parameters specified
        if providerId and assetIdType and assetId:
            logging.debug("B : all specified")
            # look up reference links stuff and redirect

            # build dummy s0 hub_key so we can re-use existing code to de-code
            dummy_hub_key = "http://copyrighthub.org/s0/hub1/creation/%s/%s/%s" % (providerId, assetIdType, assetId)

            logging.debug("dummy " + dummy_hub_key)

            parsed_key = yield _parse_hub_key(dummy_hub_key)

            logging.debug("parsed " + str(parsed_key))
            
            provider = yield _get_provider(providerId)
            provider = provider['data']

            logging.debug("provider " + str(provider))

            reference_links = provider.get('reference_links')

            logging.debug("reference links " + str(reference_links))

            link_for_id_type = yield resolve_link_id_type(reference_links, parsed_key)

            logging.debug("link_for_id_type " + link_for_id_type)

            if link_for_id_type:
                redirect = _redirect_url(link_for_id_type, parsed_key)
                logging.debug("redirected to " + redirect)
                self.redirect(redirect)
            else:
                self.render('asset_template.html', hub_key=parsed_key)
        else:
            # this should never happen so return 404 if it does
            self.set_status(404)
            self.finish()
            raise Return()