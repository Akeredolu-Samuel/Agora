import os
import asyncio
import socket

# Force IPv4 to fix Hugging Face Spaces network connect errors (broken IPv6)
old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
import qrcode
import io

import db
import nlp
import web3_client

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check if user already has a wallet
    wallet_info = db.get_user_wallet(user_id)
    
    help_text = (
        "\n\n"
        "📖 **What I can do:**\n"
        "• **Save a contact:** `save address 0x... for [name]`\n"
        "• **Send USDC payments:** `send [amount] USDC to [name]`\n"
        "• **Send directly to address:** `send [amount] USDC to 0x...`\n\n"
        "💡 *Tip: I parse natural language! You can type normally, e.g., \"pay 10 usdc to Alice\"*"
    )

    if wallet_info:
        await update.message.reply_text(
            f"Welcome back to Agora Arc!\n\n"
            f"Your Wallet Address is: `{wallet_info['wallet_address']}`\n"
            f"Please ensure it is funded with USDC on the Arc Testnet."
            f"{help_text}",
            parse_mode='Markdown'
        )
    else:
        # Generate new wallet
        address, private_key = web3_client.generate_wallet()
        db.save_user_wallet(user_id, address, private_key)
        
        keyboard = [
            [InlineKeyboardButton("🗑️ Delete/Hide This Private Key Message", callback_data="delete_private_key_msg")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Generate QR code for the address
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(address)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        bio = io.BytesIO()
        img.save(bio, "PNG")
        bio.seek(0)
        
        caption = (
            f"Welcome to Agora Arc!\n\n"
            f"I have generated a new Web3 wallet for you on the Arc blockchain.\n\n"
            f"**Address:** `{address}`\n"
            f"**Private Key:** `{private_key}`\n\n"
            f"🚨 **CRITICAL: Save this private key somewhere safe! If you lose it, you lose access to your funds.**\n\n"
            f"To start sending payments, please fund your address with USDC (and gas) on the Arc Testnet."
            f"{help_text}"
        )
        
        await update.message.reply_photo(
            photo=bio,
            caption=caption,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    wallet_info = db.get_user_wallet(user_id)
    if not wallet_info:
        await update.message.reply_text("Please type /start first to generate your wallet.")
        return

    # Parse intent via DeepSeek
    await update.message.reply_text("Thinking...")
    intent = nlp.parse_intent(text)
    action = intent.get("action")
    
    if action == "save_contact":
        name = intent.get("name")
        address = intent.get("address")
        if not name or not address:
            await update.message.reply_text("Could not extract name or address. Try 'save address 0x... for david'")
            return
            
        db.save_contact(user_id, name, address)
        await update.message.reply_text(f"✅ Saved {name} -> {address}")
        
    elif action == "send":
        recipient = intent.get("recipient")
        amount = intent.get("amount")
        
        if not recipient or not amount:
            await update.message.reply_text("Could not extract amount or recipient. Try 'send 10 usdc to david'")
            return
            
        # Check if recipient is a saved name
        to_address = db.get_contact_address(user_id, recipient)
        if not to_address:
            # Maybe the recipient IS an address
            if str(recipient).startswith("0x") and len(str(recipient)) == 42:
                to_address = recipient
            else:
                await update.message.reply_text(f"❌ Contact '{recipient}' not found. Please save it first.")
                return
        
        await update.message.reply_text(f"Initiating transfer of {amount} USDC to {recipient} ({to_address})...")
        
        try:
            tx_hash = web3_client.send_usdc(wallet_info["private_key"], to_address, float(amount))
            tx_link = f"https://testnet.arcscan.app/tx/{tx_hash}"
            await update.message.reply_text(f"✅ Transfer successful!\n\n[View Transaction on ArcScan]({tx_link})", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Transfer failed: {e}")
            
    elif action == "tip":
        amount = intent.get("amount")
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ To tip someone, you must reply to their message in the group chat!")
            return
            
        target_user_id = update.message.reply_to_message.from_user.id
        target_wallet = db.get_user_wallet(target_user_id)
        
        if not target_wallet:
            await update.message.reply_text(f"❌ The person you replied to does not have an Agora wallet yet. Tell them to message me and type /start!")
            return
            
        to_address = target_wallet["wallet_address"]
        await update.message.reply_text(f"Initiating tip of {amount} USDC to {update.message.reply_to_message.from_user.first_name}...")
        
        try:
            tx_hash = web3_client.send_usdc(wallet_info["private_key"], to_address, float(amount))
            tx_link = f"https://testnet.arcscan.app/tx/{tx_hash}"
            await update.message.reply_text(f"✅ Tip successful! 🎉\n\n[View Transaction on ArcScan]({tx_link})", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Tip failed: {e}")
            
    else:
        await update.message.reply_text("I didn't understand that command. Try saving an address, sending USDC, or tipping.")

async def delete_private_key_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "delete_private_key_msg":
        try:
            await query.message.delete()
        except Exception as e:
            # Fallback if bot lacks permissions
            await query.message.edit_text(
                "⚠️ Bot could not auto-delete this message. Please delete/clear it manually for safety!"
            )

import threading
from http.server import SimpleHTTPRequestHandler
import socketserver

if __name__ == '__main__':
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("Please set TELEGRAM_BOT_TOKEN in your .env file")
        exit(1)

    # Start a dummy HTTP server on port 7860 (required by Hugging Face / Render to show "Running")
    def run_dummy_server():
        port = int(os.getenv("PORT", 7860))
        class DummyHandler(SimpleHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Agora Bot is running!")
                
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("", port), DummyHandler) as httpd:
            print(f"Dummy server running on port {port}")
            httpd.serve_forever()

    threading.Thread(target=run_dummy_server, daemon=True).start()
        
    t_request = HTTPXRequest(
        connection_pool_size=10,
        connect_timeout=100.0,
        read_timeout=100.0,
        write_timeout=100.0,
        pool_timeout=100.0
    )
    
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .request(t_request)
        .get_updates_request(t_request)
        .build()
    )
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(delete_private_key_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # Render defaults to Python 3.14 where asyncio.get_event_loop() throws an error 
    # if no loop exists yet. We explicitly create and set one here.
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    print("Bot is running...")
    application.run_polling()
