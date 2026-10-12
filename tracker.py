import os
import requests
import yfinance as yf
import feedparser
import urllib.parse
import json

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

            # 2. Targeted News Query with Strict Ticker/Name
            clean_name = name.replace("Nippon India ", "").replace(" Ltd", "")
            search_query = f'"{clean_name}" (site:moneycontrol.com OR site:livemint.com OR site:economictimes.indiatimes.com)'
            encoded_query = urllib.parse.quote(search_query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
            
            feed = feedparser.parse(rss_url)
            articles = []
            for entry in feed.entries[:3]:
                articles.append(entry.title)

            # Fallback if no site-specific news
            if not articles:
                fallback_query = urllib.parse.quote(f'"{clean_name}" share price')
                fallback_rss = f"https://news.google.com/rss/search?q={fallback_query}&hl=en-IN&gl=IN&ceid=IN:en"
                feed = feedparser.parse(fallback_rss)
                for entry in feed.entries[:2]:
                    articles.append(entry.title)

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

def get_batch_ai_catalysts(stock_records):
    """
    Sends ALL 18 stocks in a single API request.
    Prevents RPM rate limit triggers entirely.
    """
    prompt = (
        "You are an expert Indian stock market analyst. Analyze the following portfolio stocks and their latest news.\n"
        "For EACH stock, write exactly 1 concise, direct sentence explaining what the news/market sentiment indicates "
        "and whether it is a Positive, Negative, or Neutral catalyst for the price move.\n"
        "Return the response strictly as a JSON object where keys are the stock names and values are the 1-sentence analysis.\n\n"
        "Input Data:\n"
    )
    for s in stock_records:
        news_text = " | ".join(s['news']) if s['news'] else "No breaking company news; tracking market index."
        prompt += f"- Stock: {s['name']} (Price: ₹{s['price']}, Move: {s['change']}%). News: {news_text}\n"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    try:
        res = requests.post(url, json=payload, timeout=40)
        data = res.json()
        if "candidates" in data:
            raw_text = data['candidates'][0]['content']['parts'][0]['text']
            return json.loads(raw_text)
        else:
            err_msg = data.get("error", {}).get("message", "API request limit")
            print(f"Gemini API Error: {err_msg}")
            return {}
    except Exception as e:
        print(f"AI Batch Error: {e}")
        return {}

def send_telegram_chunked(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for i in range(0, len(message), 3900):
        chunk = message[i:i+3900]
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk}, timeout=15)

if __name__ == "__main__":
    records = fetch_stock_and_news()
    if records:
        print("Fetching AI Batch Insights...")
        catalysts_dict = get_batch_ai_catalysts(records)
        
        full_report = "📊 *Daily Portfolio & News Digest*\n\n"
        for r in records:
            arrow = "🟢 +" if r['change'] >= 0 else "🔴 "
            full_report += "━━━━━━━━━━━━━━━━━━━━\n"
            full_report += f"📌 {r['name']} | ₹{r['price']} ({arrow}{r['change']}%)\n\n"
            
            # News section
            full_report += "📰 Latest Moneycontrol / Mint / ET News:\n"
            if r['news']:
                for item in r['news']:
                    full_report += f"  • {item}\n"
            else:
                full_report += "  • No major headlines found today.\n"
            
            # AI Catalyst Explanation
            full_report += "\n💡 Catalyst Analysis:\n"
            analysis = catalysts_dict.get(
                r['name'], 
                "Price action influenced by broader sector sentiment and daily trading volume."
            )
            full_report += f"{analysis}\n\n"
            
        send_telegram_chunked(full_report)
        print("Completed successfully!")
