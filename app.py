import os
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
from datetime import datetime
# optional libraries
try:
    from alpha_vantage.timeseries import TimeSeries
    ALPHA_AVAILABLE = True
except Exception:
    ALPHA_AVAILABLE = False

# Optional TA library (if available)
try:
    import ta
    TA_AVAILABLE = True
except Exception:
    TA_AVAILABLE = False

st.set_page_config(page_title="Andamento Borse Mondiali", layout="wide")
st.title("Andamento borse mondiali — Dashboard interattiva")
st.markdown("Seleziona gli indici e l'intervallo temporale per visualizzare l'andamento.")

INDEX_TICKERS = {
    "S&P 500 (USA)": "^GSPC",
    "Dow Jones (USA)": "^DJI",
    "NASDAQ-100 (USA)": "^NDX",
    "FTSE 100 (UK)": "^FTSE",
    "FTSE MIB (Italia)": "^FTMIB",
    "DAX (Germania)": "^GDAXI",
    "CAC 40 (Francia)": "^FCHI",
    "Nikkei 225 (Giappone)": "^N225",
    "Hang Seng (HK)": "^HSI",
    "SSE Composite (Shanghai)": "000001.SS",
    "ASX 200 (Australia)": "^AXJO",
    "TSX (Canada)": "^GSPTSE"
}

st.sidebar.header("Impostazioni")
default = ["S&P 500 (USA)", "FTSE MIB (Italia)", "Nikkei 225 (Giappone)"]
selected_indices = st.sidebar.multiselect("Seleziona indici", list(INDEX_TICKERS.keys()), default=default)

period_map = {
    "1 Mese": "1mo",
    "3 Mesi": "3mo",
    "6 Mesi": "6mo",
    "1 Anno": "1y",
    "2 Anni": "2y",
    "5 Anni": "5y",
    "Max": "max"
}
period_choice = st.sidebar.selectbox("Intervallo temporale", list(period_map.keys()), index=3)
freq_choice = st.sidebar.selectbox("Frequenza", ["1d", "1wk", "1mo"])

# Alpha Vantage settings
use_av = st.sidebar.checkbox("Usa Alpha Vantage (intraday) se disponibile", value=False)
av_interval = st.sidebar.selectbox("Intervallo AlphaV (se usato)", ["1min","5min","15min","30min","60min"], index=1)

# Read API key securely: prefer Streamlit secrets, then env var
ALPHA_API_KEY = None
if "ALPHA_API_KEY" in st.secrets:
    ALPHA_API_KEY = st.secrets["ALPHA_API_KEY"]
else:
    ALPHA_API_KEY = os.environ.get("ALPHA_API_KEY", None)

if use_av and not ALPHA_AVAILABLE:
    st.warning("alpha_vantage non è installato; installerai dal requirements o disabilita Alpha Vantage.")
if use_av and not ALPHA_API_KEY:
    st.warning("Hai abilitato Alpha Vantage ma non è stata trovata una chiave API. Impostala in st.secrets o come variabile d'ambiente ALPHA_API_KEY.")

if not selected_indices:
    st.warning("Seleziona almeno un indice nel pannello a sinistra.")
    st.stop()

symbols = [INDEX_TICKERS[name] for name in selected_indices]
period = period_map[period_choice]

@st.cache_data(ttl=300)
def download_yf(symbols, period, interval):
    df = yf.download(symbols, period=period, interval=interval, group_by='ticker', threads=True, progress=False)
    return df

def download_alpha_intraday(symbol, interval="5min"):
    if not ALPHA_API_KEY:
        raise RuntimeError("ALPHA_API_KEY mancante")
    ts = TimeSeries(key=ALPHA_API_KEY, output_format='pandas')
    data, meta = ts.get_intraday(symbol=symbol, interval=interval, outputsize='compact')
    data = data.rename(columns={c: c.split('. ')[-1].capitalize() for c in data.columns})
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()
    return data

with st.spinner("Scaricamento dati…"):
    try:
        if use_av and ALPHA_AVAILABLE and ALPHA_API_KEY:
            # use AV for each selected index where symbol is supported (note: indices may not be supported; sometimes use ETF tickers)
            raw = {}
            for name, sym in zip(selected_indices, symbols):
                try:
                    raw[name] = download_alpha_intraday(sym, interval=av_interval)
                except Exception as e:
                    st.warning(f"AlphaV non ha fornito dati per {name} ({sym}): {e}. Verrà usato yfinance come fallback.")
                    raw = download_yf(symbols, period, freq_choice)
                    break
        else:
            raw = download_yf(symbols, period, freq_choice)
    except Exception as e:
        st.error(f"Errore nel download dei dati: {e}")
        st.stop()

fig = go.Figure()
table_rows = []

def add_indicators(close_series):
    df = pd.DataFrame({"Close": close_series})
    df["SMA20"] = df["Close"].rolling(window=20, min_periods=1).mean()
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    if TA_AVAILABLE:
        df["RSI14"] = ta.momentum.rsi(df["Close"], window=14)
    else:
        # simple RSI fallback (not optimal)
        delta = df["Close"].diff()
        up = delta.clip(lower=0).rolling(window=14).mean()
        down = -delta.clip(upper=0).rolling(window=14).mean()
        rs = up / (down.replace(0, 1e-8))
        df["RSI14"] = 100 - (100 / (1 + rs))
    return df

# Build plot and summary
for name, sym in zip(selected_indices, symbols):
    # extract close series depending on data structure
    if isinstance(raw, dict) and name in raw:
        df_source = raw[name]
        if "Close" in df_source.columns:
            close = df_source["Close"].dropna()
        elif '4. close' in df_source.columns:
            close = df_source['4. close'].astype(float).dropna()
        else:
            # try common alternatives
            cands = [c for c in df_source.columns if 'close' in c.lower()]
            close = df_source[cands[0]].astype(float).dropna() if cands else pd.Series([], dtype=float)
    else:
        # yfinance multiindex or single
        if len(symbols) == 1:
            close = raw['Close'].dropna()
        else:
            # yfinance returns a DataFrame with column multiindex (ticker, field)
            try:
                close = raw[(sym, 'Close')].dropna()
            except Exception:
                # fallback attempt
                close = raw[sym]['Close'].dropna() if sym in raw.columns else pd.Series([], dtype=float)

    if close.empty:
        st.warning(f"Nessun dato per {name} ({sym}).")
        continue

    # indicators and normalized series for plotting
    ind = add_indicators(close)
    norm = (close / close.iloc[0]) * 100

    fig.add_trace(go.Scatter(x=norm.index, y=norm.values, mode='lines', name=name,
                             hovertemplate='%{x}<br>%{y:.2f} (base 100)'))

    fig.add_trace(go.Scatter(x=ind.index, y=ind["SMA20"], mode='lines', name=f"SMA20 {name}", opacity=0.6))
    fig.add_trace(go.Scatter(x=ind.index, y=ind["EMA20"], mode='lines', name=f"EMA20 {name}", opacity=0.6))

    last_date = close.index[-1].strftime("%Y-%m-%d")
    last_value = close.iloc[-1]
    change_pct = (close.iloc[-1] / close.iloc[-2] - 1) * 100 if len(close) >= 2 else 0.0
    table_rows.append({"Indice": name, "Simbolo": sym, "Ultima data": last_date, "Ultimo valore": f"{last_value:.2f}", "Variazione % (ultimo giorno)": f"{change_pct:.2f}%"})

fig.update_layout(title="Andamento normalizzato (base 100) — confronto indici",
                  xaxis_title="Data", yaxis_title="Valore (base 100)",
                  hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

st.plotly_chart(fig, use_container_width=True)

st.markdown("### Riepilogo indici")
df_summary = pd.DataFrame(table_rows)
st.dataframe(df_summary)

if st.button("Scarica dati (CSV)"):
    combined = pd.DataFrame()
    for name, sym in zip(selected_indices, symbols):
        if isinstance(raw, dict) and name in raw:
            s = raw[name]
            c = s["Close"] if "Close" in s.columns else s.iloc[:,0]
            combined[name] = c
        else:
            if len(symbols) == 1:
                c = raw['Close']
            else:
                try:
                    c = raw[(sym, 'Close')]
                except Exception:
                    c = raw[sym]['Close'] if sym in raw.columns else pd.Series([], dtype=float)
            combined[name] = c
    csv = combined.to_csv()
    st.download_button("Download CSV", data=csv, file_name="indici_mercati.csv", mime="text/csv")

st.markdown("---")
st.markdown("**Nota:** i dati provengono da Yahoo Finance tramite yfinance e/o Alpha Vantage. I feed gratuiti possono avere ritardi. Per dati real-time affidabili usa provider a pagamento.")
