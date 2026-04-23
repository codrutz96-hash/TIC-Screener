import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io

# Configurare pagină
st.set_page_config(page_title="Master Pro v7.0 Screener", layout="wide")

# --- FUNCȚII SUPORT ---
@st.cache_data
def get_tickers(market):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
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
    except Exception as e:
        st.error(f"Eroare la preluarea listei: {e}")
        return []

def get_ftfc_status(ticker):
    """Calculează continuitatea pe Monthly și Weekly"""
    try:
        # Preluăm date pentru direcția lunii și săptămânii
        m_data = yf.download(ticker, period="6mo", interval="1mo", progress=False)
        w_data = yf.download(ticker, period="3mo", interval="1wk", progress=False)
        
        if m_data.empty or w_data.empty: return 0, 0
        
        # Eliminăm MultiIndex dacă există
        if isinstance(m_data.columns, pd.MultiIndex): m_data.columns = m_data.columns.get_level_values(0)
        if isinstance(w_data.columns, pd.MultiIndex): w_data.columns = w_data.columns.get_level_values(0)

        m_last = m_data.iloc[-1]
        w_last = w_data.iloc[-1]
        
        m_dir = 1 if m_last['Close'] > m_last['Open'] else -1
        w_dir = 1 if w_last['Close'] > w_last['Open'] else -1
        
        return m_dir, w_dir
    except:
        return 0, 0

# --- LOGICA DE SEMNAL (PORTARE PINE SCRIPT) ---
def scan_logic(df, ticker, direction, use_ftfc):
    if len(df) < 25: return None
    
    # Calcul EMA 20 nativ in Pandas (fara pandas_ta)
    df['ema20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # Ultimele lumânări (index -1 este prezentul)
    c0 = df.iloc[-1]
    c1 = df.iloc[-2]
    c2 = df.iloc[-3]
    c3 = df.iloc[-4]
    
    is_red = lambda row: row['Close'] < row['Open']
    is_green = lambda row: row['Close'] > row['Open']

    signal = False
    
    if direction == "LONG":
        # Pattern: Roșu, Roșu, Verde, Verde
        pattern = is_red(c3) and is_red(c2) and is_green(c1) and is_green(c0)
        # Break confirmed: Close[0] > Open[3]
        breakout = c0['Close'] > c3['Open']
        # Primer Filter: high[1] < EMA20 sau high[2] < EMA20
        primer = c1['High'] < c1['ema20'] or c2['High'] < c2['ema20']
        
        if pattern and breakout and primer:
            signal = True

    else: # SHORT
        # Pattern: Verde, Verde, Roșu, Roșu
        pattern = is_green(c3) and is_green(c2) and is_red(c1) and is_red(c0)
        # Break confirmed: Close[0] < Open[3]
        breakout = c0['Close'] < c3['Open']
        # Primer Filter: low[1] > EMA20 sau low[2] > EMA20
        primer = c1['Low'] > c1['ema20'] or c2['Low'] > c2['ema20']
        
        if pattern and breakout and primer:
            signal = True

    if signal:
        ftfc_status = "Nespecificat"
        if use_ftfc:
            m_dir, w_dir = get_ftfc_status(ticker)
            d_dir = 1 if is_green(c0) else -1
            
            # Verificăm continuitatea (Toate 3 în aceeași direcție)
            if direction == "LONG":
                if not (m_dir == 1 and w_dir == 1 and d_dir == 1): return None
            else: # SHORT
                if not (m_dir == -1 and w_dir == -1 and d_dir == -1): return None
            ftfc_status = "✅ FTFC Activ"

        return {
            "Ticker": ticker,
            "Preț": round(float(c0['Close']), 2),
            "Direcție": direction,
            "FTFC": ftfc_status
        }
    return None

# --- INTERFAȚA STREAMLIT ---
st.title("🛡️ Master Pro v7.0 - Strategy Screener")
st.markdown("Bazat pe logica: **4-Candle Color Reversal + EMA Filter + FTFC**")

with st.sidebar:
    st.header("Parametri Scanare")
    mode = st.radio("Caută Semnale:", ["LONG", "SHORT"])
    tf_base = st.selectbox("Timeframe Principal:", ["1d", "1wk", "4h", "1h"], index=0)
    market = st.selectbox("Piața:", ["S&P 500", "NASDAQ 100", "Dow Jones"])
    
    st.divider()
    apply_ftfc = st.checkbox("Activează FTFC (M + W + D)", value=True)
    limit = st.slider("Limită tickere:", 10, 500, 100)

if st.button(f"Lansează Scanarea pentru {mode}"):
    tickers = get_tickers(market)
    if not tickers:
        st.error("Nu s-a putut încărca lista de tickere.")
    else:
        tickers = tickers[:limit]
        results = []
        
        prog = st.progress(0)
        status = st.empty()
        
        # Ajustare perioadă în funcție de timeframe
        period = "2y" if "d" in tf_base or "w" in tf_base else "60d"
        
        for i, t in enumerate(tickers):
            t = t.replace('.', '-')
            status.text(f"Se analizează {t} ({i+1}/{len(tickers)})...")
            
            try:
                # --- BLOCUL DE DESCARCARE OPTIMIZAT ---
                data = yf.download(t, period=period, interval=tf_base, progress=False)
                
                if data is None or data.empty or len(data) < 25:
                    continue

                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)

                match = scan_logic(data, t, mode, apply_ftfc)
                if match:
                    results.append(match)
                # --------------------------------------
            except Exception as e:
                print(f"Eroare la {t}: {e}")
                continue
            
            prog.progress((i + 1) / len(tickers))
        
        status.empty()
        if results:
            st.balloons()
            st.subheader(f"🎯 Semnale {mode} Găsite:")
            st.table(pd.DataFrame(results))
        else:
            st.info(f"Niciun semnal {mode} nu a fost găsit în acest moment.")
