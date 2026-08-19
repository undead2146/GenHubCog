from .genhub import GenHub


async def setup(bot):
    cog = GenHub(bot)
    await bot.add_cog(cog)
