from __future__ import annotations

import logging
import math

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

PAGE_SIZE = 10


class RankingPaginationView(discord.ui.View):
    def __init__(self, bot: commands.Bot, total: int) -> None:
        super().__init__(timeout=120)
        self.bot = bot
        self.total = total
        self.page = 0
        self.max_page = max(0, math.ceil(total / PAGE_SIZE) - 1)

    async def _build_embed(self) -> discord.Embed:
        from db import Database

        db: Database = self.bot.db
        rows = await db.top_balances(limit=PAGE_SIZE, offset=self.page * PAGE_SIZE)

        embed = discord.Embed(
            title="残高ランキング",
            color=discord.Color.gold(),
        )
        if not rows:
            embed.description = "まだ参加者がいません。"
        else:
            lines = []
            for i, row in enumerate(rows, start=self.page * PAGE_SIZE + 1):
                lines.append(f"**{i}.** <@{row['user_id']}> — {row['balance']}P")
            embed.description = "\n".join(lines)

        embed.set_footer(text=f"ページ {self.page + 1} / {self.max_page + 1}  (全 {self.total} 名)")
        return embed

    async def _refresh(self, interaction: discord.Interaction) -> None:
        embed = await self._build_embed()
        self._update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    def _update_buttons(self) -> None:
        self.first_btn.disabled = self.page == 0
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self.max_page
        self.last_btn.disabled = self.page >= self.max_page

    @discord.ui.button(label="<<", style=discord.ButtonStyle.secondary)
    async def first_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = 0
        await self._refresh(interaction)

    @discord.ui.button(label="<", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = max(0, self.page - 1)
        await self._refresh(interaction)

    @discord.ui.button(label=">", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = min(self.max_page, self.page + 1)
        await self._refresh(interaction)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.secondary)
    async def last_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = self.max_page
        await self._refresh(interaction)


class WalletCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="balance", description="残高を確認します")
    @app_commands.describe(user="確認するユーザー（省略時は自分）")
    async def balance(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        from db import Database

        db: Database = self.bot.db
        target = user or interaction.user
        bal = await db.fetch_balance(target.id)

        embed = discord.Embed(
            title="残高照会",
            description=f"{target.mention} の残高: **{bal}P**",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ranking", description="残高ランキングを表示します")
    async def ranking(self, interaction: discord.Interaction) -> None:
        from db import Database

        db: Database = self.bot.db
        total = await db.count_users()

        view = RankingPaginationView(self.bot, total)
        embed = await view._build_embed()
        view._update_buttons()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WalletCog(bot))
