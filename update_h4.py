import os
import json
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SPREADSHEET_ID = "18eauVO0BD8RUNMPubv04OMRDtnt4SZrKWOSObP8Ju00"   # Ganti dengan ID sebenar
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURCHF", "GBPCHF", "CADJPY",
    "AUDCAD", "AUDCHF", "AUDNZD", "CADCHF", "EURAUD", "EURCAD", "EURNZD",
    "GBPAUD", "GBPCAD", "CHFJPY", "GBPNZD", "NZDCAD", "NZDCHF", "NZDJPY",
    "XAUUSD"
]
INTERVAL = "4h"
LIMIT = 100   # cukup untuk ambil candle terbaru

def get_gspread_client():
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds_dict = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def fetch_h4(symbol: str) -> pd.DataFrame:
    url = f"https://biquote.io/api/{symbol}/ohlc"
    params = {"interval": INTERVAL, "limit": LIMIT}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    df = pd.DataFrame(data.get("bars", []))
    if df.empty:
        return df
    df = df[df["isOpen"] == False]  # hanya candle yang sudah close
    df["Date"] = pd.to_datetime(df["openTime"]).dt.strftime("%Y-%m-%d %H:%M")
    df = df[["Date", "open", "high", "low", "close"]].rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}
    )
    return df.sort_values("Date").reset_index(drop=True)

def get_last_date(ws):
    """Ambil tarikh terakhir dari sheet (jika ada)"""
    try:
        values = ws.get_all_values()
        if len(values) <= 1:  # hanya header atau kosong
            return None
        last_date_str = values[-1][0]  # anggap column A = Date
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

    # Append row baru
    rows = df.values.tolist()
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    return len(rows)

def main():
    print("=== Start Append New H4 Candles ===")
    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_ID)

    for symbol in PAIRS:
        try:
            print(f"→ {symbol}")
            ws = sh.worksheet(symbol)
            last_date = get_last_date(ws)
            if last_date:
                print(f"  Last date: {last_date}")
            else:
                print("  Sheet kosong / tiada data lama")

            df = fetch_h4(symbol)
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
