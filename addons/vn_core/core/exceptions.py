# -*- coding: utf-8 -*-
"""Framework exception hierarchy (Part 3 §12).

Pure Python: no Odoo import. The Service layer is responsible for translating
these into ``UserError`` / ``AccessError`` when the caller is a Wizard.
"""


class VNFrameworkException(Exception):
    """Base of every framework exception."""


class ValidationException(VNFrameworkException):
    """Input DTO failed validation. Raised by Validators, before Repository."""


class BusinessException(VNFrameworkException):
    """A business rule was violated. Raised by Domain."""


class RepositoryException(VNFrameworkException):
    """Data access failed. Raised by Infrastructure only."""


class MappingException(BusinessException):
    """Financial statement mapping is invalid (Part 9 §14)."""


class ReportException(VNFrameworkException):
    """Rendering failed. Raised by the Report Engine."""
