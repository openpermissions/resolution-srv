# -*- coding: utf-8 -*-
# Copyright 2016 Open Permissions Platform
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License. You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed under the License is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under the License.

import pytest
from functools import partial
from mock import patch

from tornado.ioloop import IOLoop

from koi.test_helpers import make_future, gen_test
from resolution.controllers import hub_key_handler


@patch('resolution.controllers.hub_key_handler._get_provider')
def test_parse_hub_key_s0(_get_provider):
    hub_key = 'https://openpermissions.org/s0/hub1/asset/maryevans/maryevanspictureid/10413373'
    _get_provider.return_value = make_future(
        {
            'data': {
                'website': 'www.something.org'
            }
        }
    )
    expected = {
        'resolver_id': 'https://openpermissions.org',
        'schema_version': 's0',
        'hub_id': 'hub1',
        'entity_type': 'asset',
        'organisation_id': 'maryevans',
        'id_type': 'maryevanspictureid',
        'entity_id': '10413373',
        'hub_key': hub_key,
        'provider': {
            'website': 'http://www.something.org'
        }
    }

    result = IOLoop.current().run_sync(
        partial(hub_key_handler._parse_hub_key, hub_key))

    assert _get_provider.call_count == 1
    assert result == expected


@patch('resolution.controllers.hub_key_handler._get_repository')
@patch('resolution.controllers.hub_key_handler._get_provider')
def test_parse_hub_key_s1(_get_provider, _get_repository):
    hub_key = 'https://openpermissions.org/s1/hub1/0123456789abcdef0123456789abcdef/asset/abcdef0123456789abcdef0123456789'
    _get_repository.return_value = make_future({
        'data': {
            'organisation': {'id': 'orguid'}
        }
    })
    _get_provider.return_value = make_future({
        'data': {
            'organisation_id': 'orguid',
            'website': 'www.something.org'
        }
    })
    expected = {
        'entity_id': 'abcdef0123456789abcdef0123456789',
        'entity_type': 'asset',
        'hub_id': 'hub1',
        'repository_id': '0123456789abcdef0123456789abcdef',
        'resolver_id': 'https://openpermissions.org',
        'schema_version': 's1',
        'hub_key': hub_key,
        'provider': {
            'organisation_id': 'orguid',
            'website': 'http://www.something.org'
        }
    }

    result = IOLoop.current().run_sync(
        partial(hub_key_handler._parse_hub_key, hub_key))
    assert _get_provider.call_count == 1
    assert _get_repository.call_count == 1
    assert result == expected


@pytest.mark.parametrize("input,expected", [
    ("www.me.com", "http://www.me.com"),
    ("http://www.me.com", "http://www.me.com"),
    ("https://www.me.com", "https://www.me.com"),
    ("127.0.0.1", "http://127.0.0.1"),
    ("", ""), ])
def test_parse_url(input, expected):
    assert hub_key_handler.parse_url(input) == expected


@gen_test
def test_resolve_link_id_type_no_ref_link():
    res = yield hub_key_handler.resolve_link_id_type(None, {})
    assert res is None

@gen_test
def test_resolve_link_id_type_empty_ref_link():
    res = yield hub_key_handler.resolve_link_id_type({}, {})
    assert res is None

@gen_test
def test_resolve_link_id_type_empty_ref_no_redirect_info():
    res = yield hub_key_handler.resolve_link_id_type({'no_redirect_id_type': True}, {})
    assert res is None

@gen_test
def test_resolve_link_id_type_empty_ref_no_redirect_info2():
    res = yield hub_key_handler.resolve_link_id_type({'redirect_id_type': None}, {})
    assert res is None


@gen_test
def test_resolve_link_id_type_empty_ref_no_links():
    res = yield hub_key_handler.resolve_link_id_type({'redirect_id_type': 'testidtype'}, {})
    assert res is None


@gen_test
def test_resolve_link_id_type_empty_ref_no_links2():
    res = yield hub_key_handler.resolve_link_id_type({'redirect_id_type': 'testidtype',
                                                      'links': {'otheridtype': 'http://test/'}}, {})
    assert res is None


@patch('resolution.controllers.hub_key_handler._get_ids')
@patch('resolution.controllers.hub_key_handler._get_repos_for_source_id')
@gen_test
def test_resolve_link_id_hk_s0(_get_repos_for_source_id, _get_ids):
    _get_repos_for_source_id.return_value = make_future([{'repository_id': '043023143124', 'entity_id': '0102343434'}])
    _get_ids.return_value = make_future([{'source_id_type': 'testidtype', 'source_id': 'this id has spaces and ?'}])
    res = yield hub_key_handler.resolve_link_id_type({'redirect_id_type': 'testidtype',
                                                      'links': {'testidtype': 'http://test/{source_id}'}},
                                                     {'id_type': 'otheridtype', 'entity_id': '321a23'})
    assert res is not None
    assert res == 'http://test/this+id+has+spaces+and+%3F'

@patch('resolution.controllers.hub_key_handler._get_ids')
@gen_test
def test_resolve_link_id_hk_s1(_get_ids):
    _get_ids.return_value = make_future([{'source_id_type': 'testidtype', 'source_id': 'this id has spaces and ?'}])
    res = yield hub_key_handler.resolve_link_id_type({'redirect_id_type': 'testidtype',
                                                      'links': {'testidtype': 'http://test/{source_id}'}}, {
                                                            'repository_id': '043023143124',
                                                            'entity_id': '321a23'
                                                       })
    assert res is not None
    assert res == 'http://test/this+id+has+spaces+and+%3F'