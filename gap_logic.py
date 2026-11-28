"""Gap boundaries and full-fill events based on candle bodies."""
GAP_RULE_VERSION = 'body-v1'


def detect_body_gaps(candles):
    bounds = [(min(bar['open'], bar['close']), max(bar['open'], bar['close'])) for bar in candles]
    future_lows = [float('inf')] * (len(bounds) + 1)
    future_highs = [float('-inf')] * (len(bounds) + 1)
    for i in range(len(bounds) - 1, -1, -1):
        future_lows[i] = min(bounds[i][0], future_lows[i + 1])
        future_highs[i] = max(bounds[i][1], future_highs[i + 1])
    bull, bear = [], []
    for i in range(1, len(candles)):
        low, high = bounds[i]
        previous_low, previous_high = bounds[i - 1]
        if low > previous_high * 1.001:
            closed = future_lows[i + 1] <= previous_high
            if not closed:
                bull.append(dict(date=candles[i]['date'], idx=i, bottom=previous_high, top=low))
        if high < previous_low * .999:
            closed = future_highs[i + 1] >= previous_low
            if not closed:
                bear.append(dict(date=candles[i]['date'], idx=i, bottom=high, top=previous_low))
    return bull, bear
