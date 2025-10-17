import json
import os
import logging
import csv
from datetime import datetime
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)

TOKEN = "7561194980:AAHMxi1lQnxok9XR5wFsc5iiwW-lrL3PuSQ"
ADMIN_ID = 6793697685

# states
SELECT_GAME, ENTER_ID, SELECT_AMOUNT, PAYMENT_METHOD, CONFIRM_PAYMENT = range(5)
# admin states
ADMIN_PANEL, ADMIN_UPDATE_GAME, ADMIN_UPDATE_PRICE = range(100, 103)

# data folder + files
DATA_FOLDER = os.path.expanduser("~/Desktop/GameBotData")
os.makedirs(DATA_FOLDER, exist_ok=True)
PRICE_FILE = os.path.join(DATA_FOLDER, "prices.json")
CSV_FILE = os.path.join(DATA_FOLDER, "orders.csv")

# ---------------- helper functions ----------------
AMT_TOGGLE_PREFIX = "amt_toggle:"
AMT_DONE = "amt_done"
AMT_CLEAR = "amt_clear"
AMT_CANCEL = "amt_cancel"
CART_EDIT = "cart_edit"
GO_PAYMENT = "go_payment"


def reset_order_context(context: ContextTypes.DEFAULT_TYPE):
    """Clear any leftover order-related fields to prevent cross-order mixing."""
    try:
        for k in ["game", "player_id", "amounts", "amount", "payment"]:
            context.user_data.pop(k, None)
    except Exception:
        pass


def load_prices():
    # folder မရှိလား စစ်ပြီး မရှိရင် ဖန်တီး
    os.makedirs(DATA_FOLDER, exist_ok=True)

    default = {
        "Mobile Legends": [
            ["Dia86-4800", "Dia172- 10200"],
            ["Dia257-15300", "Dia343-20500"],
            ["Dia429-25500", "Dia514-31200"],
            ["Dia600-35500", "Dia706-40500"],
            ["Dia878-50800", "Dia1049-60000"],
            ["Dia1135-66500", "Dia1412-80000"],
            ["Dia2195-122500", "Dia3688-205000"],
            ["Dia5532-312000", "Wp-6000"],
        ],
        "PUBG Mobile": [
            ["60 UC - 4200Ks", "120 UC - 8400Ks"],
            ["180 UC - 12600Ks", "240 UC - 16800Ks"],
            ["325 UC - 20000Ks", "660 UC - 41000Ks"],
            ["1800 UC - 101000Ks", "3850 UC - 200000Ks"],
        ],
    }

    try:
        if not os.path.isfile(PRICE_FILE):
            with open(PRICE_FILE, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=2, ensure_ascii=False)

        with open(PRICE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except (FileNotFoundError, json.JSONDecodeError, OSError):
        # ဖိုင်ပျက်/မရှိပြီး ဖတ်လို့မရသေးရင် default ကိုပြန်ရေး
        with open(PRICE_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2, ensure_ascii=False)
        return default

def save_prices(data):
    with open(PRICE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


CSV_FIELDS = [
    "Date",
    "OrderID",
    "Customer Name",
    "User ID",
    "Game",
    "Player ID",
    "Amount",
    "Payment",
    "Status",
]


def save_order_to_csv(order_data, update=False):
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

    if not update:
        row = {
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "OrderID": order_data.get("order_id", ""),
            "Customer Name": order_data.get("name", ""),
            "User ID": order_data.get("user_id", ""),
            "Game": order_data.get("game", ""),
            "Player ID": order_data.get("player_id", ""),
            "Amount": order_data.get("amount", ""),
            "Payment": order_data.get("payment", ""),
            "Status": order_data.get("status", ""),
        }
        with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writerow(row)
    else:
        updated = False
        rows = []
        with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if r.get("OrderID") == order_data.get("order_id"):
                    r["Status"] = order_data.get("status", r.get("Status"))
                    for key_map, fieldname in [
                        ("name", "Customer Name"),
                        ("game", "Game"),
                        ("player_id", "Player ID"),
                        ("amount", "Amount"),
                        ("payment", "Payment"),
                    ]:
                        if order_data.get(key_map):
                            r[fieldname] = order_data.get(key_map)
                    updated = True
                rows.append(r)
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        if not updated:
            save_order_to_csv(order_data, update=False)


def get_order_by_id(order_id):
    if not os.path.exists(CSV_FILE):
        return None
    with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("OrderID") == order_id:
                return r
    return None


def list_amount_labels_for_game(game: str):
    prices = load_prices()
    rows = prices.get(game, [["Default - 0Ks"]])
    labels = []
    for row in rows:
        for item in row:
            labels.append(item)
    return labels


def build_amount_keyboard(game: str, selected: dict):
    labels = list_amount_labels_for_game(game)
    rows = []
    for label in labels:
        count = selected.get(label, 0)
        mark = "✅" if count > 0 else "□"
        suffix = f" x{count}" if count > 0 else ""
        rows.append(
            [InlineKeyboardButton(f"{mark} {label}{suffix}", callback_data=f"{AMT_TOGGLE_PREFIX}{label}")]
        )
    rows.append(
        [
            InlineKeyboardButton("✅ Done", callback_data=AMT_DONE),
            InlineKeyboardButton("🧹 Clear", callback_data=AMT_CLEAR),
        ]
    )
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data=AMT_CANCEL)])
    return InlineKeyboardMarkup(rows)


def render_cart_summary(selected: dict):
    lines = ["🧺 Cart Summary", ""]
    if not selected:
        lines.append("(လက်ရှိမရွေးထားသေးပါ)")
    else:
        i = 1
        for label, cnt in selected.items():
            lines.append(f"{i}. {label} × {cnt}")
            i += 1
    lines.append("")
    lines.append("ပြောင်းချင်ရင် 🔁 Edit ကိုနှိပ်ပါ။ ဆက်လက်လုပ်ရန် 💳 Payment ကိုနှိပ်ပါ။")
    return "\n".join(lines)


# ---------------- user flow ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ensure no leftover selections from previous orders
    reset_order_context(context)

    user_id = update.effective_user.id
    BTN_GAME = "🎮 Game Top-Up"
    BTN_ADMIN = "⚙️ Admin Panel"
    BTN_CONTACT = "📞 Contact Admin"
    if user_id == 6793697685:
        keyboard = [[BTN_GAME, BTN_ADMIN, BTN_CONTACT]]
    else:
        keyboard = [[BTN_GAME, BTN_CONTACT]]
    await update.message.reply_text(
        "👋 မင်္ဂလာပါ! CASA NOVA Game Shop Bot မှ ကြိုဆိုပါတယ်။",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Reply when user taps the Contact Admin button
    await update.message.reply_text(
        "Admin Account - @casanova_097 ကိုဆက်သွယ်ပါ။အဆင်မပြေမှုများကိုပြောပြပါ။"
    )


async def game_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Starting a new order flow — clear any previous order residue
    reset_order_context(context)

    prices = load_prices()
    games = [[g] for g in prices.keys()]
    await update.message.reply_text(
        "🎮 ဂိမ်းတစ်ခုရွေးပါ👇",
        reply_markup=ReplyKeyboardMarkup(
            games, resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return SELECT_GAME


async def select_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["game"] = update.message.text
    await update.message.reply_text(f"🆔 သင့် {update.message.text} Player ID ထည့်ပါ။")
    return ENTER_ID


async def enter_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["player_id"] = update.message.text
    context.user_data["amounts"] = {}  # dict: {label: count}
    game = context.user_data.get("game")

    # Send inline selector message
    await update.message.reply_text(
        f"💎 {game} အတွက် Top-up amount များကို ရွေးပါ။ တူညီတာကို ထပ်နှိပ်ရင် အရေအတွက် တိုးသွားမယ် (x2, x3 ...)\nပြီးရင် '✅ Done' ကိုနှိပ်ပါ",
        reply_markup=build_amount_keyboard(game, {}),
    )
    return SELECT_AMOUNT


# Inline amounts callback handler inside conversation
async def amounts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    game = context.user_data.get("game")
    if not game:
        await query.answer("Session expired. /start", show_alert=True)
        return ConversationHandler.END

    selected = context.user_data.setdefault("amounts", {})  # dict {label: count}

    if data.startswith(AMT_TOGGLE_PREFIX):
        label = data[len(AMT_TOGGLE_PREFIX):]
        selected[label] = selected.get(label, 0) + 1  # increment count
        await query.edit_message_reply_markup(
            reply_markup=build_amount_keyboard(game, selected)
        )
        return SELECT_AMOUNT

    if data == AMT_CLEAR:
        selected.clear()
        await query.edit_message_reply_markup(
            reply_markup=build_amount_keyboard(game, selected)
        )
        return SELECT_AMOUNT

    if data == AMT_DONE:
        if not selected:
            await query.answer("အနည်းဆုံးတစ်ခုရွေးပါ", show_alert=True)
            return SELECT_AMOUNT
        # Show cart summary with choices
        text = render_cart_summary(selected)
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔁 Edit", callback_data=CART_EDIT),
                    InlineKeyboardButton("💳 Payment", callback_data=GO_PAYMENT),
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data=AMT_CANCEL)],
            ]
        )
        await query.edit_message_text(text=text, reply_markup=kb)
        return SELECT_AMOUNT

    if data == CART_EDIT:
        await query.edit_message_text(
            text=f"💎 {game} Amount များကို ပြန်ရွေးပါ",
            reply_markup=build_amount_keyboard(game, selected),
        )
        return SELECT_AMOUNT

    if data == GO_PAYMENT:
        # dict -> "Label xN" string
        context.user_data["amount"] = ", ".join([f"{k} x{v}" for k, v in selected.items()])
        await query.message.reply_text(
            "💳 Payment method ရွေးပါ👇",
            reply_markup=ReplyKeyboardMarkup(
                [["KBZ Pay", "Wave Pay"]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        return PAYMENT_METHOD

    if data == AMT_CANCEL:
        reset_order_context(context)
        await query.edit_message_text("❌ ဖျက်ပြီးပါပြီ။")
        return ConversationHandler.END

    return SELECT_AMOUNT


async def select_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["payment"] = update.message.text
    summary = (
        f"🧾 Order Summary\n"
        f"🎮 Game: {context.user_data.get('game')}\n"
        f"🆔 ID: {context.user_data.get('player_id')}\n"
        f"💎 Amount(s): {context.user_data.get('amount')}\n"
        f"💳 Payment: {context.user_data.get('payment')}\n\n"
        "09698026353 Note မှာ ငွေပေးချေခြင်း (or) Payment (or) Shop လို့သာရေးပေးပါ။ \n"
        "တခြား မသက်ဆိုင်သော အရာများရေးပါက ငွေဆုံးပါမည်။\n"
        "✅Transaction ငွေလွဲပြေစာ အား ပေးပို့ပါ။👇"
    )
    await update.message.reply_text(summary)
    return CONFIRM_PAYMENT


async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message
    caption = (
        f"📢 New Payment Received\n"
        f"👤Customer: {user.full_name} ({user.id})\n"
        f"🎮Game: {context.user_data.get('game')}\n"
        f"💰Amount(s): {context.user_data.get('amount')}\n"
        f"💳Payment: {context.user_data.get('payment')}\n"
    )

    order_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{order_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    caption_with_id = caption + f"\nOrderID: {order_id}"

    # send to admin
    if msg.photo:
        await context.bot.send_photo(
            chat_id=6793697685,
            photo=msg.photo[-1].file_id,
            caption=caption_with_id,
            reply_markup=reply_markup,
        )
    else:
        await context.bot.send_message(
            chat_id=6793697685,
            text=caption_with_id + "\n\n" + (msg.text or ""),
            reply_markup=reply_markup,
        )

    # send Player ID separately for clarity (your original format kept)
    await context.bot.send_message(
        chat_id=6793697685, text=f".ml {context.user_data.get('player_id')}"
    )

    # save order
    order_data = {
        "order_id": order_id,
        "name": user.full_name,
        "user_id": user.id,
        "game": context.user_data.get("game"),
        "player_id": context.user_data.get("player_id"),
        "amount": context.user_data.get("amount"),  # e.g., "Wp-6000 x3, Dia86-4800 x1"
        "payment": context.user_data.get("payment"),
        "status": "Pending",
    }
    save_order_to_csv(order_data, update=False)

    await update.message.reply_text(
        "👤Admin သို့ order details ပေးပို့ပြီးပါပြီ။သင့်ပြေစာအား 🤖bot မှစစ်ဆေးနေပါသည်။"
        "✅အတည်ပြုမှုကို စောင့်ဆိုင်းပါ။"
    )
    return ConversationHandler.END


# ---------------- admin confirm/cancel ----------------
async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_", 1)
    action, order_id = data
    order = get_order_by_id(order_id)
    if not order:
        await query.message.reply_text("⚠️ Order not found.")
        return
    new_status = "Confirmed" if action == "confirm" else "Canceled"
    save_order_to_csv(
        {
            "order_id": order_id,
            "status": new_status,
            "name": order.get("Customer Name"),
            "game": order.get("Game"),
            "player_id": order.get("Player ID"),
            "amount": order.get("Amount"),
            "payment": order.get("Payment"),
        },
        update=True,
    )

    if action == "confirm":
        await query.message.reply_text("✅ Order has been confirmed.")
    else:
        await query.message.reply_text("❌ Order has been canceled.")
    try:
        user_id = int(order.get("User ID"))
        if action == "confirm":
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "✅ သင်၏ payment ကိုအတည်ပြုပြီးပါပြီ။"
                    "နောက်တစ်ကြိမ်ဝယ်ယူရန် /start ကို နှိပ်ပါ ကျေးဇူးတင်ပါတယ်။"
                ),
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ သင်၏ payment ကို အတည်မပြုနိုင်ပါ။"
                    "မမှန်ကန်သောနည်းလမ်းကို အသုံးပြုထားသည်ကို 🤖bot မှစစ်ဆေးတွေ့ရှိသောကြောင့်"
                    " သင့် 🚫order အားပယ်ချပါသည်💢။ ❗️Admin ကို ဆက်သွယ်ပါ။"
                    "\n\nAdmin Account - @casanova_097 ကိုဆက်သွယ်ပါ။အဆင်မပြေမှုများကိုပြောပြပါ။လိမ်လည်၍ ပို့သော ပြေစာမှား/အတု များအတွက် ဖြေရှင်းချက် ပေးမည်မဟုတ်ပါ။"
                ),
            )
    except Exception:
        pass


# ---------------- admin panel ----------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 6793697685:
        return
    keyboard = [["📋 View Games & Prices", "✏️ Update Prices"], ["⬅️ Back to Home"]]
    await update.message.reply_text(
        "⚙️ Admin Panel",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return ADMIN_PANEL


async def view_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = load_prices()
    lines = ["📋 Current Game Prices\n"]
    for game, rows in prices.items():
        lines.append(f"🎮 {game}")
        for row in rows:
            lines.append("   • " + " | ".join(row))
        lines.append("")
    await update.message.reply_text("\n".join(lines))


async def admin_update_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = load_prices()
    games = [[g] for g in prices.keys()]
    await update.message.reply_text(
        "🎯 ဂိမ်းတစ်ခုရွေးပါ။",
        reply_markup=ReplyKeyboardMarkup(
            games, resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return ADMIN_UPDATE_GAME


async def admin_choose_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 6793697685:
        return
    context.user_data["update_game"] = update.message.text
    await update.message.reply_text(
        "📝 တန်ဖိုးအသစ်များကို ထည့်ပါ (ဥပမာ ➜ 86 Diamonds - 4800Ks | 172 Diamonds - 10200Ks)\n"
        "တန်းခွဲရန် = '|' (each '|' separates a row). Items in same row separated by comma ','."
    )
    return ADMIN_UPDATE_PRICE


async def admin_save_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 6793697685:
        return
    game = context.user_data.get("update_game")
    text = (update.message.text or "").strip()
    rows = [r.strip() for r in text.split("|") if r.strip()]
    new_prices = []
    for r in rows:
        items = [it.strip() for it in r.split(",") if it.strip()]
        new_prices.append(items)
    prices = load_prices()
    prices[game] = new_prices
    save_prices(prices)
    await update.message.reply_text(
        f"✅ {game} အတွက် ဈေးနှုန်းအသစ်များ update လုပ်ပြီးပါပြီ။ (View with '📋 View Games & Prices')"
    )
    return ADMIN_PANEL


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # On cancel, also clear any in-progress order data
    reset_order_context(context)
    await update.message.reply_text("❌ ဖျက်ပြီးပါပြီ။")
    return ConversationHandler.END


# ---------------- handlers registration ----------------
app = ApplicationBuilder().token(TOKEN).build()

user_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("🎮 Game Top-Up"), game_menu)],
    states={
        SELECT_GAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_game)],
        ENTER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_id)],
        SELECT_AMOUNT: [
            CallbackQueryHandler(
                amounts_callback,
                pattern=(
                    rf"^(?:{AMT_DONE}|{AMT_CLEAR}|{AMT_CANCEL}|{CART_EDIT}|{GO_PAYMENT}|{AMT_TOGGLE_PREFIX}.*)$"
                ),
            )
        ],
        PAYMENT_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_payment)],
        CONFIRM_PAYMENT: [
            MessageHandler(
                filters.PHOTO | (filters.TEXT & ~filters.COMMAND), confirm_payment
            )
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

admin_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("⚙️ Admin Panel"), admin_panel)],
    states={
        ADMIN_PANEL: [
            MessageHandler(filters.Regex("📋 View Games & Prices"), view_prices),
            MessageHandler(filters.Regex("✏️ Update Prices"), admin_update_prices),
            MessageHandler(filters.Regex("⬅️ Back to Home"), start),
        ],
        ADMIN_UPDATE_GAME: [
            MessageHandler(
                filters.TEXT & filters.User(6793697685) & ~filters.COMMAND,
                admin_choose_game,
            )
        ],
        ADMIN_UPDATE_PRICE: [
            MessageHandler(
                filters.TEXT & filters.User(6793697685) & ~filters.COMMAND,
                admin_save_price,
            )
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

app.add_handler(CommandHandler("start", start))
app.add_handler(user_conv)
app.add_handler(admin_conv)
# Contact Admin button handler (outside conversations)
app.add_handler(MessageHandler(filters.Regex("📞 Contact Admin"), contact_admin))
# Admin confirm/cancel for orders
app.add_handler(CallbackQueryHandler(handle_admin_action, pattern="^(confirm|cancel)_"))

print("✅ Bot is running...")
app.run_polling()

