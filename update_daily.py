import os
import json
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ============ CONFIG ============
SPREADSHEET_ID = "1s5NFZLv6JVF0sV-JlcKN4htsKRIzlqh6D7nKZ9UDDO0"   # Ganti dengan ID spreadsheet Daily
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURCHF", "GBPCHF", "CADJPY",
    "AUDCAD", "AUDCHF", "AUDNZD", "CADCHF", "EURAUD", "EURCAD", "EURNZD",
    "GBPAUD", "GBPCAD", "CHFJPY", "GBPNZD", "NZDCAD", "NZDCHF", "NZDJPY",
    "XAUUSD"
]
INTERVAL = "1d"
LIMIT = 100
# ================================

def get_gspread_client():
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds_dict = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def fetch_daily(symbol: str) -> pd.DataFrame:
    url = f"https://biquote.io/api/{symbol}/ohlc"
    params = {"interval": INTERVAL, "limit": LIMIT}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    df = pd.DataFrame(data.get("bars", []))
    if df.empty:
        return df
    df = df[df["isOpen"] == False]
    df["Date"] = pd.to_datetime(df["openTime"]).dt.strftime("%Y-%m-%d")
    df = df[["Date", "open", "high", "low", "close"]].rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}
    )
    return df.sort_values("Date").reset_index(drop=True)

def get_last_date(ws):
    try:
        values = ws.get_all_values()
        if len(values) <= 1:
            return None
        last_date_str = values[-1][0]
        return pd.to_datetime(last_date_str)
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
    print("=== Start Append New Daily Candles ===")
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

            df = fetch_daily(symbol)
            if df.empty:
                print("  Tiada data dari API")
                continue

            added = append_new_candles(ws, df, last_date)
            print(f"  ✓ Added {added} new candle(s)")

        except gspread.WorksheetNotFound:
            print(f"  ✗ Tab '{symbol}' tidak wujud")
        except Exception as e:
            print(f"  ✗ Error: {e}")

    print("=== Done ===")

if __name__ == "__main__":
    main()
