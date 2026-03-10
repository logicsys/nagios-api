#!/usr/bin/env python3
#
# Nagios class.
#

from .core import (  # noqa: F401, E402
    Comment, Downtime, Host, HostOrService, Info,
    Nagios, NagiosObject, Program, Service,
)

version = "1.2.2"
