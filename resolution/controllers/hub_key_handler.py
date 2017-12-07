# -*- coding: utf-8 -*-
# Copyright 2016 Open Permissions Platform Coalition
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License. You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed under the License is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under the License.

"""Resolve a Hub Key"""
import urllib

from urllib import urlencode
from urlparse import urlparse, parse_qs, urlunparse

from bass import hubkey
from chub import API
from koi import base, exceptions
from koi.configure import ssl_server_options
from tornado import httpclient
from tornado.gen import coroutine, Return
from tornado.options import options

from chub.oauth2 import Read, get_token

import logging

@coroutine
def _get_repository(repository_id):
    """Get a repository from the accounts service

    :param repository_id: str
    :returns: repository resource
    :raises: koi.exceptions.HTTPError
    """
    client = API(options.url_accounts, ssl_options=ssl_server_options())

    try:
        repo = yield client.accounts.repositories[repository_id].get()
        raise Return(repo)
    except httpclient.HTTPError as exc:
        if exc.code == 404:
            msg = 'Unknown repository ID'
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
            msg = 'Unexpected error ' + exc.message

        raise exceptions.HTTPError(exc.code, msg, source='accounts')

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
def _get_ids(repository_id, entity_id):
    """Get ids from the repository service

    :param provider_id: str
    :returns: organisation resource
    :raises: koi.exceptions.HTTPError
    """
    repository = yield _get_repository(repository_id)
    repository_url = repository['data']['service']['location']

    token = yield get_token(
        options.url_auth, options.service_id,
        options.client_secret, scope=Read(),
        ssl_options=ssl_server_options()
    )
    client = API(repository_url, token=token, ssl_options=ssl_server_options())

    try:
        res = yield client.repository.repositories[repository_id].assets[entity_id].ids.get()
        raise Return(res['data'])
    except httpclient.HTTPError as exc:
        raise exceptions.HTTPError(exc.code, str(exc), source='repository')

@coroutine
def _get_repos_for_source_id(source_id_type, source_id):
    """Get repositories having information about a specific source_id
    :param source_id_type: type of the source_id
    :param source_id: the id of the asset for which we do the query
    :returns: organisation resource
    :raises: koi.exceptions.HTTPError
    """
    token = yield get_token(
        options.url_auth, options.service_id,
        options.client_secret, scope=Read(),
        ssl_options=ssl_server_options()
    )
    client = API(options.url_index, token=token, ssl_options=ssl_server_options())
    repos = yield client.index['entity-types']['asset']['id-types'][source_id_type].ids[source_id].repositories.get()
    raise Return(repos['data']['repositories'])

@coroutine
def _parse_hub_key(hub_key):
    """Parse a hub key

    :param key: a hub key
    :returns: a parsed hub key, including the provider organisation
    :raises: koi.exceptions.HTTPError
    """
    try:
        parsed = hubkey.parse_hub_key(hub_key)

        if parsed['schema_version'] == 's0':
            provider = yield _get_provider(parsed['organisation_id'])
        else:
            repository = yield _get_repository(parsed['repository_id'])
            provider = yield _get_provider(repository['data']['organisation']['id'])
    except ValueError as exc:
        raise exceptions.HTTPError(404, 'Invalid hub key: ' + exc.message)

    parsed['provider'] = provider['data']
    parsed['provider']['website'] = _parse_url(parsed['provider'].get('website', ''))
    parsed['hub_key'] = hub_key

    raise Return(parsed)

@coroutine
def resolve_link_id_type(reference_links, parsed_key):
    if not reference_links:
        raise Return(None)

    redirect_id_type = reference_links.get('redirect_id_type')

    if not redirect_id_type:
        raise Return(None)

    redirect_id_type = redirect_id_type.lower()

    _link_for_id_type = reference_links.get("links",{}).get(redirect_id_type)

    if not _link_for_id_type:
        raise Return(None)

    if '{source_id}' not in _link_for_id_type:
        raise Return(_link_for_id_type)

    if "id_type" in parsed_key:
        # s0 key
        if parsed_key['id_type'] == redirect_id_type:
            source_ids = [{'source_id_type': parsed_key['id_type'], 'source_id': parsed_key['entity_id']}]
        else:
            repo_ids = yield _get_repos_for_source_id(parsed_key['id_type'], parsed_key['entity_id'])
            source_ids = []

            for repo in repo_ids:
                partial_source_ids = yield _get_ids(repo['repository_id'], repo['entity_id'])
                source_ids += partial_source_ids
    else:
        # s1 key
        source_ids = yield _get_ids(parsed_key['repository_id'], parsed_key['entity_id'])

    link_for_id_type = None
    for cid in source_ids:
        if cid["source_id_type"].lower() == redirect_id_type:
            link_for_id_type = _link_for_id_type.format(source_id=urllib.quote_plus(cid["source_id"]))

    raise Return(link_for_id_type)

@coroutine
def resolve_payment_link_id_type(payment, parsed_key, offer_id):
    if not payment:
        raise Return(None)

    redirect_id_type = payment.get("source_id_type", None)

    if not redirect_id_type:
        raise Return(None)

    redirect_id_type = redirect_id_type.lower()

    _link_for_id_type = payment.get("url", None)

    if not _link_for_id_type:
        raise Return(None)

    if '{source_id}' not in _link_for_id_type:
        raise Return(_link_for_id_type)

    source_ids = yield _get_ids(parsed_key['repository_id'], parsed_key['entity_id'])

    link_for_id_type = None
    for cid in source_ids:
        if cid["source_id_type"].lower() == redirect_id_type:
            try:
                link_for_id_type = _link_for_id_type.format(source_id=urllib.quote_plus(cid["source_id"]), offer_id=offer_id)
            except KeyError:
                raise exceptions.HTTPError(500, 'Payment link missing either {source_id} or {offer_id}', source='resolution')

    raise Return(link_for_id_type)    

def _parse_url(url):
    """Parse a url. If it's got no protocol, adds
    http. If it has protocol, keep it.
    :param url: a url or domain or ip
    :returns: a url
    """
    url = url.strip()
    parsed = urlparse(url)
    if url and not parsed.scheme:
        url = 'http://' + url
    return url

@coroutine
def _get_asset_details(hubkey):
    """ get the asset details from a hubkey
    """
    client = API(options.url_query, ssl_options=ssl_server_options())

    try:
        res = yield client.query.entities.get(hub_key=hubkey)
        raise Return(res['data'])
    except httpclient.HTTPError as exc:
        if exc.code == 404:
            msg = 'No matching asset found'
        else:
            msg = 'Unexpected error ' + exc.message

        raise exceptions.HTTPError(exc.code, msg, source='query')

def getOfferTextValue(offerSnippet, attributeName):
    try:
        return offerSnippet[attributeName]['@value']
    except:
        try:
            return offerSnippet[attributeName]
        except:
            return ''

def testNodeContainsValue(node, prop, searchValue):
    if not node or not prop or not searchValue:
        return False
    elif node.get(prop, '') == '':
        return False
    elif isinstance(node.get(prop), basestring):
        return (node.get(prop) == searchValue)
    else:
        return (searchValue in node.get(prop))

@coroutine
def _get_offers_by_type_and_id(source_id_type, source_id):
    """ get asset offers for given type and id
    :param source_id_type: str
    :param source_id: str
    :returns: list of offers json
    :raises: koi.exceptions.HTTPError
    """
    client = API(options.url_query, ssl_options=ssl_server_options())

    try:
        req_body = '[{"source_id_type": "' + source_id_type + '", "source_id": "' + source_id + '"}]'

        client.query.search.offers.prepare_request(headers={'Content-Type': 'application/json'},
                                                body=req_body.strip())
        res = yield client.query.search.offers.post()
        raise Return(res['data'])        
    except httpclient.HTTPError as exc:
        msg = 'Unexpected error ' + exc.message
        raise exceptions.HTTPError(exc.code, msg, source='query')

def _getCleanQuerystringParts(cls):
    """
    strip our internal parameters from the querystring and return all others

    returns a dict
    """
    cleanQs = {}

    qs = cls.request.query
    parts = parse_qs(qs)

    for x in parts:
        if x not in ['hubpid', 'hubidt', 'hubaid']:
            cleanQs[x] = parts[x]

    return cleanQs

def _mergeQuerystrings(cls, linkUrl):
    """
    takes the linkUrl and adds in any querystring params in the request Url

    returns url string
    """
    if not linkUrl:
        return ''

    url_parts = list(urlparse(linkUrl))
    linkQs = parse_qs(url_parts[4])

    linkQs.update(_getCleanQuerystringParts(cls))

    url_parts[4] = urlencode(linkQs, True)

    return urlunparse(url_parts)
            
@coroutine
def redirectToAsset(cls, provider, assetIdType, assetId, showJson=None):
    # build dummy hub_key so we can re-use existing code to extract asset details
    repo_ids = yield _get_repos_for_source_id(assetIdType.lower(), assetId)
    repository_id = repo_ids[0]['repository_id']
    entity_id = repo_ids[0]['entity_id']
    dummy_hub_key = "http://copyrighthub.org/s1/hub1/%s/asset/%s" % (repository_id, entity_id)

    parsed_key = yield _parse_hub_key(dummy_hub_key)

    reference_links = provider.get('reference_links')

    # get reference links
    link_for_id_type = yield resolve_link_id_type(reference_links, parsed_key)

    # get asset details
    details = yield _get_asset_details(dummy_hub_key)

    asset_details = []
    asset_description = ''

    if details.get('@graph', '') != '':
        for item in details['@graph']:
            if testNodeContainsValue(item, '@type', 'op:Id'):
                asset_detail = {
                    'id': item['op:value']['@value'],
                    'idType': item['op:id_type']['@id'][4:]
                }
                asset_details.append(asset_detail)
            elif testNodeContainsValue(item, '@type', 'op:Asset') and item.get('dcterm:description', '') != '':
                asset_description = item['dcterm:description'].get('@value', '')

    # get offers
    offers = yield _get_offers_by_type_and_id(assetIdType, assetId)

    offer_details = []

    if offers and provider.get('payment', None):
        for offer in offers[0]['offers']:
            # find the actual offer details inside the @graph node
            for snippet in offer['@graph']:
                if snippet.get('type', '') == 'offer':
                    # get payment link
                    offer_id = snippet['@id'][3:]
                    payment_link = yield resolve_payment_link_id_type(provider.get('payment', ''), parsed_key, offer_id)

                    offer_detail = {
                        'title': getOfferTextValue(snippet, 'dcterm:title'),
                        'description': getOfferTextValue(snippet, 'op:policyDescription'),
                        'link': _mergeQuerystrings(cls, payment_link)
                    }
                    
                    offer_details.append(offer_detail)

    # return Json if requested to
    if showJson:
        cls.set_header('Content-Type', 'application/json; charset=UTF-8')

        res = {
            'asset': details,
            'provider': provider,
            'offers': offers
        }
        cls.write(res)
    else:
        # use the reference link if there is one
        if link_for_id_type:
            # replace tokens in reference link with real values
            redirect = _redirect_url(link_for_id_type, parsed_key)

            # add passed-in querystring values
            redirect = _mergeQuerystrings(cls, redirect)

            cls.redirect(redirect)
        else:
            cls.render('asset_template.html', data=provider, assets=asset_details, 
                            description=asset_description, offers=offer_details)

def _redirect_url(url, parsed_key):
    """Take a redirect url string,
    and format using parameters from hub_key.
    :param url: a url or domain or ip
    :param parsed_key: a dictionary of parameters associated with hub_key
    :returns: a url
    """
    try:
        parsed = url.format(**parsed_key)
    except KeyError as exc:
        msg = 'Invalid paramater in Redirect URL: ' + exc.message
        raise exceptions.HTTPError(404, msg)
    return parsed


class HubKeyHandler(base.BaseHandler):
    def initialize(self, **kwargs):
        try:
            self.version = kwargs['version']
        except KeyError:
            raise KeyError('App version is required')

    def write_error(self, status_code, **kwargs):
        """
        Use BaseHandler.write_error if json, otherwise use a html template

        :param status_code: the response's status code, e.g. 500
        """
        if 'application/json' in self.request.headers.get('Accept', '').split(';'):
            return super(HubKeyHandler, self).write_error(status_code, **kwargs)

        if 'exc_info' in kwargs and hasattr(kwargs['exc_info'][1], 'errors'):
            errors = kwargs['exc_info'][1].errors
            if isinstance(errors, basestring):
                errors = [errors]
        else:
            errors = [kwargs.get('reason', self._reason)]

        self.render('error.html', errors=errors)


    @coroutine
    def get(self):
        """
        Resolve a hub key

        Returns JSON if request Content-Type is JSON, and HTML otherwise.
        """
        try:
            hub_key = self.request.full_url()
            parsed_key = yield _parse_hub_key(hub_key)
        except ValueError:
            self.set_status(404)
            self.finish()
            raise Return()

        provider = parsed_key['provider']
        assetIdType = parsed_key['id_type']
        assetId = parsed_key['entity_id']

        yield redirectToAsset(self, provider, assetIdType, assetId)
        