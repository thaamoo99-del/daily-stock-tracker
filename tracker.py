import os
import time
import requests
import yfinance as yf
import feedparser
import urllib.parse
import math

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

def fetch_stock_and_news(ticker, name):
    try:
        stock = yf.Ticker(ticker)
        # 1-month data eduthu NaN values-ai remove panrom
        hist = stock.history(period="1mo")
        hist = hist.dropna(subset=['Close'])
        
        curr_close = 0.0
        pct_change = 0.0
        
        if len(hist) >= 2:
            prev_close = float(hist['Close'].iloc[-2])
            curr_close = float(hist['Close'].iloc[-1])
            if prev_close > 0:
                pct_change = ((curr_close - prev_close) / prev_close) * 100
        elif len(hist) == 1:
            curr_close = float(hist['Close'].iloc[-1])
            pct_change = 0.0

        # Oruvelai innum NaN aaga irundhaal fallback handle panrom
        if math.isnan(curr_close) or curr_close == 0.0:
            print(f"Skipping or price unavailable for {name}")
            return None

        # News Filter
        clean_name = name.replace(" Ltd", "").replace(" InterMESH", "")
        search_query = f'"{clean_name}" share price'
        encoded = urllib.parse.quote(search_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        
        feed = feedparser.parse(rss_url)
        articles = []
        name_token = clean_name.split()[0].lower()
        
        for entry in feed.entries[:6]:
            if name_token in entry.title.lower() or "etf" in name_token or "bees" in name_token:
                articles.append(entry.title)
            if len(articles) == 2:
                break

        return {
            "name": name,
            "price": round(curr_close, 2),
            "change": round(pct_change, 2),
            "news": articles
        }
    except Exception as e:
        print(f"Error fetching {name}: {e}")
        return None

def get_ai_catalyst(name, price, change, news_list):
    if not news_list:
        return f"Trading at ₹{price} ({change}%). Moving in sync with broader market trend."
    
    news_text = " | ".join(news_list)
    prompt = (
        f"Stock: {name}. Change: {change}%. Price: ₹{price}. "
        f"Headlines: {news_text}. "
        f"Explain in exactly 1 direct sentence the core market catalyst behind this move."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        res = requests.post(url, json=payload, timeout=20).json()
        if "candidates" in res and res["candidates"]:
            return res["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        pass
    return "Consolidation driven by domestic equity inflows and sector trends."

def send_telegram_single(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": message
    }
    requests.post(url, json=payload, timeout=15)

if __name__ == "__main__":
    send_telegram_single("📊 Daily Portfolio Updates Starting...")
    time.sleep(1.5)

    for ticker, name in STOCKS.items():
        data = fetch_stock_and_news(ticker, name)
        
        # Valid price illana antha stock message send aagadhu (NaN thadukkum)
        if not data:
            continue
            
        arrow = "🟢 +" if data['change'] >= 0 else "🔴 "
        card = f"📌 {data['name']} | ₹{data['price']} ({arrow}{data['change']}%)\n\n"
        
        card += "📰 Latest News:\n"
        if data['news']:
            for n in data['news']:
                card += f"  • {n}\n"
        else:
            card += "  • No major company alert today.\n"
            
        analysis = get_ai_catalyst(data['name'], data['price'], data['change'], data['news'])
        card += f"\n💡 Catalyst Analysis:\n{analysis}"
        
        send_telegram_single(card)
        time.sleep(1.5)

    print("Completed sending updates!")
