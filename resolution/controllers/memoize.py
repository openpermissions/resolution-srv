# -*- coding: utf-8 -*-
# Copyright 2016 Open Permissions Platform Coalition
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License. You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed under the License is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under the License.

from tornado.options import options

import time

class Memoize:
    def __init__(self, fn):
        self.fn = fn
        self.memo = {}
        self.timestamp = {}
        self.items = 0

    def __call__(self, *args):
        # clear if too many items (to stop memory being consumed indefinitely)
        if self.items > options.memoize_max_items:
            self.memo = {}
            self.timestamp = {}
            self.items = 0
            
        if args not in self.memo:
            # execute function and store if not already in memo
            self.memo[args] = self.fn(*args)
            self.timestamp[args] = time.time()
            self.items += 1
        elif time.time() > self.timestamp[args] + options.memoize_seconds:
            # execute function and store if passed expiry time
            self.memo[args] = self.fn(*args)
            self.timestamp[args] = time.time()

        return self.memo[args]
