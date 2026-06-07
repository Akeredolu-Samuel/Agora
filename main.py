import os
import asyncio
import socket
import io

# Force IPv4 (fixes broken IPv6 on Hugging Face / Render)
_old_getaddrinfo = socket.getaddrinfo
def _new_getaddrinfo(*args, **kwargs):
    return [r for r in _old_getaddrinfo(*args, **kwargs) if r[0] == socket.AF_INET]
socket.getaddrinfo = _new_getaddrinfo

from dotenv import load_dotenv
import qrcode
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.request import HTTPXRequest

import db
import nlp
import web3_client

load_dotenv()
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
ARCSCAN_BASE_URL = "https://testnet.arcscan.app"

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _short(addr: str) -> str:
    """0x9572...916a"""
    return addr[:6] + "..." + addr[-4:]

def _tx_link(tx_hash: str) -> str:
    return f"{ARCSCAN_BASE_URL}/tx/{tx_hash}"

def _qr_bytes(data: str) -> io.BytesIO:
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, "PNG")
    bio.seek(0)
    return bio

WELCOME_BACK_TEXT = (
    "👋 *Welcome back to Agora Arc!*\n\n"
    "Your Web3 payment wallet is ready and waiting.\n\n"
    "━━━━━━━━━━━━━━━\n"
    "📖 *Commands*\n"
    "• `/balance` — Check your wallet balance\n"
    "• `/history` — View recent transactions\n"
    "• `/qr` — Show your wallet QR code\n"
    "• `/private_key` — Export your private key\n\n"
    "💬 *Natural Language Commands*\n"
    "• `pay 10 to John` — Send USDC\n"
    "• `save 0x... as John` — Save a contact\n"
    "• `swap 10 usdc for eurc` — Swap tokens\n"
    "• Reply to a message with `tip 5` — Tip someone\n"
    "━━━━━━━━━━━━━━━\n\n"
    "🐦 *Follow us on X for updates!*\n"
    "[👉 @agora\\_payy](https://x.com/agora_payy)\n"
    "👤 *Founder:* [@samwissyy](https://x.com/samwissyy)"
)

NEW_WALLET_TEXT = (
    "🎉 *Welcome to Agora Arc!*\n\n"
    "I've created a brand-new Web3 wallet for you on the *Arc Blockchain*.\n\n"
    "━━━━━━━━━━━━━━━\n"
    "📬 *Your Address:*\n`{address}`\n\n"
    "🔑 *Private Key:*\n`{private_key}`\n"
    "━━━━━━━━━━━━━━━\n\n"
    "🚨 *CRITICAL — Save your private key somewhere safe!*\n"
    "If you lose it, you lose access to your funds forever.\n\n"
    "Fund this address with USDC on the Arc Testnet to get started.\n\n"
    "📖 *Commands*\n"
    "• `/balance` — Check your wallet balance\n"
    "• `/history` — View recent transactions\n"
    "• `/qr` — Show your wallet QR code\n"
    "• `/private_key` — Export your private key\n\n"
    "💬 *Natural Language Commands*\n"
    "• `pay 10 to John` — Send USDC\n"
    "• `save 0x... as John` — Save a contact\n"
    "• `swap 10 usdc for eurc` — Swap tokens\n"
    "• Reply to a message with `tip 5` — Tip someone\n"
    "━━━━━━━━━━━━━━━\n\n"
    "🐦 *Follow us on X for updates!*\n"
    "[👉 @agora\\_payy](https://x.com/agora_payy)\n"
    "👤 *Founder:* [@samwissyy](https://x.com/samwissyy)"
)

# ---------------------------------------------------------------------------
# /start — persistent wallet + welcome message
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id     = update.effective_user.id
    first_name  = update.effective_user.first_name or "friend"
    wallet_info = db.get_user_wallet(user_id)

    if wallet_info:
        # Returning user — show wallet address, never regenerate
        address = wallet_info["wallet_address"]
        await update.message.reply_photo(
            photo=_qr_bytes(address),
            caption=(
                f"👋 Hey *{first_name}*!\n\n"
                f"📬 *Your Wallet:*\n`{address}`\n\n"
            ) + WELCOME_BACK_TEXT,
            parse_mode="Markdown",
        )
    else:
        # New user — generate wallet once and store it encrypted
        address, private_key = web3_client.generate_wallet()
        db.save_user_wallet(user_id, address, private_key)

        keyboard = [[
            InlineKeyboardButton("🗑️ Delete this private key message", callback_data="delete_pk_msg")
        ]]
        await update.message.reply_photo(
            photo=_qr_bytes(address),
            caption=NEW_WALLET_TEXT.format(address=address, private_key=private_key),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

# ---------------------------------------------------------------------------
# /balance
# ---------------------------------------------------------------------------

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id     = update.effective_user.id
    wallet_info = db.get_user_wallet(user_id)
    if not wallet_info:
        await update.message.reply_text("Please type /start first to generate your wallet.")
        return

    address = wallet_info["wallet_address"]
    await update.message.reply_text("⏳ Fetching balances...")

    usdc    = web3_client.get_usdc_balance(address)
    eurc    = web3_client.get_eurc_balance(address)
    native  = web3_client.get_native_balance(address)

    await update.message.reply_text(
        f"💰 *Wallet Balance*\n\n"
        f"• USDC:  `{usdc:,.4f}`\n"
        f"• EURC:  `{eurc:,.4f}`\n"
        f"• Native (gas): `{native:,.6f}`\n\n"
        f"📬 Address:\n`{address}`",
        parse_mode="Markdown",
    )

# ---------------------------------------------------------------------------
# /history
# ---------------------------------------------------------------------------

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id     = update.effective_user.id
    wallet_info = db.get_user_wallet(user_id)
    if not wallet_info:
        await update.message.reply_text("Please type /start first to generate your wallet.")
        return

    address = wallet_info["wallet_address"]
    await update.message.reply_text("⏳ Fetching transaction history...")

    txs = web3_client.get_transaction_history(address, limit=10)
    if not txs:
        await update.message.reply_text(
            "📭 No transactions found yet.\n\nFund your wallet and make your first payment!"
        )
        return

    lines = ["📋 *Recent Transactions*\n"]
    for tx in txs:
        arrow = "⬆" if tx["type"] == "Sent" else "⬇"
        link  = f"[View]({_tx_link(tx['tx_hash'])})"
        lines.append(
            f"{arrow} *{tx['type']}* {tx['amount']} {tx['symbol']} "
            f"{'to' if tx['type'] == 'Sent' else 'from'} `{tx['counterparty']}` {link}"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )

# ---------------------------------------------------------------------------
# /qr
# ---------------------------------------------------------------------------

async def show_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id     = update.effective_user.id
    wallet_info = db.get_user_wallet(user_id)
    if not wallet_info:
        await update.message.reply_text("Please type /start first to generate your wallet.")
        return

    address = wallet_info["wallet_address"]
    await update.message.reply_photo(
        photo=_qr_bytes(address),
        caption=(
            f"📷 *Your Agora Arc Wallet*\n\n"
            f"`{address}`\n\n"
            f"Fund this address with USDC on the Arc Testnet."
        ),
        parse_mode="Markdown",
    )

# ---------------------------------------------------------------------------
# /private_key
# ---------------------------------------------------------------------------

async def export_private_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id     = update.effective_user.id
    wallet_info = db.get_user_wallet(user_id)
    if not wallet_info:
        await update.message.reply_text("Please type /start first to generate your wallet.")
        return

    private_key = wallet_info["private_key"]
    
    keyboard = [[
        InlineKeyboardButton("✅ Saved (Delete Message)", callback_data="delete_pk_msg")
    ]]
    
    await update.message.reply_text(
        "🚨 *CRITICAL SECURITY WARNING* 🚨\n\n"
        "Anyone with this private key can steal your funds. Never share it with anyone!\n\n"
        f"🔑 *Your Private Key:*\n`{private_key}`\n\n"
        "Click the button below to delete this message once you have saved it securely.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------------------------------------------------------------------
# Natural-language message handler
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id     = update.effective_user.id
    text        = update.message.text
    wallet_info = db.get_user_wallet(user_id)

    if not wallet_info:
        await update.message.reply_text("Please type /start first to generate your wallet.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    intent  = nlp.parse_intent(text)
    action  = intent.get("action")

    # ── Save contact ────────────────────────────────────────────────────────
    if action == "save_contact":
        name    = intent.get("name")
        address = intent.get("address")
        if not name or not address:
            await update.message.reply_text(
                "❌ Couldn't extract name or address. Try:\n`save 0x... as John`",
                parse_mode="Markdown"
            )
            return
        db.save_contact(user_id, name, address)
        await update.message.reply_text(f"✅ Saved *{name}* → `{address}`", parse_mode="Markdown")

    # ── Send USDC (with confirmation) ───────────────────────────────────────
    elif action == "send":
        recipient = intent.get("recipient")
        amount    = intent.get("amount")

        if not recipient or not amount:
            await update.message.reply_text(
                "❌ Couldn't parse amount or recipient. Try:\n`pay 10 to John`",
                parse_mode="Markdown"
            )
            return

        to_address = db.get_contact_address(user_id, str(recipient))
        if not to_address:
            if str(recipient).startswith("0x") and len(str(recipient)) == 42:
                to_address = recipient
            else:
                await update.message.reply_text(
                    f"❌ Contact *{recipient}* not found. Save it first with:\n`save 0x... as {recipient}`",
                    parse_mode="Markdown"
                )
                return

        # Store pending tx in user_data for the callback
        context.user_data["pending_tx"] = {
            "to_address": to_address,
            "amount":     float(amount),
            "memo":       "send",
            "label":      str(recipient),
        }

        keyboard = [[
            InlineKeyboardButton("✅ Confirm", callback_data="confirm_send"),
            InlineKeyboardButton("❌ Cancel",  callback_data="cancel_send"),
        ]]
        await update.message.reply_text(
            f"📤 *Payment Confirmation*\n\n"
            f"You are sending:\n"
            f"• Amount: *{amount} USDC*\n"
            f"• To: *{recipient}*\n"
            f"• Address: `{_short(to_address)}`\n\n"
            f"Please confirm below.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # ── Tip (with confirmation) ──────────────────────────────────────────────
    elif action == "tip":
        amount = intent.get("amount")
        if not update.message.reply_to_message:
            await update.message.reply_text(
                "❌ To tip someone, reply to their message in the group chat with `tip 5`.",
                parse_mode="Markdown"
            )
            return

        target_user    = update.message.reply_to_message.from_user
        target_wallet  = db.get_user_wallet(target_user.id)
        if not target_wallet:
            await update.message.reply_text(
                f"❌ *{target_user.first_name}* doesn't have an Agora wallet yet. "
                f"Tell them to message me and type /start!",
                parse_mode="Markdown"
            )
            return

        to_address = target_wallet["wallet_address"]
        context.user_data["pending_tx"] = {
            "to_address": to_address,
            "amount":     float(amount),
            "memo":       "tip",
            "label":      target_user.first_name,
        }

        keyboard = [[
            InlineKeyboardButton("✅ Confirm", callback_data="confirm_send"),
            InlineKeyboardButton("❌ Cancel",  callback_data="cancel_send"),
        ]]
        await update.message.reply_text(
            f"🎁 *Tip Confirmation*\n\n"
            f"You are tipping:\n"
            f"• Amount: *{amount} USDC*\n"
            f"• To: *{target_user.first_name}*\n"
            f"• Address: `{_short(to_address)}`\n\n"
            f"Please confirm below.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # ── Swap ────────────────────────────────────────────────────────────────
    elif action == "swap":
        from_token = intent.get("from_token", "USDC").upper()
        to_token   = intent.get("to_token", "EURC").upper()
        amount     = intent.get("amount")

        if not amount:
            await update.message.reply_text("❌ Couldn't parse swap amount. Try: `swap 10 usdc for eurc`",
                                         parse_mode="Markdown")
            return

        await update.message.reply_text(
            f"🔁 *Swap Feature Coming Soon!*\n\n"
            f"You want to swap *{amount} {from_token}* → *{to_token}*.\n\n"
            f"The AgoraSwap contract is being deployed to the Arc Testnet. "
            f"Stay tuned — follow us on X for the announcement!\n\n"
            f"🐦 [👉 @agora\\_payy](https://x.com/agora_payy)\n"
            f"👤 *Founder:* [@samwissyy](https://x.com/samwissyy)",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

    # ── Unknown ─────────────────────────────────────────────────────────────
    else:
        await update.message.reply_text(
            "🤷 I didn't understand that. Here are some things you can say:\n\n"
            "• `pay 10 to John`\n"
            "• `save 0x... as John`\n"
            "• `swap 10 usdc for eurc`\n"
            "• Reply to a message with `tip 5`"
        )

# ---------------------------------------------------------------------------
# Callback query handler (confirmations + delete private key)
# ---------------------------------------------------------------------------

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # ── Delete private key message ──────────────────────────────────────────
    if query.data == "delete_pk_msg":
        try:
            await query.message.delete()
        except Exception:
            try:
                await query.message.edit_text("⚠️ Message couldn't be deleted automatically. Please delete it manually!")
            except:
                await query.message.edit_caption("⚠️ Message couldn't be deleted automatically. Please delete it manually!")
        return

    # ── Confirm send / tip ──────────────────────────────────────────────────
    if query.data == "confirm_send":
        pending = context.user_data.get("pending_tx")
        if not pending:
            await query.message.edit_text("❌ Transaction expired. Please try again.")
            return

        wallet_info = db.get_user_wallet(user_id)
        if not wallet_info:
            await query.message.edit_text("❌ Wallet not found. Please type /start.")
            return

        await query.message.edit_text("⏳ Broadcasting transaction...")

        try:
            tx_hash = web3_client.send_usdc(
                wallet_info["private_key"],
                pending["to_address"],
                pending["amount"],
                memo=pending.get("memo", "send"),
            )
            emoji = "🎁" if pending.get("memo") == "tip" else "✅"
            await query.message.edit_text(
                f"{emoji} *Success!*\n\n"
                f"Sent *{pending['amount']} USDC* to *{pending['label']}*\n\n"
                f"[View on ArcScan]({_tx_link(tx_hash)})",
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            await query.message.edit_text(f"❌ Transfer failed:\n`{e}`", parse_mode="Markdown")
        finally:
            context.user_data.pop("pending_tx", None)

    # ── Cancel send ─────────────────────────────────────────────────────────
    elif query.data == "cancel_send":
        context.user_data.pop("pending_tx", None)
        await query.message.edit_text("🚫 Transaction cancelled.")

# ---------------------------------------------------------------------------
# Dummy HTTP server (required by Hugging Face / Render to show "Running")
# ---------------------------------------------------------------------------

def _start_dummy_server():
    import threading
    import socketserver
    from http.server import SimpleHTTPRequestHandler

    port = int(os.getenv("PORT", 7860))

    class _Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Agora Bot is running!")
        def log_message(self, *args):  # silence request logs
            pass

    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("", port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Dummy HTTP server running on port {port}")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("ERROR: Please set TELEGRAM_BOT_TOKEN in your .env file")
        raise SystemExit(1)

    _start_dummy_server()

    t_request = HTTPXRequest(
        connection_pool_size=10,
        connect_timeout=100.0,
        read_timeout=100.0,
        write_timeout=100.0,
        pool_timeout=100.0,
    )

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .request(t_request)
        .get_updates_request(t_request)
        .build()
    )

    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("balance", show_balance))
    app.add_handler(CommandHandler("history", show_history))
    app.add_handler(CommandHandler("qr",      show_qr))
    app.add_handler(CommandHandler("private_key", export_private_key))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    print("Agora Bot is running...")
    app.run_polling()
