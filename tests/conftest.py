# tests/conftest.py
import sys
import types
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
