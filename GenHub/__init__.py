import sys
print('<<<<< LOADING GenHub FROM THIS FILE >>>>>', file=sys.stderr)

async def setup(bot):
    from .genhub import GenHub
    await bot.add_cog(GenHub(bot))
