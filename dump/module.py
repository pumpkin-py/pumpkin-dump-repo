import os
import tempfile
from pathlib import Path

import nextcord
from nextcord.ext import commands

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

    @commands.group(name="db-dump")
    async def dbdump_(self, ctx):
        await utils.discord.send_help(ctx)

    @dbdump_.command(name="options")
    async def dbdump_options(self, ctx):
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

    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    @dbdump_.command(name="get")
    async def dbdump_get(self, ctx, content: str):
        if content not in grapher.extract.CONTENT:
            await ctx.reply(_(ctx, "I don't know how to show this kind of data."))
            return

        scanner = grapher.extract.scanners.get_scanner(content)
        files = grapher.extract._scan_directory(PUMPKIN_DUMP_DIRECTORY)

        async with ctx.typing():
            data = scanner.search(ctx.guild.id, ctx.author.id, files)

            writer = grapher.extract.writers.CSVWriter(scanner, data)

            Path("/tmp/pumpkin.py/").mkdir(exist_ok=True)
            csv = Path(f"/tmp/pumpkin.py/{ctx.guild.id}_{ctx.author.id}_{content}.csv")
            png = Path("/tmp/pumpkin.py/dump.png")

            writer.dump(csv)

            chart = grapher.graph.graph(csv)

            # TODO This may be broken when the tool changes.
            # Which it may, because this is not pretty workaround.
            timespan = chart.title.split("\n")[1]
            chart.title = f"{content}, {ctx.author.name}, {ctx.guild.name}\n{timespan}"

            chart.render_to_png(str(png))

            with png.open("rb") as handle:
                await ctx.reply(
                    file=nextcord.File(fp=handle, filename=f"{content}.png")
                )

        csv.unlink()
        png.unlink()


def setup(bot) -> None:
    bot.add_cog(Dump(bot))
