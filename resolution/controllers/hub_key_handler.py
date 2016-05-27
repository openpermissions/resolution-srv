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
from urlparse import urlparse

from bass import hubkey
from chub import API
from koi import base, exceptions
from koi.configure import ssl_server_options
from tornado import httpclient
from tornado.gen import coroutine, Return
from tornado.options import options

from chub.oauth2 import Read, get_token


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
    parsed['provider']['website'] = parse_url(parsed['provider'].get('website', ''))
    parsed['hub_key'] = hub_key

    raise Return(parsed)

@coroutine
def resolve_link_id_type(reference_links, parsed_key):
    if not reference_links:
        raise Return(None)

    redirect_id_type = reference_links.get('redirect_id_type')

    if not redirect_id_type:
        raise Return(None)

    _link_for_id_type = reference_links.get("links",{}).get(redirect_id_type)

    if not _link_for_id_type:
        raise Return(None)

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
        if cid["source_id_type"] == redirect_id_type:
            if '{source_id}' not in _link_for_id_type:
                link_for_id_type=_link_for_id_type
            else:
                link_for_id_type = _link_for_id_type.format(source_id=urllib.quote_plus(cid["source_id"]))

    raise Return(link_for_id_type)

def parse_url(url):
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

        reference_links = parsed_key['provider'].get('reference_links')
        link_for_id_type = yield resolve_link_id_type(reference_links, parsed_key)

        if link_for_id_type:
            redirect = _redirect_url(link_for_id_type, parsed_key)
            self.redirect(redirect)
        elif 'application/json' in self.request.headers.get('Accept', '').split(';'):
            self.write(parsed_key)
        else:
            self.render('template.html', hub_key=parsed_key)
