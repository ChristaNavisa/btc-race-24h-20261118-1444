# BTC Momentum Bot — Race a BTC trading bot live for 24 hours

[![make.fun](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/c/btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/ChristaNavisa/btc-race-24h-20261118-1444/rank.svg)](https://make.fun/c/btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/ChristaNavisa/btc-race-24h-20261118-1444/reward.svg)](https://make.fun/c/btc-race-24h-20261118-1444)

A long-only momentum bot that trades Coinbase Wrapped BTC (cbBTC) against
USDC on 1-minute bars, built for the
[make.fun competition "Race a BTC trading bot live for 24 hours"](https://make.fun/c/btc-race-24h-20261118-1444).
Paper money only: it starts with $1,000, pays 4 bps fee + 2 bps slippage
plus pool price impact on every fill, and is ranked by net PnL on the
24-hour race window.

## Strategy

`main.py` (Python 3.13, standard library only) speaks
`agent-fun/bars-replay/v1` on stdin/stdout: one JSON line per minute,
one reply per batch.

- **Enter** when the 60-bar trailing return is at least **+30 bps** and
  the 240-bar trailing return is at least **−20 bps** — the short trend
  is up and the 4-hour trend is not in a deep fall.
- **Exit** when the 60-bar trailing return falls to **−40 bps**, or when
  the close drops **0.8%** below the highest close since entry
  (trailing stop).
- One position at a time, 100% of cash on entry, whole position on exit,
  `max_slippage_bps` 200.

A full-size round trip costs roughly 30–40 bps, so a trade has to catch
a move clearly bigger than that. One-minute BTC noise is only ~7 bps
per bar, so the signal comes from the hour-scale trend, not the
minute-scale wiggle. The bot trades rarely — a few round trips a day —
and only when the trend is actually there. All decisions use integer
basis points on closes already sent, so two runs on the same bars
produce identical orders.

## Local dev-window result

Graded on the kit's frozen 24-hour dev window (1,440 bars):

- **Net PnL: +$7.93** (dev gate: > $0 — passes)
- **Trades: 4** (2 round trips)
- **Max drawdown: 1.00%** (guardrail: ≤ 25%)
- Deterministic: two runs produce byte-identical action logs.

## Files

- `main.py` — the bot (entrypoint)
- `LICENSE` — MIT
- `.makefun/owner.json` — claim file naming the payout wallet
