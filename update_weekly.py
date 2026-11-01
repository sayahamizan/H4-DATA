import os
import json
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ============ CONFIG ============
SPREADSHEET_ID = "1oL7IA8m3cKMeP3yyM6E8vwB4nl4rAZ_IjgLACxF7lFo"   # Ganti
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURCHF", "GBPCHF", "CADJPY",
    "AUDCAD", "AUDCHF", "AUDNZD", "CADCHF", "EURAUD", "EURCAD", "EURNZD",
    "GBPAUD", "GBPCAD", "CHFJPY", "GBPNZD", "NZDCAD", "NZDCHF", "NZDJPY",
    "XAUUSD"
]
LIMIT = 300   # cukup untuk beberapa bulan daily
# ================================

def get_gspread_client():
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds_dict = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def fetch_daily(symbol: str) -> pd.DataFrame:
    url = f"https://biquote.io/api/{symbol}/ohlc"
    params = {"interval": "1d", "limit": LIMIT}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    df = pd.DataFrame(data.get("bars", []))
    if df.empty:
        return df
    df = df[df["isOpen"] == False]
    df["Date"] = pd.to_datetime(df["openTime"])
    df = df.set_index("Date").sort_index()
    df = df[["open", "high", "low", "close"]]
    return df

def to_weekly(df_daily: pd.DataFrame) -> pd.DataFrame:
    """Resample Daily → Weekly (Isnin sebagai start week)"""
    if df_daily.empty:
        return df_daily
    weekly = df_daily.resample("W-MON", label="left", closed="left").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last"
    }).dropna()
    weekly = weekly.reset_index()
    weekly["Date"] = weekly["Date"].dt.strftime("%Y-%m-%d")
    weekly = weekly[["Date", "open", "high", "low", "close"]].rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}
    )
    return weekly

def get_last_date(ws):
    try:
        values = ws.get_all_values()
        if len(values) <= 1:
            return None
        return pd.to_datetime(values[-1][0])
    except Exception:
        return None

def append_new_candles(ws, df: pd.DataFrame, last_date):
    if df.empty:
        return 0
    if last_date is not None:
        df["Date_dt"] = pd.to_datetime(df["Date"])
        df = df[df["Date_dt"] > last_date].drop(columns=["Date_dt"])
    if df.empty:
        return 0
    ws.append_rows(df.values.tolist(), value_input_option="USER_ENTERED")
    return len(df)

def main():
    print("=== Start Append New Weekly Candles ===")
    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_ID)

    for symbol in PAIRS:
        try:
            print(f"→ {symbol}")
            ws = sh.worksheet(symbol)
            last_date = get_last_date(ws)
            if last_date:
                print(f"  Last date: {last_date.date()}")
            else:
                print("  Sheet kosong / tiada data lama")

            df_daily = fetch_daily(symbol)
            if df_daily.empty:
                print("  Tiada data daily")
                continue

            df_weekly = to_weekly(df_daily)
            added = append_new_candles(ws, df_weekly, last_date)
            print(f"  ✓ Added {added} new weekly candle(s)")

        except gspread.WorksheetNotFound:
            print(f"  ✗ Tab '{symbol}' tidak wujud")
        except Exception as e:
            print(f"  ✗ Error: {e}")

    print("=== Done ===")

if __name__ == "__main__":
    main()
