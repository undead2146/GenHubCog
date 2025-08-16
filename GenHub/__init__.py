import sys
print('<<<<< LOADING GenHub FROM THIS FILE >>>>>', file=sys.stderr)
from .genhub import GenHub

async def setup(bot):
    await bot.add_cog(GenHub(bot))