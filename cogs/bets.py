from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

import bet_service

logger = logging.getLogger(__name__)


class BetsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="bet-create", description="新しい賭けを作成します")
    @app_commands.describe(target="賭けの対象（自由記述）")
    async def bet_create(
        self,
        interaction: discord.Interaction,
        target: str,
    ) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            bet_id = await bet_service.create_bet(
                self.bot,
                interaction.user.id,
                target,
                interaction.channel,
            )
        except Exception:
            logger.exception("bet_create failed for user %d", interaction.user.id)
            await interaction.followup.send("賭けの作成に失敗しました。", ephemeral=True)
            return

        await interaction.followup.send(
            f"賭け **#{bet_id}** を作成しました！",
            ephemeral=True,
        )

    @app_commands.command(name="bet-list", description="進行中の賭け一覧を表示します")
    async def bet_list(self, interaction: discord.Interaction) -> None:
        from db import Database

        db: Database = self.bot.db
        bets = await db.fetch_open_bets()

        if not bets:
            await interaction.response.send_message("進行中の賭けはありません。", ephemeral=True)
            return

        embed = discord.Embed(title="進行中の賭け一覧", color=discord.Color.blue())
        lines = []
        for b in bets[:20]:
            guild_id = interaction.guild_id or 0
            jump = f"https://discord.com/channels/{guild_id}/{b['channel_id']}/{b['message_id']}"
            lines.append(f"**#{b['bet_id']}** [{b['target']}]({jump})")

        embed.description = "\n".join(lines)
        if len(bets) > 20:
            embed.set_footer(text=f"他 {len(bets) - 20} 件")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BetsCog(bot))
