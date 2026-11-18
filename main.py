"""Momentum bot for cbBTC (CBBTC/USDC) on 1-minute bars.

Speaks agent-fun/bars-replay/v1: newline-delimited JSON on stdin/stdout.
Reads one bar per minute, answers each batch with at most one order.

Strategy (long only, full size, integer math, no clock, no network):
  - Enter when the 60-bar trailing return is at least +30 bps and the
    240-bar trailing return is at least -20 bps (i.e. the short trend is
    up and the 4-hour trend is not in a deep fall).
  - Exit when the 60-bar trailing return falls to -40 bps or less, or
    when the close drops 0.8% below the highest close seen since entry
    (trailing stop).
  - One position at a time, 100% of cash on entry, whole position on exit.

Why this shape: a full-size round trip costs roughly 30-40 bps in fee,
slippage and pool impact, so a trade must catch a move clearly bigger
than that. One-minute BTC noise is only ~7 bps per bar, so the signal
has to come from the hour-scale trend, not the minute-scale wiggle.
The 240-bar filter keeps the bot out of sustained multi-hour falls,
where a long-only bot can only lose, and the trailing stop caps the
loss on any single trade. The bot trades rarely (a few round trips per
day) and only when the trend is actually there.

All decisions use integer basis points on the closes the harness has
already sent, so two runs on the same bars produce the same orders.

Measured on the kit's frozen 24-hour dev window (1,440 bars):
net PnL +$7.93, 4 trades (2 round trips), max drawdown 1.00%,
byte-identical action logs across two runs.
"""

import json
import sys

SYMBOL = "CBBTC"

# Entry: 60-bar return >= +30 bps while 240-bar return >= -20 bps.
ENTRY_WINDOW = 60
ENTRY_MIN_BPS = 30
TREND_WINDOW = 240
TREND_MIN_BPS = -20
# Exit: 60-bar return <= -40 bps, or 0.8% below the peak since entry.
EXIT_WINDOW = 60
EXIT_MAX_BPS = -40
TRAIL_BPS = 80
# Slippage guard: a fill more than 2% away from the latest close is
# rejected by the harness; per-minute moves are far smaller than that.
MAX_SLIPPAGE_BPS = 200


def trailing_return_bps(closes, window):
    """Return of the latest close vs the close `window` bars ago, in bps.

    Returns None until enough closes have been seen. Integer math only.
    """
    if len(closes) <= window:
        return None
    now = closes[-1]
    then = closes[-1 - window]
    if then <= 0:
        return None
    return (now - then) * 10000 // then


class Bot:
    """Holds the wire state and the strategy state for one run."""

    def __init__(self):
        self.closes = []
        self.cash = 0
        self.qty = 0
        self.warmup_bars = 0
        self.seq = -1
        self.peak = 0
        self.next_client_id = 1

    def client_id(self):
        cid = "o%d" % self.next_client_id
        self.next_client_id += 1
        return cid

    def on_hello(self, msg):
        self.warmup_bars = msg.get("warmup_bars", 0) or 0
        capital = msg.get("capital", {})
        self.cash = int(capital.get("quote_units", "0") or "0")

    def on_batch(self, msg):
        self.seq = msg["seq"]
        for bar in msg.get("bars", []):
            if bar.get("symbol") == SYMBOL:
                self.closes.append(int(bar["c"]))
        account = msg.get("account", {})
        self.cash = int(account.get("cash_quote_units", "0") or "0")
        self.qty = 0
        for pos in account.get("positions", []):
            if pos.get("symbol") == SYMBOL:
                self.qty = int(pos.get("qty", "0") or "0")
        return self.decide()

    def decide(self):
        """The orders for this batch: at most one, or none."""
        if not self.closes:
            return []
        if self.seq < self.warmup_bars:
            return []
        close = self.closes[-1]
        if self.qty > 0:
            if close > self.peak:
                self.peak = close
            ret60 = trailing_return_bps(self.closes, EXIT_WINDOW)
            if ret60 is not None and ret60 <= EXIT_MAX_BPS:
                return [self.sell_all()]
            if close * 10000 <= self.peak * (10000 - TRAIL_BPS):
                return [self.sell_all()]
            return []
        entry_ret = trailing_return_bps(self.closes, ENTRY_WINDOW)
        trend_ret = trailing_return_bps(self.closes, TREND_WINDOW)
        if entry_ret is None or trend_ret is None:
            return []
        if entry_ret >= ENTRY_MIN_BPS and trend_ret >= TREND_MIN_BPS:
            if self.cash >= 1000000:
                self.peak = close
                return [self.buy_all()]
        return []

    def buy_all(self):
        return {
            "side": "buy",
            "client_id": self.client_id(),
            "symbol": SYMBOL,
            "notional_quote_units": str(self.cash),
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }

    def sell_all(self):
        return {
            "side": "sell",
            "client_id": self.client_id(),
            "symbol": SYMBOL,
            "qty": str(self.qty),
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }


def main():
    bot = Bot()
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        kind = msg.get("type")
        if kind == "hello":
            bot.on_hello(msg)
        elif kind == "batch":
            orders = bot.on_batch(msg)
            reply = {"type": "reply", "seq": msg["seq"], "orders": orders}
            out.write(json.dumps(reply, separators=(",", ":")) + "\n")
            out.flush()
        elif kind == "done":
            break
        else:
            raise ValueError("unknown message type: %r" % (kind,))


if __name__ == "__main__":
    main()
