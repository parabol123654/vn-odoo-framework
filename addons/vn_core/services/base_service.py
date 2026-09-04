# -*- coding: utf-8 -*-
"""Base application service (Part 11 §5).

A Service validates input, resolves collaborators, calls the Domain and returns a
``ResultDTO``. It performs no accounting calculation and no SQL. It is also the
layer that converts framework exceptions into something a caller can use — a
``ResultDTO`` for programmatic callers, a ``UserError`` for Wizards.
"""

import logging
import time

from odoo import _
from odoo.exceptions import AccessError, UserError

from ..core.exceptions import (
    BusinessException, RepositoryException, ValidationException,
    VNFrameworkException,
)
from ..dto.result import ResultDTO

_logger = logging.getLogger(__name__)


class BaseService:

    #: Overridden by subclasses; used for audit logging.
    name = 'service'

    def __init__(self, env):
        self.env = env

    # ------------------------------------------------------------------
    def _execute(self, operation, **audit):
        """Run ``operation``, timing it and normalising every failure."""
        started = time.time()
        try:
            data = operation()
        except VNFrameworkException as error:
            elapsed = time.time() - started
            _logger.warning('%s failed after %.3fs: %s',
                            self.name, elapsed, error)
            return ResultDTO.fail(str(error), elapsed)
        elapsed = time.time() - started
        self._audit(elapsed, **audit)
        return ResultDTO.ok(data, elapsed)

    def _audit(self, elapsed, **context):
        """Audit log lives in the Service, never in the Engine (Part 11 §13)."""
        _logger.info(
            'report=%s user=%s company=%s elapsed=%.3fs %s',
            self.name, self.env.uid, self.env.company.id, elapsed,
            ' '.join('%s=%s' % item for item in sorted(context.items())))

    def _raise_for(self, result):
        """Turn a failed ``ResultDTO`` into the right Odoo exception."""
        if result.success:
            return result
        message = '\n'.join(result.errors)
        # Odoo 14's _() takes the source string only; the multi-argument
        # form arrives in 16.0. Interpolate after translating.
        raise UserError(
            _('%s could not be produced:\n%s') % (self.name, message))

    @staticmethod
    def translate_exception(error):
        """Map a framework exception onto its Odoo counterpart."""
        if isinstance(error, ValidationException):
            return UserError(str(error))
        if isinstance(error, BusinessException):
            return UserError(str(error))
        if isinstance(error, RepositoryException):
            return UserError(str(error))
        return AccessError(str(error))
