import os
import requests
import yfinance as yf
import feedparser
import urllib.parse

# Ungaloda Complete Portfolio (NSE tickers with .NS suffix)
STOCKS = {
    # 1. Growth & New-Age EV
    "ATHERENERG.NS": "Ather Energy",
    
    # 2. Large-Cap Bluechips & Banking
    "DRREDDY.NS": "Dr Reddys Laboratories",
    "HDFCBANK.NS": "HDFC Bank",
    "IDFCFIRSTB.NS": "IDFC First Bank",
    "HINDUNILVR.NS": "Hindustan Unilever",
    "RELIANCE.NS": "Reliance Industries",
    "ITC.NS": "ITC Ltd",
    
    # 3. NBFC & Gold Finance
    "MANAPPURAM.NS": "Manappuram Finance",
    "MUTHOOTFIN.NS": "Muthoot Finance",
    
    # 4. IT, Digital & Monopoly Business
    "WIPRO.NS": "Wipro",
    "INDIAMART.NS": "IndiaMART InterMESH",
    "IRCTC.NS": "IRCTC",
    
    # 5. Agro, Power & Mid/Small-Caps
    "RALLIS.NS": "Rallis India",
    "RTNPOWER.NS": "RattanIndia Power",
    "STUDDS.NS": "Studds Accessories",
    "YESBANK.NS": "Yes Bank",
    
    # 6. Benchmark ETFs (Commodities & Index)
    "GOLDBEES.NS": "Nippon India Gold BeES",
    "SILVERBEES.NS": "Nippon India Silver BeES",
    "NIFTYBEES.NS": "Nippon India Nifty 50 BeES"
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

def fetch_stock_data():
    summary_data = []
    for ticker, name in STOCKS.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                curr_close = hist['Close'].iloc[-1]
                pct_change = ((curr_close - prev_close) / prev_close) * 100
            elif len(hist) == 1:
                curr_close = hist['Close'].iloc[-1]
                pct_change = 0.0
            else:
                continue

            query = urllib.parse.quote(f"{name} share stock news")
            rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
            feed = feedparser.parse(rss_url)
            news_items = [entry.title for entry in feed.entries[:3]]

            summary_data.append({
                "name": name,
                "price": round(curr_close, 2),
                "change": round(pct_change, 2),
                "news": news_items
            })
        except Exception as e:
            print(f"Error fetching {name}: {e}")
    return summary_data

def get_ai_insights(stock_records):
    prompt = "You are a stock market analyst. Analyze the following Indian portfolio movements today. For each stock, explain in 2 concise bullets why it moved (correlate with news/market sentiment) and state if it is a fundamental shift or regular market volatility:\n\n"
    for s in stock_records:
        prompt += f"Stock: {s['name']} | Close: ₹{s['price']} | Daily Change: {s['change']}%\n"
        prompt += f"Recent News Headlines: {'; '.join(s['news'])}\n\n"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    res = requests.post(url, json=payload).json()
    
    try:
        return res['candidates'][0]['content']['parts'][0]['text']
    except Exception:
        return "AI analysis could not be generated."

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    records = fetch_stock_data()
    if records:
        header = "📊 *Daily Portfolio & News Digest*\n\n"
        for r in records:
            arrow = "🟢 +" if r['change'] >= 0 else "🔴 "
            header += f"• *{r['name']}*: ₹{r['price']} ({arrow}{r['change']}%)\n"
        
        insights = get_ai_insights(records)
        full_message = f"{header}\n---\n*Market Catalyst Insights:*\n{insights}"
        send_telegram(full_message)
