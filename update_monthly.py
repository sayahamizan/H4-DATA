import os
import json
import time
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ============ CONFIG ============
SPREADSHEET_ID = "1pBlgoPGAeTdllrmeSp1QW4bGR3FsD2DfomKG0rS4fHc"   # Ganti
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURCHF", "GBPCHF", "CADJPY",
    "AUDCAD", "AUDCHF", "AUDNZD", "CADCHF", "EURAUD", "EURCAD", "EURNZD",
    "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD", "NZDCAD", "NZDCHF", "NZDJPY",
    "XAUUSD"
]
INTERVAL = "1month"
OUTPUTSIZE = 50
BATCH_SIZE = 5
SLEEP_BETWEEN_BATCH = 60
# ================================

def get_gspread_client():
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds_dict = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def to_twelvedata_symbol(symbol: str) -> str:
    if len(symbol) == 6:
        return f"{symbol[:3]}/{symbol[3:]}"
    return symbol

def fetch_monthly(symbol: str, api_key: str) -> pd.DataFrame:
    td_symbol = to_twelvedata_symbol(symbol)
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": td_symbol,
        "interval": INTERVAL,
        "outputsize": OUTPUTSIZE,
        "apikey": api_key,
        "format": "JSON",
        "order": "ASC"
    }
    r = requests.get(url, params=params, timeout=30)

    if r.status_code == 404:
        print(f"  404 Not Found for {td_symbol}")
        return pd.DataFrame()
    if r.status_code == 429:
        print("  Rate limit / credit habis")
        return pd.DataFrame()

    r.raise_for_status()
    data = r.json()

    if data.get("status") == "error":
        print(f"  API Error: {data.get('message')}")
        return pd.DataFrame()

    values = data.get("values", [])
    if not values:
        return pd.DataFrame()

    df = pd.DataFrame(values)
    df = df.rename(columns={
        "datetime": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close"
    })
    df = df[["Date", "Open", "High", "Low", "Close"]]
    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    return df.sort_values("Date").reset_index(drop=True)

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
    print("=== Start Append New Monthly Candles (Twelve Data) ===")
    api_key = os.environ["TWELVEDATA_API_KEY"]
    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_ID)

    total = len(PAIRS)
    for batch_start in range(0, total, BATCH_SIZE):
        batch = PAIRS[batch_start:batch_start + BATCH_SIZE]
        print(f"\n--- Batch {batch_start // BATCH_SIZE + 1} ({len(batch)} pairs) ---")

        for symbol in batch:
            try:
                print(f"→ {symbol}")
                ws = sh.worksheet(symbol)
                last_date = get_last_date(ws)
                if last_date:
                    print(f"  Last date: {last_date.date()}")
                else:
                    print("  Sheet kosong / tiada data lama")

                df = fetch_monthly(symbol, api_key)
                if df.empty:
                    print("  Tiada data dari API")
                    continue

                added = append_new_candles(ws, df, last_date)
                print(f"  ✓ Added {added} new monthly candle(s)")

            except gspread.WorksheetNotFound:
                print(f"  ✗ Tab '{symbol}' tidak wujud")
            except Exception as e:
                print(f"  ✗ Error: {e}")

        if batch_start + BATCH_SIZE < total:
            print(f"\nMenunggu {SLEEP_BETWEEN_BATCH} saat sebelum batch seterusnya...")
            time.sleep(SLEEP_BETWEEN_BATCH)

    print("\n=== Done ===")

if __name__ == "__main__":
    main()
