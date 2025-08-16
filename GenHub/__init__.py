from .genhub import GenHub

async def setup(bot):
    await bot.add_cog(GenHub(bot))