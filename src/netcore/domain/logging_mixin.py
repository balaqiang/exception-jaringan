"""Reusable logging mixin."""

from __future__ import annotations

import logging


class LoggerMixin:
    """Provide ``self.logger`` bound to the concrete class name."""

    @property
    def logger(self) -> logging.Logger:
        """Return a module logger named after the class."""
        return logging.getLogger(f"netcore.{type(self).__name__.lower()}")
