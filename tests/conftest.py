import sys
import types
import pytest
import GenHub.utils as utils
from unittest.mock import MagicMock


# ----- redbot.core.commands stub -----
commands_mod = types.ModuleType("redbot.core.commands")

class Cog:
    pass

def is_owner():
    def decorator(func):
        return func
    return decorator

class _GroupWrapper:
    def __init__(self, func):
        self.func = func
    def __call__(self, *a, **kw):
        return self.func(*a, **kw)
    def command(self, *dargs, **dkwargs):
        def deco(f):
            return f
        return deco

def group(*gargs, **gkwargs):
    def deco(func):
        return _GroupWrapper(func)
    return deco

def command(*cargs, **ckwargs):
    def deco(func):
        return func
    return deco

commands_mod.Cog = Cog
commands_mod.is_owner = is_owner
commands_mod.group = group
commands_mod.command = command

# ----- redbot.core.bot stub -----
bot_mod = types.ModuleType("redbot.core.bot")
class Red:
    pass
bot_mod.Red = Red

# ----- redbot.core.app_commands stub -----
app_commands_mod = types.ModuleType("redbot.core.app_commands")
def app_command_decorator(**kwargs):
    def deco(func):
        return func
    return deco
app_commands_mod.command = app_command_decorator

# ----- redbot.core.config stub -----
config_mod = types.ModuleType("redbot.core.config")

class DummyConfig:
    @classmethod
    def get_conf(cls, *args, **kwargs):
        # Return a MagicMock that behaves like a config object
        return MagicMock()

config_mod.Config = DummyConfig

# ----- redbot.core parent -----
core_mod = types.ModuleType("redbot.core")
core_mod.commands = commands_mod
core_mod.bot = bot_mod
core_mod.app_commands = app_commands_mod
core_mod.config = config_mod
core_mod.Config = DummyConfig

# ----- top-level redbot package -----
redbot_mod = types.ModuleType("redbot")
redbot_mod.core = core_mod

# Install into sys.modules
sys.modules["redbot"] = redbot_mod
sys.modules["redbot.core"] = core_mod
sys.modules["redbot.core.commands"] = commands_mod
sys.modules["redbot.core.bot"] = bot_mod
sys.modules["redbot.core.app_commands"] = app_commands_mod
sys.modules["redbot.core.config"] = config_mod

import pytest
import asyncio

@pytest.fixture(autouse=True)
def clear_thread_cache_and_restore_utils():
    """Autouse fixture that clears the thread cache and restores
    GenHub.utils.get_or_create_thread to its original implementation
    before and after each test to avoid cross-test pollution.
    """
    # Import the utils module from the package under test
    try:
        import GenHub.utils as _utils
    except Exception:
        # If import fails, just yield (some tests may not need utils)
        yield
        return

    # Stash the original implementation once
    if not hasattr(_utils, "_ORIG_get_or_create_thread"):
        _utils._ORIG_get_or_create_thread = getattr(_utils, "get_or_create_thread", None)

    # Pre-test cleanup/restore
    if hasattr(_utils, "thread_cache"):
        try:
            _utils.thread_cache.clear()
        except Exception:
            pass
    if _utils._ORIG_get_or_create_thread is not None:
        _utils.get_or_create_thread = _utils._ORIG_get_or_create_thread

    yield

    # Post-test cleanup/restore
    if hasattr(_utils, "thread_cache"):
        try:
            _utils.thread_cache.clear()
        except Exception:
            pass
    if _utils._ORIG_get_or_create_thread is not None:
        _utils.get_or_create_thread = _utils._ORIG_get_or_create_thread
