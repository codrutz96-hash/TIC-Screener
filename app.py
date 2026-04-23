import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Pattern Screener", layout="wide")

# --- FUNCȚIE OBȚINERE TICKERE ---
@st.cache_data
def get_tickers(market):
    if market == "S&P 500":
        return pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]['Symbol'].tolist()
    elif market == "NASDAQ 100":
        return pd.read_html('https://en.wikipedia.org/wiki/Nasdaq-100')[4]['Ticker'].tolist()
    elif market == "Dow Jones":
        return pd.read_html('https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average')[1]['Symbol'].tolist()
    return []

# --- LOGICA DE DETECȚIE PATTERN ---
def scan_pattern(df, ticker):
    if len(df) < 4:
        return None
    
    # Ultimele 4 lumânări
    # c1 = acum 3 zile, c2 = acum 2 zile, c3 = ieri, c4 = azi (ultima inchisa)
    c1 = df.iloc[-4]
    c2 = df.iloc[-3]
    c3 = df.iloc[-2]
    c4 = df.iloc[-1]

    # Condiții:
    # 1. C1 Roșie (Close < Open)
    # 2. C2 Roșie (Close < Open)
    # 3. C3 Verde (Close > Open)
    # 4. C4 Verde (Close > Open)
    # 5. C4 Close > C1 High
    
    is_red1 = c1['Close'] < c1['Open']
    is_red2 = c2['Close'] < c2['Open']
    is_green3 = c3['Close'] > c3['Open']
    is_green4 = c4['Close'] > c4['Open']
    breakout = c4['Close'] > c1['High']

    if is_red1 and is_red2 and is_green3 and is_green4 and breakout:
        return {
            "Ticker": ticker,
            "Pret": round(c4['Close'], 2),
            "High C1": round(c1['High'], 2),
            "Schimbare %": round(((c4['Close'] / c4['Open']) - 1) * 100, 2)
        }
    return None

# --- UI STREAMLIT ---
st.title("🕯️ 4-Candle Pattern Scanner")
st.write("Cauta pattern-ul: **Roșu, Roșu, Verde, Verde (Breakout peste High C1)**")

with st.sidebar:
    market_choice = st.selectbox("Alege Index-ul", ["S&P 500", "NASDAQ 100", "Dow Jones"])
    st.info("Sfat: Scanarea durează ~30 secunde pentru S&P 500.")

if st.button("Lansează Scanarea"):
    tickers = get_tickers(market_choice)
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Descarcam datele in grupuri (Batch) pentru viteza maxima
    batch_size = 50
    for i in range(0, len(tickers), batch_size):
        current_batch = tickers[i : i + batch_size]
        status_text.text(f"Se analizează grupul {i//batch_size + 1}...")
        
        # Descarcam datele pe ultimele 10 zile pentru a avea context suficient
        data = yf.download(current_batch, period="10d", interval="1d", group_by='ticker', progress=False)
        
        for ticker in current_batch:
            try:
                # Verificam daca avem date pentru ticker-ul respectiv (yf.download poate returna NaN)
                if ticker in data.columns.levels[0]:
                    df_ticker = data[ticker].dropna()
                    match = scan_pattern(df_ticker, ticker)
                    if match:
                        results.append(match)
            except:
                continue
        
        progress_bar.progress((i + batch_size) / len(tickers) if (i + batch_size) < len(tickers) else 1.0)

    status_text.success("Scanare completă!")

    if results:
        st.balloons()
        st.subheader(f"✅ Am găsit {len(results)} acțiuni care respectă tiparul:")
        final_df = pd.DataFrame(results)
        st.table(final_df) # Tabel curat
    else:
        st.warning("Nicio acțiune nu îndeplinește criteriile în acest moment.")
