#!/usr/bin/env python3
"""抓取 0050 與美股歷史資料，輸出 data.js（供 index.html 讀取）。
用法：python update_data.py      （只需 Python 3，無需安裝套件）
"""
import json, urllib.request, datetime as dt
from collections import defaultdict

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{}?range={}&interval={}"

def chart(sym, rng, itv):
    url = BASE.format(urllib.request.quote(sym), rng, itv)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        res = json.load(r)["chart"]["result"][0]
    off = res["meta"].get("gmtoffset", 0)
    q = res["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(res.get("timestamp") or []):
        if q["close"][i] is None:
            continue
        local = dt.datetime.fromtimestamp(t + off, dt.timezone.utc).replace(tzinfo=None)
        rows.append((local, q["open"][i], q["high"][i], q["low"][i], q["close"][i]))
    return rows

def daily(sym):
    return [{"d": r[0].strftime("%Y-%m-%d"), "o": r[1], "h": r[2], "l": r[3], "c": r[4]}
            for r in chart(sym, "2y", "1d")]

out = {"updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M")}
out["tw"] = daily("0050.TW")
out["us"] = {k: [{"d": x["d"], "c": x["c"]} for x in daily(s)]
             for k, s in {"spx": "^GSPC", "ixic": "^IXIC", "sox": "^SOX", "tsm": "TSM"}.items()}

# 補資料：Yahoo 偶爾缺最近一天，改用證交所（TWSE）官方日成交資料補上比 Yahoo 更新的日期
def twse_month(ym):
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=%s01&stockNo=0050" % ym
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        j = json.load(r)
    rows = []
    for x in j.get("data", []):
        try:
            y, m, d = x[0].split("/")
            f = lambda v: float(v.replace(",", ""))
            rows.append({"d": "%d-%s-%s" % (int(y) + 1911, m, d),
                         "o": f(x[3]), "h": f(x[4]), "l": f(x[5]), "c": f(x[6])})
        except (ValueError, IndexError):
            pass  # 無成交時為 "--"
    return rows

try:
    today = dt.date.today()
    prev_month = today.replace(day=1) - dt.timedelta(days=1)
    have = {x["d"] for x in out["tw"]}
    added = []
    for ym in (prev_month.strftime("%Y%m"), today.strftime("%Y%m")):
        for row in twse_month(ym):
            if row["d"] not in have:          # Yahoo 沒有的交易日（含中間缺的）都補上
                out["tw"].append(row); have.add(row["d"]); added.append(row["d"])
    out["tw"].sort(key=lambda x: x["d"])
    if added:
        print("Yahoo 缺少、已由證交所補上：", ", ".join(sorted(added)))
except Exception as e:
    print("證交所補資料失敗（不影響其他功能）：", e)

# 盤中執行時，Yahoo 會給「今天尚未收盤」的暫時 K 棒；收盤前先剔除，避免當成收盤價計算
tw_now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=8)
if out["tw"] and out["tw"][-1]["d"] == tw_now.strftime("%Y-%m-%d") and tw_now.hour * 60 + tw_now.minute < 13 * 60 + 40:
    print("台股尚未收盤，略過今天的暫時資料：", out["tw"][-1]["d"])
    out["tw"].pop()

# 盤中高低點出現時段（15 分 K，最近約 60 天）
try:
    prev, gap = None, {}
    for x in out["tw"]:
        if prev:
            gap[x["d"]] = x["o"] / prev - 1
        prev = x["c"]
    days = defaultdict(list)
    for r in chart("0050.TW", "60d", "15m"):
        days[r[0].strftime("%Y-%m-%d")].append(r)
    hist = {k: {"low": [0] * 9, "high": [0] * 9, "n": 0} for k in ("dn", "flat", "up")}
    for d, bars in days.items():
        if d not in gap or len(bars) < 10:
            continue
        reg = "dn" if gap[d] < -0.004 else "up" if gap[d] > 0.004 else "flat"
        b = lambda r: min(8, max(0, (r[0].hour * 60 + r[0].minute - 540) // 30))
        hist[reg]["low"][b(min(bars, key=lambda r: r[3]))] += 1
        hist[reg]["high"][b(max(bars, key=lambda r: r[2]))] += 1
        hist[reg]["n"] += 1
    out["intraday"] = hist
except Exception as e:
    print("盤中資料取得失敗（不影響其他功能）：", e)
    out["intraday"] = None

with open("data.js", "w", encoding="utf-8") as f:
    f.write("window.DATA = " + json.dumps(out, ensure_ascii=False) + ";")
print("完成：data.js，0050 共", len(out["tw"]), "筆，最新", out["tw"][-1]["d"])
print("0050 最近 6 個交易日：", ", ".join(x["d"][5:] for x in out["tw"][-6:]))
print("美股最近 3 個交易日：", ", ".join(x["d"][5:] for x in out["us"]["spx"][-3:]))
