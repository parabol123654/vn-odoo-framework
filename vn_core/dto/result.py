# -*- coding: utf-8 -*-
"""Result DTO (Part 3 §16, Part 10 §13).

Every Service returns one of these — never raw data, never a tuple.
"""

from typing import Any, NamedTuple, Tuple


class ResultDTO(NamedTuple):
    success: bool
    data: Any = None
    messages: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()
    execution_time: float = 0.0

    @classmethod
    def ok(cls, data, execution_time=0.0, warnings=(), messages=()):
        return cls(True, data, tuple(messages), tuple(warnings), (),
                   execution_time)

    @classmethod
    def fail(cls, errors, execution_time=0.0):
        if isinstance(errors, str):
            errors = (errors,)
        return cls(False, None, (), (), tuple(errors), execution_time)
