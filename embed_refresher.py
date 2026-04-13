from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord

logger = logging.getLogger(__name__)


def _log_task_exception(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.exception("EmbedRefresher task failed", exc_info=exc)


class EmbedRefresher:
    def __init__(self, bot: "discord.Client") -> None:
        self.bot = bot
        self.pending: dict[int, set[int]] = {}   # channel_id -> {bet_id, ...}
        self.tasks: dict[int, asyncio.Task] = {}

    def schedule(self, channel_id: int, bet_id: int) -> None:
        self.pending.setdefault(channel_id, set()).add(bet_id)
        if channel_id not in self.tasks or self.tasks[channel_id].done():
            task = asyncio.create_task(self._drain(channel_id))
            task.add_done_callback(_log_task_exception)
            self.tasks[channel_id] = task

    async def _drain(self, channel_id: int) -> None:
        try:
            await asyncio.sleep(2.0)
            batch = self.pending.pop(channel_id, set())
            for bet_id in list(batch)[:4]:
                try:
                    await self._do_refresh(bet_id)
                except Exception:
                    logger.exception("refresh failed bet=%s", bet_id)
            leftover = list(batch)[4:]
            if leftover:
                self.pending.setdefault(channel_id, set()).update(leftover)
                task = asyncio.create_task(self._drain(channel_id))
                task.add_done_callback(_log_task_exception)
                self.tasks[channel_id] = task
        finally:
            self.tasks.pop(channel_id, None)

    async def _do_refresh(self, bet_id: int) -> None:
        from db import Database
        from embeds import build_bet_embed

        db: Database = self.bot.db  # type: ignore[attr-defined]
        bet = await db.fetch_bet(bet_id)
        if bet is None or bet["status"] != "open":
            return

        entries = await db.fetch_bet_entries(bet_id)
        live = await db.fetch_live_periods_tx(db.conn, bet_id)

        channel = self.bot.get_channel(bet["channel_id"])
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(bet["channel_id"])
            except Exception:
                logger.warning("Cannot fetch channel %s", bet["channel_id"])
                return

        try:
            message = await channel.fetch_message(bet["message_id"])
        except Exception:
            logger.warning("Cannot fetch message %s for bet %s", bet["message_id"], bet_id)
            return

        embed = build_bet_embed(bet, entries, live)
        await message.edit(embed=embed)

    def cancel_all(self) -> None:
        for task in self.tasks.values():
            task.cancel()
        self.tasks.clear()
        self.pending.clear()
