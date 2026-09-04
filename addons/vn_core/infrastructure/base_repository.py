# -*- coding: utf-8 -*-
"""Base repository (Part 6 §5).

Holds the Odoo environment and nothing else — no business rules. This is the
boundary where the pure-Python Domain meets Odoo.
"""

import logging

_logger = logging.getLogger(__name__)


class BaseRepository:

    def __init__(self, env):
        self.env = env

    @property
    def cr(self):
        return self.env.cr

    @property
    def uid(self):
        return self.env.uid

    @property
    def company(self):
        return self.env.company

    def _log_slow(self, label, seconds, threshold=1.0):
        if seconds >= threshold:
            _logger.info('%s took %.3fs', label, seconds)
