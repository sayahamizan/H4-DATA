import os
import json
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ============ CONFIG ============
SPREADSHEET_ID = "18eauVO0BD8RUNMPubv04OMRDtnt4SZrKWOSObP8Ju00"   # ambil dari URL Sheet
# Senarai pair (nama tab mesti sama dengan symbol)
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURCHF", "GBPCHF", "CADJPY",
    "AUDCAD", "AUDCHF", "AUDNZD", "CADCHF", "EURAUD", "EURCAD", "EURNZD",
    "GBPAUD", "GBPCAD", "CHFJPY", "GBPNZD", "NZDCAD", "NZDCHF", "NZDJPY",
    "XAUUSD"
]
INTERVAL = "4h"
LIMIT = 1000          # max ~1000 bar
# =================================

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
    df = pd.DataFrame(data["bars"])
    if df.empty:
        return df
    df = df[df["isOpen"] == False]          # hanya candle yang sudah close
    df["Date"] = pd.to_datetime(df["openTime"]).dt.strftime("%Y-%m-%d %H:%M")
    df = df[["Date", "open", "high", "low", "close"]].rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}
    )
    df = df.sort_values("Date").reset_index(drop=True)
    return df

def update_sheet(gc, symbol: str, df: pd.DataFrame):
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet(symbol)
    except gspread.WorksheetNotFound:
        print(f"Tab {symbol} tidak wujud, skip.")
        return

    # Clear data lama (keep header)
    ws.clear()
    # Tulis header + data
    values = [df.columns.tolist()] + df.values.tolist()
    ws.update(values, "A1", value_input_option="USER_ENTERED")
    print(f"{symbol}: updated {len(df)} rows")

def main():
    gc = get_gspread_client()
    for symbol in PAIRS:
        try:
            df = fetch_h4(symbol)
            if df.empty:
                print(f"{symbol}: tiada data")
                continue
            update_sheet(gc, symbol, df)
        except Exception as e:
            print(f"Error {symbol}: {e}")

if __name__ == "__main__":
    main()
