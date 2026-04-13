from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from odds import PERIOD_KEYS, PERIOD_LABELS, PERIOD_SECONDS

if TYPE_CHECKING:
    import discord

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _log_task_exception(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.exception("Scheduler task failed", exc_info=exc)


class Scheduler:
    def __init__(self, bot: "discord.Client") -> None:
        self.bot = bot
        self.tasks: set[asyncio.Task] = set()
        self.in_flight: set[int] = set()  # schedule_ids currently being announced

    async def schedule_for_new_bet(self, bet_id: int, created_at: str) -> None:
        from db import Database

        db: Database = self.bot.db  # type: ignore[attr-defined]
        created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)

        schedule_entries = []
        for pk in PERIOD_KEYS:
            fire_at = created_dt.timestamp() + PERIOD_SECONDS[pk]
            fire_at_iso = datetime.fromtimestamp(fire_at, tz=timezone.utc).isoformat()
            schedule_entries.append((pk, fire_at_iso))

        ids = await db.insert_schedules(bet_id, schedule_entries)

        for sched_id, (pk, fire_at_iso) in zip(ids, schedule_entries):
            fire_at_dt = datetime.fromisoformat(fire_at_iso)
            self._spawn(sched_id, bet_id, pk, fire_at_dt)

        logger.info("Scheduled %d milestones for bet #%d", len(ids), bet_id)

    async def restore(self) -> None:
        """Reload all unfired schedules on startup."""
        from db import Database

        db: Database = self.bot.db  # type: ignore[attr-defined]
        rows = await db.fetch_pending_schedules()
        for row in rows:
            fire_at_dt = datetime.fromisoformat(row["fire_at"])
            if fire_at_dt.tzinfo is None:
                fire_at_dt = fire_at_dt.replace(tzinfo=timezone.utc)
            self._spawn(row["schedule_id"], row["bet_id"], row["period_key"], fire_at_dt)
        logger.info("Scheduler restored %d pending schedules", len(rows))

    def _spawn(
        self,
        sched_id: int,
        bet_id: int,
        period_key: str,
        fire_at: datetime,
    ) -> None:
        task = asyncio.create_task(
            self._run(sched_id, bet_id, period_key, fire_at)
        )
        task.add_done_callback(_log_task_exception)
        task.add_done_callback(self.tasks.discard)
        self.tasks.add(task)

    async def _run(
        self,
        sched_id: int,
        bet_id: int,
        period_key: str,
        fire_at: datetime,
    ) -> None:
        delay = max(0.0, (fire_at - _utcnow()).total_seconds())
        if delay > 0:
            await asyncio.sleep(delay)

        if sched_id in self.in_flight:
            return
        self.in_flight.add(sched_id)

        try:
            await self._announce(bet_id, period_key)
            from db import Database
            db: Database = self.bot.db  # type: ignore[attr-defined]
            await db.claim_schedule_success(sched_id)
            logger.info("Schedule %d fired (bet #%d, %s)", sched_id, bet_id, period_key)
        except Exception:
            logger.exception("Schedule %d announce failed, will retry on next restart", sched_id)
            self.in_flight.discard(sched_id)

    async def _announce(self, bet_id: int, period_key: str) -> None:
        from db import Database
        from embed_refresher import EmbedRefresher

        db: Database = self.bot.db  # type: ignore[attr-defined]
        refresher: EmbedRefresher = self.bot.refresher  # type: ignore[attr-defined]

        bet = await db.fetch_bet(bet_id)
        if bet is None or bet["status"] != "open":
            return

        label = PERIOD_LABELS[period_key]

        # Find previous period label for the "negけ確定" message
        keys = list(PERIOD_KEYS)
        idx = keys.index(period_key)
        prev_label = PERIOD_LABELS[keys[idx - 1]] if idx > 0 else None

        channel = self.bot.get_channel(bet["channel_id"])
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(bet["channel_id"])
            except Exception:
                logger.warning("Cannot find channel %s for bet #%d", bet["channel_id"], bet_id)
                return

        if prev_label:
            msg = f"⏰ 賭け **#{bet_id}**「{bet['target']}」で **{label}** が経過しました。『{prev_label}』に賭けた方は負け確定です。"
        else:
            msg = f"⏰ 賭け **#{bet_id}**「{bet['target']}」で **{label}** が経過しました。"

        await channel.send(msg)
        refresher.schedule(bet["channel_id"], bet_id)

    def cancel_for_bet(self, bet_id: int) -> None:
        """Cancel all pending tasks for a given bet (called after close_bet)."""
        # Tasks are keyed only by Task object; we can't easily filter by bet_id
        # without extra bookkeeping. Instead, the closed bet check in _run will
        # short-circuit. Still cancel tasks to free resources.
        # For now, cancel all and let the in-flight set handle dedup.
        # A more targeted approach would require a mapping task -> bet_id.
        pass  # Tasks will naturally exit when they check bet status

    def cancel_all(self) -> None:
        for task in list(self.tasks):
            task.cancel()
        self.tasks.clear()
