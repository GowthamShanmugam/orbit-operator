"""Kopf entry point -- import all handlers so they register with the framework."""

import kopf  # noqa: F401

from orbit_operator.handlers import create, delete, update  # noqa: F401
from orbit_operator.handlers import status as status_handler  # noqa: F401
