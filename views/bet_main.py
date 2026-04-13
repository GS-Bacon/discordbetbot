from __future__ import annotations

import logging

import discord
from discord import ui

import bet_service

logger = logging.getLogger(__name__)


class JoinBetButton(
    ui.DynamicItem[ui.Button],
    template=r"bet:(?P<bet_id>\d+):join",
):
    def __init__(self, bet_id: int) -> None:
        self.bet_id = bet_id
        super().__init__(
            ui.Button(
                label="参加する",
                style=discord.ButtonStyle.primary,
                custom_id=f"bet:{bet_id}:join",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: ui.Button,
        match: "re.Match[str]",
        /,
    ) -> "JoinBetButton":
        return cls(int(match["bet_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        from views.period_select import PeriodSelectView

        bet_id = self.bet_id
        view = await PeriodSelectView.create(interaction.client, bet_id)
        if view is None:
            await interaction.response.send_message(
                "この賭けはすでに終了しています。", ephemeral=True
            )
            return

        bal = await interaction.client.db.fetch_balance(interaction.user.id)
        await interaction.response.send_message(
            f"期間を選んでください：\n現在残高: **{bal}P**",
            view=view,
            ephemeral=True,
        )


class RefreshBetButton(
    ui.DynamicItem[ui.Button],
    template=r"bet:(?P<bet_id>\d+):refresh",
):
    def __init__(self, bet_id: int) -> None:
        self.bet_id = bet_id
        super().__init__(
            ui.Button(
                label="状況を更新",
                style=discord.ButtonStyle.secondary,
                custom_id=f"bet:{bet_id}:refresh",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: ui.Button,
        match: "re.Match[str]",
        /,
    ) -> "RefreshBetButton":
        return cls(int(match["bet_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        from embed_refresher import EmbedRefresher

        refresher: EmbedRefresher = interaction.client.refresher  # type: ignore[attr-defined]
        channel_id = interaction.channel_id
        if channel_id is not None:
            refresher.schedule(channel_id, self.bet_id)
        await interaction.response.send_message("Embed を更新しました。", ephemeral=True)


class CloseBetButton(
    ui.DynamicItem[ui.Button],
    template=r"bet:(?P<bet_id>\d+):close",
):
    def __init__(self, bet_id: int) -> None:
        self.bet_id = bet_id
        super().__init__(
            ui.Button(
                label="飽きた",
                style=discord.ButtonStyle.danger,
                custom_id=f"bet:{bet_id}:close",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: ui.Button,
        match: "re.Match[str]",
        /,
    ) -> "CloseBetButton":
        return cls(int(match["bet_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            result = await bet_service.close_bet(
                interaction.client,
                self.bet_id,
                interaction.user.id,
            )
        except bet_service.NotAllowed:
            await interaction.followup.send(
                "賭けを作成した本人のみが宣言できます。", ephemeral=True
            )
            return
        except bet_service.BetAlreadyClosed:
            await interaction.followup.send(
                "この賭けはすでに終了しています。", ephemeral=True
            )
            return
        except bet_service.BetNotFound:
            await interaction.followup.send("賭けが見つかりません。", ephemeral=True)
            return
        except Exception:
            logger.exception("close_bet failed for bet #%d", self.bet_id)
            await interaction.followup.send("エラーが発生しました。", ephemeral=True)
            return

        from odds import PERIOD_LABELS
        if result.winners:
            winner_labels = "・".join(PERIOD_LABELS[w] for w in result.winners)
            msg = (
                f"賭け **#{result.bet_id}** を締め切りました。\n"
                f"経過時間: {int(result.elapsed_sec)}秒\n"
                f"勝ち期間: **{winner_labels}**"
            )
        else:
            msg = f"賭け **#{result.bet_id}** を締め切りました（参加者なし）。"

        await interaction.followup.send(msg, ephemeral=True)


def build_bet_view(bet_id: int) -> ui.View:
    view = ui.View(timeout=None)
    view.add_item(JoinBetButton(bet_id))
    view.add_item(RefreshBetButton(bet_id))
    view.add_item(CloseBetButton(bet_id))
    return view
