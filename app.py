import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import io

st.set_page_config(page_title="Master Pro v7.0 Screener", layout="wide")

# --- FUNCȚII SUPORT ---
@st.cache_data
def get_tickers(market):
    headers = {"User-Agent": "Mozilla/5.0"}
    urls = {
        "S&P 500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "NASDAQ 100": "https://en.wikipedia.org/wiki/Nasdaq-100",
        "Dow Jones": "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
    }
    try:
        res = requests.get(urls[market], headers=headers)
        idx = 0 if market == "S&P 500" else (4 if market == "NASDAQ 100" else 1)
        df = pd.read_html(io.StringIO(res.text))[idx]
        col = 'Symbol' if 'Symbol' in df.columns else 'Ticker'
        return df[col].tolist()
    except: return []

def get_ftfc_status(ticker):
    """Calculează continuitatea pe D, W, M"""
    try:
        # Luăm date pentru Monthly și Weekly
        d_m = yf.download(ticker, period="6mo", interval="1mo", progress=False).iloc[-1]
        d_w = yf.download(ticker, period="3mo", interval="1wk", progress=False).iloc[-1]
        
        m_dir = 1 if d_m['Close'] > d_m['Open'] else -1
        w_dir = 1 if d_w['Close'] > d_w['Open'] else -1
        
        return m_dir, w_dir
    except: return 0, 0

# --- LOGICA DE SEMNAL (PINE SCRIPT PORT) ---
def scan_logic(df, ticker, direction, use_ftfc):
    if len(df) < 25: return None
    
    # Calcul EMA 20 (Filter MA)
    df['ema20'] = ta.ema(df['Close'], length=20)
    
    # Ultimele lumânări
    c = df.iloc[-1]   # c0
    c1 = df.iloc[-2]  
    c2 = df.iloc[-3]
    c3 = df.iloc[-4]  # c3 în Pine
    
    is_red = lambda row: row['Close'] < row['Open']
    is_green = lambda row: row['Close'] > row['Open']

    signal = False
    
    if direction == "LONG":
        # Logica Pine: is_red(3) and is_red(2) and is_green(1) and is_green(0)
        pattern = is_red(c3) and is_red(c2) and is_green(c1) and is_green(c)
        breakout = c['Close'] > c3['Open'] # Close[0] > Open[3]
        # Primer Filter: high[1] < ma or high[2] < ma
        primer = c1['High'] < c1['ema20'] or c2['High'] < c2['ema20']
        
        if pattern and breakout and primer:
            signal = True

    else: # SHORT
        pattern = is_green(c3) and is_green(c2) and is_red(c1) and is_red(c)
        breakout = c['Close'] < c3['Open'] # Close[0] < Open[3]
        primer = c1['Low'] > c1['ema20'] or c2['Low'] > c2['ema20']
        
        if pattern and breakout and primer:
            signal = True

    if signal:
        ftfc_text = "N/A"
        if use_ftfc:
            m_dir, w_dir = get_ftfc_status(ticker)
            d_dir = 1 if is_green(c) else -1
            
            # Verificăm dacă D, W și M sunt în aceeași direcție
            if direction == "LONG" and not (m_dir == 1 and w_dir == 1 and d_dir == 1):
                return None
            if direction == "SHORT" and not (m_dir == -1 and w_dir == -1 and d_dir == -1):
                return None
            ftfc_text = "✅ Full Continuity"

        return {
            "Ticker": ticker,
            "Preț": round(c['Close'], 2),
            "FTFC": ftfc_text,
            "Timeframe": "Selected"
        }
    return None

# --- INTERFAȚA ---
st.title("🛡️ Master Pro v7.0 Stock Screener")

with st.sidebar:
    st.header("Configurare Semnal")
    mode = st.radio("Direcție", ["LONG", "SHORT"])
    tf_base = st.selectbox("Timeframe Principal", ["1d", "1wk", "4h", "1h"])
    market = st.selectbox("Piața", ["S&P 500", "NASDAQ 100", "Dow Jones"])
    
    st.divider()
    apply_ftfc = st.checkbox("Activează FTFC Filter (D+W+M)", value=True)
    limit = st.slider("Nr. Companii de scanat", 10, 500, 50)

if st.button(f"Scanează {market} pentru {mode}"):
    tickers = get_tickers(market)[:limit]
    results = []
    
    prog = st.progress(0)
    status = st.empty()
    
    for i, t in enumerate(tickers):
        t = t.replace('.', '-')
        status.text(f"Analizăm {t}...")
        
        # Luăm date în funcție de timeframe-ul ales
        period = "60d" if "h" in tf_base else "2y"
        df = yf.download(t, period=period, interval=tf_base, progress=False)
        
        if not df.empty:
            match = scan_logic(df, t, mode, apply_ftfc)
            if match:
                results.append(match)
        
        prog.progress((i + 1) / len(tickers))
    
    status.empty()
    if results:
        st.success(f"Am găsit {len(results)} oportunități!")
        st.table(pd.DataFrame(results))
    else:
        st.warning("Niciun semnal găsit conform criteriilor.")
