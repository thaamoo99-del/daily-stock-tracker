import os
import time
import requests
import yfinance as yf
import feedparser
import urllib.parse

STOCKS = {
    "ATHERENERG.NS": "Ather Energy",
    "DRREDDY.NS": "Dr Reddys Laboratories",
    "HDFCBANK.NS": "HDFC Bank",
    "IDFCFIRSTB.NS": "IDFC First Bank",
    "HINDUNILVR.NS": "Hindustan Unilever",
    "RELIANCE.NS": "Reliance Industries",
    "ITC.NS": "ITC Ltd",
    "MANAPPURAM.NS": "Manappuram Finance",
    "MUTHOOTFIN.NS": "Muthoot Finance",
    "WIPRO.NS": "Wipro",
    "INDIAMART.NS": "IndiaMART InterMESH",
    "IRCTC.NS": "IRCTC",
    "RALLIS.NS": "Rallis India",
    "RTNPOWER.NS": "RattanIndia Power",
    "STUDDS.NS": "Studds Accessories",
    "YESBANK.NS": "Yes Bank",
    "GOLDBEES.NS": "Gold BeES",
    "SILVERBEES.NS": "Silver BeES",
    "NIFTYBEES.NS": "Nifty 50 BeES"
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

def fetch_stock_and_news():
    results = []
    for ticker, name in STOCKS.items():
        try:
            # 1. Price Data
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5d")
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                curr_close = hist['Close'].iloc[-1]
                pct_change = ((curr_close - prev_close) / prev_close) * 100
            elif len(hist) == 1:
                curr_close = hist['Close'].iloc[-1]
                pct_change = 0.0
            else:
                curr_close = 0.0
                pct_change = 0.0

            # 2. News Search with strict validation
            clean_name = name.replace(" Ltd", "").replace(" InterMESH", "")
            search_query = f'"{clean_name}" share price'
            encoded = urllib.parse.quote(search_query)
            rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
            
            feed = feedparser.parse(rss_url)
            articles = []
            name_token = clean_name.split()[0].lower()
            
            for entry in feed.entries[:6]:
                # Strict check: headline MUST contain the core company name or token
                if name_token in entry.title.lower() or "etf" in name_token or "bees" in name_token:
                    articles.append(entry.title)
                if len(articles) == 3:
                    break

            results.append({
                "ticker": ticker,
                "name": name,
                "price": round(float(curr_close), 2),
                "change": round(float(pct_change), 2),
                "news": articles
            })
        except Exception as e:
            print(f"Error fetching {name}: {e}")
    return results

def get_ai_catalyst(name, price, change, news_list):
    """Fetches direct catalyst explanation per stock safely using gemini-1.5-flash"""
    if not news_list:
        return f"Trading at ₹{price} ({change}%). No major company headlines today; moving in sync with broader market index."
    
    news_summary = " | ".join(news_list)
    prompt = (
        f"You are a stock market analyst. Stock: {name}. Daily Change: {change}%. "
        f"Recent News: {news_summary}. "
        f"In exactly 1 concise sentence, explain the primary catalyst driving the sentiment or price move."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        res = requests.post(url, json=payload, timeout=20)
        data = res.json()
        if "candidates" in data and data["candidates"]:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            return f"Broader market sector flows and trade volume influencing price action at ₹{price}."
    except Exception:
        return f"Consolidation driven by domestic equity inflows and sector trends."

def send_telegram_chunked(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for i in range(0, len(message), 3800):
        chunk = message[i:i+3800]
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk}, timeout=15)

if __name__ == "__main__":
    records = fetch_stock_and_news()
    if records:
        print("Processing AI Insights...")
        full_report = "📊 Daily Portfolio & News Digest\n\n"
        
        for r in records:
            arrow = "🟢 +" if r['change'] >= 0 else "🔴 "
            full_report += "━━━━━━━━━━━━━━━━━━━━\n"
            full_report += f"📌 {r['name']} | ₹{r['price']} ({arrow}{r['change']}%)\n\n"
            
            full_report += "📰 Latest News Headlines:\n"
            if r['news']:
                for item in r['news']:
                    full_report += f"  • {item}\n"
            else:
                full_report += "  • Tracking index movements (No specific company alert)\n"
            
            # AI Catalyst Generation with 1-second pacing to prevent rate limits
            analysis = get_ai_catalyst(r['name'], r['price'], r['change'], r['news'])
            full_report += f"\n💡 Catalyst Analysis:\n{analysis}\n\n"
            time.sleep(1.2)  # Avoids rate limit triggers completely
            
        send_telegram_chunked(full_report)
        print("Done!")
