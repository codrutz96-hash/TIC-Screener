import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io  # <--- Linie nouă

st.set_page_config(page_title="Pattern Screener Pro", layout="wide")

# --- FUNCȚIE OBȚINERE TICKERE (VARIANTA REPARATĂ) ---
@st.cache_data
def get_tickers(market):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        if market == "S&P 500":
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            response = requests.get(url, headers=headers)
            # Folosim io.StringIO pentru a evita eroarea de citire
            df = pd.read_html(io.StringIO(response.text))[0]
            return df['Symbol'].tolist()
            
        elif market == "NASDAQ 100":
            url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
            response = requests.get(url, headers=headers)
            df = pd.read_html(io.StringIO(response.text))[4]
            col = 'Ticker' if 'Ticker' in df.columns else 'Symbol'
            return df[col].tolist()
            
        elif market == "Dow Jones":
            url = 'https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average'
            response = requests.get(url, headers=headers)
            df = pd.read_html(io.StringIO(response.text))[1]
            return df['Symbol'].tolist()
    except Exception as e:
        st.error(f"Eroare la preluarea listei {market}: {e}")
        return []
    return []

# --- LOGICA DE DETECȚIE PATTERN (CERINȚA TA) ---
def scan_pattern(df, ticker):
    if len(df) < 4:
        return None
    
    # Ultimele 4 lumânări: c1 (veche) -> c4 (cea mai recentă/azi)
    c1 = df.iloc[-4]
    c2 = df.iloc[-3]
    c3 = df.iloc[-2]
    c4 = df.iloc[-1]

    # 1. C1 Roșie (Close < Open)
    is_red1 = c1['Close'] < c1['Open']
    # 2. C2 Roșie (Close < Open)
    is_red2 = c2['Close'] < c2['Open']
    # 3. C3 Verde (Close > Open)
    is_green3 = c3['Close'] > c3['Open']
    # 4. C4 Verde (Close > Open)
    is_green4 = c4['Close'] > c4['Open']
    # 5. C4 Close > C1 High (Breakout)
    breakout = c4['Close'] > c1['High']

    if is_red1 and is_red2 and is_green3 and is_green4 and breakout:
        return {
            "Ticker": ticker,
            "Pret Actual": round(float(c4['Close']), 2),
            "High C1 (Barieră)": round(float(c1['High']), 2),
            "Evoluție Azi %": round(((float(c4['Close']) / float(c4['Open'])) - 1) * 100, 2)
        }
    return None

# --- UI STREAMLIT ---
st.title("🕯️ 4-Candle Reversal Screener")
st.markdown("Căutăm pattern-ul: :red[Roșu] → :red[Roșu] → :green[Verde] → :green[Verde (Breakout)]")

with st.sidebar:
    st.header("Setări")
    market_choice = st.selectbox("Alege Piața", ["S&P 500", "NASDAQ 100", "Dow Jones"])
    limit_scan = st.slider("Limită de scanare (pentru viteză)", 10, 500, 100)
    st.divider()
    st.write("Aplicația verifică dacă prețul actual a depășit maximul primei lumânări roșii din grup.")

if st.button("🚀 Lansează Scanarea"):
    tickers = get_tickers(market_choice)
    tickers = [t.replace('.', '-') for t in tickers] # Corecție pentru simboluri tip BRK.B
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Batch download pentru performanță
    batch_size = 30
    tickers_to_scan = tickers[:limit_scan]
    
    for i in range(0, len(tickers_to_scan), batch_size):
        batch = tickers_to_scan[i : i + batch_size]
        status_text.text(f"Analizăm {i} - {i+len(batch)} din {len(tickers_to_scan)}...")
        
        try:
            # Descărcăm ultimele 10 zile
            data = yf.download(batch, period="10d", interval="1d", group_by='ticker', progress=False)
            
            for ticker in batch:
                if len(batch) > 1:
                    df_ticker = data[ticker].dropna()
                else:
                    df_ticker = data.dropna()
                
                match = scan_pattern(df_ticker, ticker)
                if match:
                    results.append(match)
        except Exception as e:
            continue
            
        progress_bar.progress((i + len(batch)) / len(tickers_to_scan))

    status_text.success("Scanare finalizată!")

    if results:
        st.balloons()
        st.subheader(f"🎯 Rezultate Găsite ({len(results)})")
        st.table(pd.DataFrame(results))
    else:
        st.info("Nicio acțiune nu respectă pattern-ul în acest moment.")
