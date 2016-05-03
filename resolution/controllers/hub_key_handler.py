# -*- coding: utf-8 -*-
# Copyright 2016 Open Permissions Platform Coalition
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License. You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed under the License is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under the License.

"""Resolve a Hub Key"""
from urlparse import urlparse

from bass import hubkey
from chub import API
from koi import base, exceptions
from tornado import httpclient
from tornado.gen import coroutine, Return
from tornado.options import options


@coroutine
def _get_repository(repository_id):
    """Get a repository from the accounts service

    :param repository_id: str
    :returns: repository resource
    :raises: koi.exceptions.HTTPError
    """
    client = API(options.url_accounts, ca_certs=options.ssl_ca_cert)

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
    client = API(options.url_accounts, ca_certs=options.ssl_ca_cert)

    try:
        org = yield client.accounts.organisations[provider_id].get()
        raise Return(org)
    except httpclient.HTTPError as exc:
        if exc.code == 404:
            msg = 'Unknown provider ID'
        else:
            msg = 'Unexpected error'

        raise exceptions.HTTPError(exc.code, msg, source='acocunts')


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
        hub_key = self.request.full_url()
        parsed_key = yield _parse_hub_key(hub_key)

        reference_links = parsed_key['provider'].get('reference_links')
        link_for_id_type = reference_links.get(parsed_key['id_type'])

        if reference_links and link_for_id_type:
            redirect = _redirect_url(link_for_id_type, parsed_key)
            self.redirect(redirect, True)
        elif 'application/json' in self.request.headers.get('Accept', '').split(';'):
            self.write(parsed_key)
        else:
            self.render('template.html', hub_key=parsed_key)
