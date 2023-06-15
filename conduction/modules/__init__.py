# Copyright © 2019-present gsfernandes81

# This file is part of "conduction-tines".

# conduction-tines is free software: you can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.

# "conduction-tines" is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License along with
# conduction-tines. If not, see <https://www.gnu.org/licenses/>.

import os
import pkgutil
import importlib

__all__ = []
for loader, module_name, is_pkg in pkgutil.walk_packages(__path__):
    # Loads all modules in this directory
    module = importlib.import_module("." + module_name, package=__name__)

    # If the module has a _no_register attribute, and it's set to True, don't register it
    # in __all__
    try:
        do_not_register = module._no_register
    except AttributeError:
        do_not_register = False

    if do_not_register:
        continue
    else:
        __all__.append(module_name)
        globals()[module_name] = module
