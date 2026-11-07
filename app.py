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

# --- Design system "Borse" (tema chiaro) -------------------------------------
DS = {
    "surface_100": "#f5f7f6", "surface_200": "#e9edeb", "surface_raised": "#ffffff",
    "ink": "#14201d", "ink_muted": "#52605b", "rule": "#c9d1cd",
    "petrolio": "#0e5a61", "ottone": "#8a6416",
    "rialzo": "#17703f", "ribasso": "#b5381a",
}
SERIES_COLORS = ["#0e5a61", "#8a6416", "#3a52b0", "#7d3a70", "#5f6e1a", "#5a6a64"]
FONT_DISPLAY = '"Barlow Condensed", "Arial Narrow", sans-serif'
FONT_SANS = '"Source Sans 3", "Segoe UI", system-ui, sans-serif'
FONT_MONO = '"IBM Plex Mono", ui-monospace, Menlo, monospace'

DS_CSS = f"""
<style>
@import url("https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600&family=IBM+Plex+Mono:wght@400;500&family=Source+Sans+3:wght@400;600&display=swap");
h1, h2, h3 {{ font-family: {FONT_DISPLAY} !important; font-weight: 600 !important; letter-spacing: .01em; }}
h1 {{ color: {DS["petrolio"]} !important; }}
[data-testid="stWidgetLabel"] p {{ font-size: 12px !important; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: {DS["ink_muted"]}; }}
.b-table-wrap {{ overflow-x: auto; }}
.b-table {{ border-collapse: collapse; width: 100%; font-family: {FONT_SANS}; font-size: 15px; }}
.b-table th {{ background: {DS["surface_200"]}; text-align: left; padding: 8px 12px; font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: {DS["ink_muted"]}; white-space: nowrap; border: 0; }}
.b-table td {{ padding: 8px 12px; border: 0; border-bottom: 1px solid {DS["rule"]}; white-space: nowrap; color: {DS["ink"]}; }}
.b-table .num {{ text-align: right; font-family: {FONT_MONO}; font-variant-numeric: tabular-nums; font-size: 14px; }}
.b-ticker {{ font-family: {FONT_MONO}; font-size: 12px; color: {DS["ink_muted"]}; }}
.b-var--up {{ color: {DS["rialzo"]}; }} .b-var--down {{ color: {DS["ribasso"]}; }} .b-var--flat {{ color: {DS["ink_muted"]}; }}
.b-note {{ font-size: 13px; line-height: 18px; color: {DS["ink_muted"]}; }}
</style>
"""


def fmt_it(value, decimals=2):
    """Numero in formato italiano: 34.218,47"""
    s = f"{value:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def variazione_html(pct):
    """Variazione con freccia, segno e colore (componente Variazione)."""
    if round(pct, 2) == 0:
        return '<span class="b-var--flat">0,00 %</span>'
    if pct > 0:
        return f'<span class="b-var--up"><span aria-hidden="true">▲</span> +{fmt_it(pct)} %</span>'
    return f'<span class="b-var--down"><span aria-hidden="true">▼</span> −{fmt_it(abs(pct))} %</span>'


st.set_page_config(page_title="Andamento borse mondiali", layout="wide")
st.markdown(DS_CSS, unsafe_allow_html=True)
st.title("Andamento borse mondiali")
st.markdown("Seleziona gli indici e l'intervallo temporale per confrontarne l'andamento su base 100.")

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
selected_indices = st.sidebar.multiselect("Indici", list(INDEX_TICKERS.keys()), default=default)

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
freq_map = {"Giornaliera": "1d", "Settimanale": "1wk", "Mensile": "1mo"}
freq_choice = freq_map[st.sidebar.selectbox("Frequenza", list(freq_map.keys()))]

# Alpha Vantage settings
use_av = st.sidebar.checkbox("Usa Alpha Vantage (intraday) se disponibile", value=False)
av_interval = st.sidebar.selectbox("Intervallo Alpha Vantage", ["1min","5min","15min","30min","60min"], index=1)

# Read API key securely: prefer Streamlit secrets, then env var
ALPHA_API_KEY = None
try:
    ALPHA_API_KEY = st.secrets.get("ALPHA_API_KEY")
except Exception:
    # nessun secrets.toml (es. esecuzione locale)
    pass
if not ALPHA_API_KEY:
    ALPHA_API_KEY = os.environ.get("ALPHA_API_KEY", None)

if use_av and not ALPHA_AVAILABLE:
    st.warning("La libreria alpha_vantage non è installata. Aggiungila a requirements.txt o disattiva Alpha Vantage.")
if use_av and not ALPHA_API_KEY:
    st.warning("Chiave API Alpha Vantage non trovata. Aggiungila in Secrets come ALPHA_API_KEY.")

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
        st.warning(f"Nessun dato per {name} ({sym}). L'indice non compare nel grafico.")
        continue

    # indicators and normalized series for plotting
    ind = add_indicators(close)
    norm = (close / close.iloc[0]) * 100
    base = close.iloc[0] / 100

    k = len(table_rows)
    color = SERIES_COLORS[k % len(SERIES_COLORS)]
    dash = "solid" if k < len(SERIES_COLORS) else "dash"
    group = f"g{k}"

    fig.add_trace(go.Scatter(x=norm.index, y=norm.values, mode='lines', name=name, legendgroup=group,
                             line=dict(color=color, width=2, dash=dash),
                             hovertemplate='%{y:.2f}'))
    # medie mobili sulla stessa scala base 100, stesso colore, 1px, opacità 0,6
    fig.add_trace(go.Scatter(x=ind.index, y=ind["SMA20"] / base, mode='lines', name=f"SMA20 {name}", legendgroup=group,
                             line=dict(color=color, width=1, dash="dash"), opacity=0.6, hovertemplate='%{y:.2f}'))
    fig.add_trace(go.Scatter(x=ind.index, y=ind["EMA20"] / base, mode='lines', name=f"EMA20 {name}", legendgroup=group,
                             line=dict(color=color, width=1, dash="dot"), opacity=0.6, hovertemplate='%{y:.2f}'))
    # ultimo punto marcato
    fig.add_trace(go.Scatter(x=[norm.index[-1]], y=[norm.values[-1]], mode='markers', legendgroup=group,
                             marker=dict(color=color, size=6), showlegend=False, hoverinfo='skip'))

    last_date = close.index[-1].strftime("%d/%m/%Y")
    last_value = close.iloc[-1]
    change_pct = (close.iloc[-1] / close.iloc[-2] - 1) * 100 if len(close) >= 2 else 0.0
    table_rows.append({"Indice": name, "Simbolo": sym, "Ultima data": last_date,
                       "Ultimo valore": fmt_it(last_value), "Variazione": variazione_html(change_pct)})

fig.add_hline(y=100, line=dict(color=DS["ottone"], width=1, dash="dash"))
fig.update_layout(title=dict(text="Andamento normalizzato (base 100)",
                             font=dict(family=FONT_DISPLAY, size=26, color=DS["ink"])),
                  font=dict(family=FONT_SANS, size=13, color=DS["ink_muted"]),
                  paper_bgcolor=DS["surface_100"], plot_bgcolor=DS["surface_100"],
                  xaxis=dict(title="Data", showgrid=False, linecolor=DS["rule"], tickformat="%m/%Y", hoverformat="%d/%m/%Y"),
                  yaxis=dict(title="Valore (base 100)", gridcolor=DS["rule"], zeroline=False),
                  separators=",.",
                  hovermode="x unified",
                  hoverlabel=dict(bgcolor=DS["surface_raised"], bordercolor=DS["rule"],
                                  font=dict(family=FONT_MONO, size=14, color=DS["ink"])),
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                              font=dict(color=DS["ink"])))

st.plotly_chart(fig, use_container_width=True)

st.markdown("### Riepilogo indici")
rows_html = "".join(
    f'<tr><td>{r["Indice"]}</td><td><span class="b-ticker">{r["Simbolo"]}</span></td>'
    f'<td class="num">{r["Ultima data"]}</td><td class="num">{r["Ultimo valore"]}</td>'
    f'<td class="num">{r["Variazione"]}</td></tr>'
    for r in table_rows
)
st.markdown(
    '<div class="b-table-wrap"><table class="b-table"><thead><tr>'
    '<th>Indice</th><th>Simbolo</th><th>Ultima data</th>'
    '<th style="text-align:right">Ultimo valore</th><th style="text-align:right">Var. % (ultimo giorno)</th>'
    f'</tr></thead><tbody>{rows_html}</tbody></table></div>',
    unsafe_allow_html=True,
)
st.write("")

if st.button("Prepara CSV"):
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
    st.download_button("Scarica CSV", data=csv, file_name="indici_mercati.csv", mime="text/csv", type="primary")

st.markdown("---")
st.markdown('<p class="b-note">Dati Yahoo Finance via yfinance e, se attivo, Alpha Vantage. '
            'I feed gratuiti possono avere ritardi: per dati in tempo reale serve un provider a pagamento.</p>',
            unsafe_allow_html=True)
