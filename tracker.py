import os
import requests
import yfinance as yf
import feedparser
import urllib.parse

# 18 Portfolio Holdings
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
    "GOLDBEES.NS": "Nippon India Gold BeES",
    "SILVERBEES.NS": "Nippon India Silver BeES",
    "NIFTYBEES.NS": "Nippon India Nifty 50 BeES"
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

            # 2. Targeted News from Moneycontrol, Livemint & Economic Times
            search_query = f"{name} (site:moneycontrol.com OR site:livemint.com OR site:economictimes.indiatimes.com)"
            encoded_query = urllib.parse.quote(search_query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
            
            feed = feedparser.parse(rss_url)
            articles = []
            
            # If site-specific news is empty, fallback to general financial news
            if not feed.entries:
                fallback_query = urllib.parse.quote(f"{name} share market news")
                fallback_rss = f"https://news.google.com/rss/search?q={fallback_query}&hl=en-IN&gl=IN&ceid=IN:en"
                feed = feedparser.parse(fallback_rss)

            for entry in feed.entries[:4]:  # Pulls up to 4 latest news items
                source_title = entry.title
                articles.append(source_title)

            results.append({
                "ticker": ticker,
                "name": name,
                "price": round(float(curr_close), 2),
                "change": round(float(pct_change), 2),
                "news": articles
            })
        except Exception as e:
            print(f"Error processing {name}: {e}")
    return results

def get_ai_catalyst_analysis(stock_item):
    if not stock_item['news']:
        return "No breaking company-specific news. Price move driven by sector sentiment & general market trend."
    
    prompt = (
        f"Stock: {stock_item['name']} (NSE Ticker: {stock_item['ticker']})\n"
        f"Daily Price Change: {stock_item['change']}% (Close: ₹{stock_item['price']})\n"
        f"Recent News from Financial Outlets (Moneycontrol/Mint/ET):\n"
        + "\n".join([f"- {n}" for n in stock_item['news']]) + "\n\n"
        f"Task: In 1-2 sharp, direct sentences, explain what the latest news signifies and whether it acts as a positive, negative, or neutral catalyst for the stock's current move."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        res = requests.post(url, json=payload, timeout=20)
        data = res.json()
        if "candidates" in data:
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            return "Analysis pending API quota update."
    except Exception as e:
        return f"AI summary error: {e}"

def send_telegram_chunked(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # Telegram max limit is 4096 characters per message
    for i in range(0, len(message), 3900):
        chunk = message[i:i+3900]
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "Markdown"}, timeout=15)

if __name__ == "__main__":
    records = fetch_stock_and_news()
    if records:
        full_report = "📊 *Daily Comprehensive Portfolio & Financial News Digest*\n\n"
        
        for r in records:
            arrow = "🟢 +" if r['change'] >= 0 else "🔴 "
            full_report += f"━━━━━━━━━━━━━━━━━━━━\n"
            full_report += f"📌 *{r['name']}* | ₹{r['price']} ({arrow}{r['change']}%)\n\n"
            
            # News Section
            full_report += "📰 *Latest Moneycontrol / Mint / ET News:*\n"
            if r['news']:
                for item in r['news']:
                    full_report += f"  • {item}\n"
            else:
                full_report += "  • No major headlines found in the last 24h.\n"
            
            # AI Catalyst Explanation Section
            full_report += "\n💡 *Catalyst Analysis:*\n"
            analysis = get_ai_catalyst_analysis(r)
            full_report += f"{analysis}\n\n"
            
        send_telegram_chunked(full_report)
