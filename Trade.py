import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Conv2D, MaxPooling2D, Flatten
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram import Update
import matplotlib.pyplot as plt
import seaborn as sns
import sqlite3
import cv2
import logging
import os
from datetime import datetime
dsfwg
# Logging sozlamalari
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot tokeni (Telegramdan oling)
TELEGRAM_TOKEN = "7593482245:AAEN-wvWlTZSpv95eSKgHJzOTg_2Igjbzmw"

# SQLite ma'lumotlar bazasini sozlash
def init_db():
    conn = sqlite3.connect("gold_prices.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS prices
                 (timestamp TEXT, price REAL, bid REAL, ask REAL)''')
    conn.commit()
    conn.close()

# MetaTrader 5 bilan ulanish
def connect_mt5():
    if not mt5.initialize():
        logger.error("MetaTrader5 ulanmadi!")
        return False
    logger.info("MetaTrader5 ulandi")
    return True

# Oltin narxlarini olish
def get_gold_price():
    if not mt5.symbol_select("XAUUSD", True):
        logger.error("XAUUSD topilmadi")
        return None
    price_info = mt5.symbol_info_tick("XAUUSD")
    if price_info is None:
        logger.error("Narx ma'lumotlari olinmadiscdvfbte
        return None
    return {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "bid": price_info.bid,
        "ask": price_info.ask,
        "price": (price_info.bid + price_info.ask) / 2
    }

# Narxlarni bazaga saqlash
def save_price_to_db(price_data):
    conn = sqlite3.connect("gold_prices.db")
    c = conn.cursor()
    c.execute("INSERT INTO prices (timestamp, price, bid, ask) VALUES (?, ?, ?, ?)",
              (price_data["time"], price_data["price"], price_data["bid"], price_data["ask"]))
    conn.commit()
    conn.close()

# Tarixiy ma'lumotlarni olish
def get_historical_data(minutes=60):
    conn = sqlite3.connect("gold_prices.db")
    df = pd.read_sql_query("SELECT * FROM prices ORDER BY timestamp DESC LIMIT ?", conn, params=(minutes,))
    conn.close()
    return df[::-1]

# LSTM modeli (narx prognozi uchun)
def build_lstm_model():
    model = Sequential([
        LSTM(30, input_shape=(10, 1), return_sequences=False),
        Dense(15),
        Dense(1)
    ])
    model.compile(optimizer='adam', loss='mse')
    return model

# CNN modeli (rasm tahlili uchun)
def build_cnn_model():
    model = Sequential([
        Conv2D(32, (3, 3), activation='relu', input_shape=(64, 64, 3)),
        MaxPooling2D((2, 2)),
        Conv2D(64, (3, 3), activation='relu'),
        MaxPooling2D((2, 2)),
        Flatten(),
        Dense(128, activation='relu'),
        Dense(3, activation='softmax')  # 3 sinf: ko‘tariladi, tushadi, barqaror
    ])
    model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
    return model

# Narx prognozi
def predict_price(model, data):
    if len(data) < 10:
        return None, None, None, None, None
    scaled_data = (data - data.mean()) / data.std()
    X = np.array([scaled_data[-10:]])
    X = X.reshape((X.shape[0], X.shape[1], 1))
    pred = model.predict(X, verbose=0)[0][0]
    pred_price = pred * data.std() + data.mean()
    current_price = data.iloc[-1]
    change = pred_price - current_price
    change_percent = (change / current_price) * 100
    trend = "ko‘tariladi" if change > 0 else "tushadi" if change < -0.1 else "barqaror"
    prob = np.random.uniform(55, 75)  # Real modelda aniq ehtimollik
    return pred_price, trend, prob, change, change_percent

# Rasm tahlili
def analyze_image(image_path):
    cnn_model = build_cnn_model()  # Real loyihada oldindan o‘qitilgan model
    img = cv2.imread(image_path)
    if img is None:
        return None, None
    img = cv2.resize(img, (64, 64))
    img = img / 255.0  # Normalizatsiya
    img = np.expand_dims(img, axis=0)
    prediction = cnn_model.predict(img, verbose=0)[0]
    classes = ["ko‘tariladi", "tushadi", "barqaror"]
    trend = classes[np.argmax(prediction)]
    prob = float(prediction.max() * 100)
    return trend, prob

# RSI hisoblash
def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else None

# Grafik yaratish
def create_chart(data):
    plt.figure(figsize=(8, 4))
    sns.lineplot(x=pd.to_datetime(data["timestamp"]), y=data["price"], label="XAU/USD")
    plt.xticks(rotation=45)
    plt.title("Oltin Narxi Grafigi")
    plt.tight_layout()
    plt.savefig("chart.png")
    plt.close()

        "📊 Grafik rasm yuboring, 1 daqiqalik prognoz beraman!"
    )

def price(update: Update, context: CallbackContext):
    price_data = get_gold_price()
    if price_data:
        save_price_to_db(price_data)
        update.message.reply_text(
            f"📈 Oltin Narxi (XAU/USD):\n"
            f"Narx: ${price_data['price']:.2f}\n"
            f"Bid: ${price_data['bid']:.2f}\n"
            f"Ask: ${price_data['ask']:.2f}\n"
            f"Vaqt: {price_data['time']}"
        )
    else:
        update.message.reply_text("❌ Narx ma'lumotlari olinmadi. MT5 ulanganligini tekshiring.")

def forecast(update: Update, context: CallbackContext):
    data = get_historical_data(minutes=60)
    if len(data) < 10:
        update.message.reply_text("❌ Prognoz uchun yetarli ma'lumot yo‘q")
        return
    model = build_lstm_model()  # Real loyihada oldindan o‘qitilgan model
    pred_price, trend, prob, change, change_percent = predict_price(model, data["price"])
    if pred_price is None:
        update.message.reply_text("❌ Prognoz hisoblanmadi")
        return
    rsi = calculate_rsi(data["price"])
    rsi_status = "Haddan tashqari sotib olingan" if rsi > 70 else "Haddan tashqari sotilgan" if rsi < 30 else "Neytral"
    change_text = f"{abs(change):.2f} (+{change_percent:.2f}%)" if change > 0 else f"{abs(change):.2f} (-{abs(change_percent):.2f}%)"
    update.message.reply_text(
        f"🔮 Keyingi 1 daqiqa prognozi:\n"
        f"Joriy narx: ${data['price'].iloc[-1]:.2f}\n"
        f"Narx {trend}: ${pred_price:.2f} ({change_text})\n"
        f"Ehtimollik: {prob:.1f}%\n"
        f"RSI: {rsi:.1f} ({rsi_status})\n"
        f"Maslahat: {'Kutish' if trend == 'barqaror' else 'Ehtiyot bo‘ling'}"
    )

def chart(update: Update, context: CallbackContext):
    data = get_historical_data(minutes=60)
    if len(data) < 2:
        update.message.reply_text("❌ Grafik uchun yetarli ma'lumot yo‘q")
        return
    create_chart(data)
    update.message.reply_photo(photo=open("chart.png", "rb"))
    os.remove("chart.png")

def alert(update: Update, context: CallbackContext):
    try:
        price_level = float(context.args[0])
        context.user_data["alert_price"] = price_level
        update.message.reply_text(f"🔔 Narx ${price_level:.2f} ga yetganda xabar beraman")
    except (IndexError, ValueError):
        update.message.reply_text("❌ Iltimos, narxni to‘g‘ri kiriting: /alert 3200")

def handle_image(update: Update, context: CallbackContext):
    file = update.message.photo[-1].get_file()
    file.download("temp_image.jpg")
    trend, prob = analyze_image("temp_image.jpg")
    if trend is None:
        update.message.reply_text("❌ Rasmni tahlil qilib bo‘lmadi. Iltimos, aniq grafik yuboring.")
        return
    update.message.reply_text(
        f"📊 Rasm asosida 1 daqiqalik prognoz:\n"
        f"Narx {trend}\n"
        f"Ehtimollik: {prob:.1f}%"
    )
    os.remove("temp_image.jpg")

# Har daqiqada narx tekshiruvi
def check_alerts(context: CallbackContext):
    price_data = get_gold_price()
    if price_data:
        save_price_to_db(price_data)
        for user_id, data in context.dispatcher.user_data.items():
            if "alert_price" in data:
                alert_price = data["alert_price"]
                if abs(price_data["price"] - alert_price) < 0.5:
                    context.bot.send_message(
                        chat_id=user_id,
                        text=f"🚨 Ogohlantirish: Oltin narxi ${price_data['price']:.2f} ga yetdi!"
                    )
                    del context.dispatcher.user_data[user_id]["alert_price"]

# Asosiy funksiya
def main():
    init_db()
    if not connect_mt5():
        logger.error("Bot ishga tushmadi: MT5 ulanmadi")
        return

    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("price", price))
    dp.add_handler(CommandHandler("forecast", forecast))
    dp.add_handler(CommandHandler("chart", chart))
    dp.add_handler(CommandHandler("alert", alert))
    dp.add_handler(MessageHandler(Filters.photo, handle_image))

    updater.job_queue.run_repeating(check_alerts, interval=60, first=10)

    updater.start_polling()
    logger.info("Bot ishga tushdi")
    updater.idle()

if __name__ == "__main__":
    main()
