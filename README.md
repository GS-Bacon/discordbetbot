# Discord Bet Bot

Discord 上で「いつ飽きるか」などの*期間予想*を賭けるゲーム BOT。

## セットアップ

```bash
# 1. 依存パッケージのインストール（venv 推奨）
pip install -r requirements-dev.txt

# 2. .env 作成
cp .env.example .env
# DISCORD_TOKEN と DEV_GUILD_ID を設定する

# 3. テスト実行
pytest tests/

# 4. BOT 起動
python bot.py
```

## Discord Developer Portal の設定

1. https://discord.com/developers/applications → New Application
2. Bot タブ → Reset Token → .env に貼り付け
3. Bot の必要な権限:
   - `Send Messages`
   - `Embed Links`
   - `Use Application Commands`
4. OAuth2 → URL Generator: scopes `bot` + `applications.commands`
5. 生成した URL でサーバーに招待

## スラッシュコマンド

| コマンド | 説明 |
|---|---|
| `/bet-create target:<text>` | 新しい賭けを作成 |
| `/bet-list` | 進行中の賭け一覧 |
| `/balance [user]` | 残高確認 |
| `/ranking` | リーダーボード（10 名/ページ） |

## 賭けの流れ

1. `/bet-create target:テストゲームをいつ飽きる？` でEmbedを投稿
2. **[参加する]** を押して期間を選択（100P消費、500Pボーナス付与）
3. 各期間が経過するとチャンネルに自動通知
4. 作成者が **[飽きた]** を押すと締め切り・配当計算・結果発表

## タイマーのテスト（期間短縮）

```bash
# 例: 全期間を数十秒に圧縮
PERIOD_SECONDS_OVERRIDE='{"1d":10,"3d":20,"1w":30,"2w":40,"1mo":50,"3mo":60,"6mo":70,"1y":80}' python bot.py
```

## DB リセット

```bash
python scripts/reset_db.py
```

## アーキテクチャ

```
bot.py              エントリポイント
config.py           .env 読み込み
db.py               aiosqlite、スキーマ、クエリ
odds.py             配当計算（純粋関数）
scheduler.py        期間経過通知タスク
embeds.py           Embed 構築
embed_refresher.py  デバウンス更新 (5 edits/5s 対策)
bet_service.py      ビジネスロジック（cogs / views から共有）
views/              DynamicItem ボタン・Select
cogs/               スラッシュコマンド
tests/              pytest ユニットテスト
```
