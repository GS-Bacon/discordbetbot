from __future__ import annotations

import logging
from typing import Any

import discord
from discord import ui

import bet_service
from odds import PERIOD_KEYS, PERIOD_LABELS, PERIOD_MULT

logger = logging.getLogger(__name__)


class PeriodSelectView(ui.View):
    def __init__(self, bot: Any, bet_id: int, live_periods: list[str]) -> None:
        super().__init__(timeout=120)
        self.bet_id = bet_id
        options = [
            discord.SelectOption(
                label=f"{PERIOD_LABELS[pk]}  ({PERIOD_MULT[pk]}x)",
                value=pk,
            )
            for pk in PERIOD_KEYS
            if pk in live_periods
        ]
        select = ui.Select(
            placeholder="期間を選択",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._select_callback
        self.add_item(select)
        self._select = select

    @classmethod
    async def create(cls, bot: Any, bet_id: int) -> "PeriodSelectView | None":
        """
        Factory: fetch live periods from DB and build the view.
        Returns None if the bet is closed or has no live periods.
        """
        from db import Database

        db: Database = bot.db
        bet = await db.fetch_bet(bet_id)
        if bet is None or bet["status"] != "open":
            return None

        live = await db.fetch_live_periods_tx(db.conn, bet_id)
        if not live:
            return None

        return cls(bot, bet_id, live)

    async def _select_callback(self, interaction: discord.Interaction) -> None:
        period_key = self._select.values[0]
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            result = await bet_service.join_bet(
                interaction.client,
                self.bet_id,
                interaction.user.id,
                period_key,
            )
        except bet_service.PeriodEliminated:
            await interaction.followup.send(
                "選択した期間はすでに負け確定です。別の期間を選んでください。",
                ephemeral=True,
            )
            return
        except bet_service.BetAlreadyClosed:
            await interaction.followup.send(
                "この賭けはすでに終了しています。",
                ephemeral=True,
            )
            return
        except Exception:
            logger.exception("join_bet failed for bet #%d user %d", self.bet_id, interaction.user.id)
            await interaction.followup.send("エラーが発生しました。", ephemeral=True)
            return

        from embeds import build_participation_embed

        embed = build_participation_embed(self.bet_id, result.period_key, result.new_balance)
        await interaction.followup.send(embed=embed, ephemeral=True)
        self.stop()
