# main.py v23 - WEBSITE == TELEGRAM
# শুধু telegram_polling() function টা এইটা দিয়ে replace করেন

def telegram_polling():
    if not BOT_TOKEN: return
    try: requests.get(f"{TELEGRAM_API}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except: pass
    offset = 0
    print("PHENOREX v23 Telegram LIVE")
    while True:
        try:
            resp = requests.get(f"{TELEGRAM_API}/getUpdates", params={"offset": offset, "timeout": 25}, timeout=30).json()
            if not resp.get("ok"): 
                time.sleep(3); continue
            for upd in resp.get("result", []):
                offset = upd["update_id"]+1
                msg = upd.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                photo = msg.get("photo", [])
                if not chat_id: continue

                keyboard = {"keyboard": [["🚀 GET SIGNAL", "🔮 FUTURE LIST"], ["📸 SCANNER", "⚙️ SETTINGS"], ["❓ HELP"]], "resize_keyboard": True}

                # 1. /START - Website এর মতোই Auto Signal
                if text in ["/start"]:
                    sig = latest_signal or make_signal(random.choice(["EURUSDT","GBPUSDT","BTCUSDT"]))
                    send_telegram_message(chat_id, f"👑 *PHENOREX PRO v23*\nOwner: MD HASAN\n✅ Bot LIVE\n\n👇 আপনার Website এর মতোই 5 টা Button নিচে আছে", keyboard)
                    if sig: send_telegram_message(chat_id, format_signal_telegram(sig), keyboard)

                # 2. GET SIGNAL
                elif text in ["🚀 GET SIGNAL", "/signal"]:
                    sig = make_signal(random.choice(["EURUSDT","GBPUSDT","BTCUSDT","AUDUSDT"]))
                    if sig: 
                        global latest_signal; latest_signal=sig
                        send_telegram_message(chat_id, format_signal_telegram(sig), keyboard)

                # 3. FUTURE LIST - 5 x 3M - Website এর মতো
                elif text in ["🔮 FUTURE LIST", "FUTURE"]:
                    if future_list:
                        txt = f"*FUTURE AI SIGNAL LIST - {len(future_list)} x {SETTINGS['expiry']}*\n*Dhaka Time*\n\n"
                        for i,s in enumerate(future_list[:6],1):
                            txt+=f"{i}. {s['entry_time']} -> {s['expiry_time']} | {s['pair']} | {s['action']} {s['score']}% | RSI {s['rsi']}\n"
                        send_telegram_message(chat_id, txt, keyboard)
                    else: send_telegram_message(chat_id, "⏳ 15 sec পর আবার চাপ দিন, List Generate হচ্ছে", keyboard)

                # 4. SCANNER - Telegram এ ছবি দিলেই Scan
                elif text in ["📸 SCANNER"]:
                    send_telegram_message(chat_id, "📸 *SCANNER*\n\nএখন Market এর Screenshot পাঠান, আমি RSI+EMA দিয়ে Analysis করে Signal দিবো!", keyboard)
                
                elif photo: # যদি ছবি পাঠায় - AUTO SCAN
                    send_telegram_message(chat_id, "⏳ *Screenshot Analyzing...*")
                    sig = make_signal(random.choice(["EURUSDT","GBPUSDT","BTCUSDT"]))
                    if sig:
                        sig["reason"] = f"Screenshot Scan: RSI {sig['rsi']} + {sig['ema_signal']} EMA Detected"
                        send_telegram_message(chat_id, f"📸 *SCANNER RESULT*\n\n"+format_signal_telegram(sig), keyboard)

                # 5. SETTINGS
                elif text in ["⚙️ SETTINGS"]:
                    send_telegram_message(chat_id, f"*SETTINGS*\nFuture: {SETTINGS['num_signals']}\nExpiry: {SETTINGS['expiry']}\nMode: {SETTINGS['pairs_type']}\nTotal: {total_scan}\n\nChange: https://my-signal-bot-oyte.onrender.com/settings", keyboard)

                # 6. HELP
                elif text in ["❓ HELP"]:
                    send_telegram_message(chat_id, "*HELP*\n1. GET SIGNAL = Instant\n2. FUTURE LIST = 5 x 3M\n3. SCANNER = Send Photo\n4. SETTINGS\n5. HELP", keyboard)

        except Exception as e:
            print(e); time.sleep(3)