import os
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

from pie import check, exceptions, i18n, logger, utils

import grapher


_PUMPKIN_DUMP_DIRECTORY: str = os.getenv("PUMPKIN_DUMP_DIRECTORY")


def test_dotenv() -> None:
    if type(_PUMPKIN_DUMP_DIRECTORY) != str:
        raise exceptions.DotEnvException("PUMPKIN_DUMP_DIRECTORY is not set.")
    if not os.path.isdir(_PUMPKIN_DUMP_DIRECTORY):
        raise exceptions.DotEnvException(
            "PUMPKIN_DUMP_DIRECTORY does not point to valid directory."
        )


test_dotenv()

PUMPKIN_DUMP_DIRECTORY = Path(_PUMPKIN_DUMP_DIRECTORY)


_ = i18n.Translator("modules/dump").translate
guild_log = logger.Guild.logger()


class Dump(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.guild_only()
    @check.acl2(check.ACLevel.MEMBER)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.group(name="db-dump")
    async def dbdump_(self, ctx):
        """Display long-term bot usage statistics."""
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.MEMBER)
    @dbdump_.command(name="options")
    async def dbdump_options(self, ctx):
        """Display which data are available."""
        await ctx.reply(
            _(
                ctx,
                "`pumpkin-dump-tool` can decode several types of information. "
                "I may not have them all, though, if they are managed by some other bot.",
            )
            + "\n\n"
            + _(ctx, "The supported types of content are:")
            + "\n> "
            + ", ".join(grapher.extract.CONTENT)
        )

    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    @check.acl2(check.ACLevel.MEMBER)
    @dbdump_.command(name="get")
    async def dbdump_get(
        self,
        ctx,
        content: str,
        content2: Optional[str] = None,
        content3: Optional[str] = None,
    ):
        """Display your statistics for up to three types of content."""
        if content not in grapher.extract.CONTENT:
            await ctx.reply(_(ctx, "I don't know how to show this kind of data."))
            return
        if content2 is not None and content2 not in grapher.extract.CONTENT:
            await ctx.reply(
                _(ctx, "I don't know how to display the second type of content.")
            )
            return
        if content3 is not None and content3 not in grapher.extract.CONTENT:
            await ctx.reply(
                _(ctx, "I don't know how to display the third type of content.")
            )
            return

        files = grapher.extract._scan_directory(PUMPKIN_DUMP_DIRECTORY)

        async with ctx.typing():
            scanner = grapher.extract.scanners.get_scanner(content)
            data0 = scanner.search(ctx.guild.id, ctx.author.id, files)

            if content2:
                scanner2 = grapher.extract.scanners.get_scanner(content2)
                data2 = scanner2.search(ctx.guild.id, ctx.author.id, files)
            else:
                data2 = None

            if content3:
                scanner3 = grapher.extract.scanners.get_scanner(content3)
                data3 = scanner3.search(ctx.guild.id, ctx.author.id, files)
            else:
                data3 = None

            writer = grapher.extract.writers.CSVWriter(scanner, data0)

            Path("/tmp/pumpkin.py/").mkdir(exist_ok=True)
            csv = Path(f"/tmp/pumpkin.py/{ctx.guild.id}_{ctx.author.id}_{content}.csv")
            png = Path(f"/tmp/pumpkin.py/{ctx.guild.id}_{ctx.author.id}_{content}.png")

            writer.dump(csv)

            chart = grapher.graph.graph(csv, series_name=content)
            if data2 is not None:
                chart.add(content2, [v for v in data2.values()])
            if data3 is not None:
                chart.add(content3, [v for v in data3.values()])

            timespan = chart.title
            chart.title = f"{ctx.author.name}, {ctx.guild.name}\n{timespan}"

            chart.render_to_png(str(png))

            with png.open("rb") as handle:
                await ctx.reply(file=discord.File(fp=handle, filename=f"{content}.png"))

        csv.unlink()
        png.unlink()

    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    @check.acl2(check.ACLevel.MEMBER)
    @dbdump_.command(name="compare")
    async def dbdump_compare(
        self,
        ctx,
        content: str,
        member1: discord.Member,
        member2: Optional[discord.Member] = None,
        member3: Optional[discord.Member] = None,
    ):
        """Compare your statistics with up to three other members."""
        if content not in grapher.extract.CONTENT:
            await ctx.reply(_(ctx, "I don't know how to show this kind of data."))
            return

        scanner = grapher.extract.scanners.get_scanner(content)
        files = grapher.extract._scan_directory(PUMPKIN_DUMP_DIRECTORY)

        async with ctx.typing():
            data0 = scanner.search(ctx.guild.id, ctx.author.id, files)
            data1 = scanner.search(ctx.guild.id, member1.id, files)
            data2 = scanner.search(ctx.guild.id, member2.id, files) if member2 else None
            data3 = scanner.search(ctx.guild.id, member3.id, files) if member3 else None

            writer = grapher.extract.writers.CSVWriter(scanner, data0)

            Path("/tmp/pumpkin.py/").mkdir(exist_ok=True)
            csv = Path(f"/tmp/pumpkin.py/{ctx.guild.id}_{ctx.author.id}_{content}.csv")
            png = Path(f"/tmp/pumpkin.py/{ctx.guild.id}_{ctx.author.id}_{content}.png")

            writer.dump(csv)
            chart = grapher.graph.graph(csv, series_name=ctx.author.name)

            chart.add(member1.display_name, [v for v in data1.values()])
            if data2 is not None:
                chart.add(member2.display_name, [v for v in data2.values()])
            if data3 is not None:
                chart.add(member3.display_name, [v for v in data3.values()])

            timespan = chart.title
            chart.title = f"{content}, {ctx.guild.name}\n{timespan}"

            chart.render_to_png(str(png))

            with png.open("rb") as handle:
                await ctx.reply(file=discord.File(fp=handle, filename=f"{content}.png"))

        csv.unlink()
        png.unlink()


async def setup(bot) -> None:
    await bot.add_cog(Dump(bot))
