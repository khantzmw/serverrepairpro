import telebot
import paramiko
import os
import re
import threading
import uuid

# သင့်၏ Bot Token
BOT_TOKEN = '8858455616:AAER4frpyFgJtzVUPp0IG6fofUnCpLfjj4s'
bot = telebot.TeleBot(BOT_TOKEN)

# User Information မှတ်သားရန် (Queue ပုံစံဖြင့် ယာယီမှတ်ရန်)
user_data = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = "Mingalar par taw thr twy..."
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: message.content_type == 'text' and not message.text.startswith('/'))
def get_credentials(message):
    text = message.text.strip()
    chat_id = message.chat.id
    
    ip = None
    user = "root"
    pw = None

    if "IPv4 Address:" in text:
        ip_match = re.search(r"IPv4 Address:\s*([\d\.]+)", text)
        pw_match = re.search(r"Password:\s*(\S+)", text)
        if ip_match and pw_match:
            ip = ip_match.group(1)
            pw = pw_match.group(1)

    elif len(text.split()) == 2:
        parts = text.split()
        ip = parts[0]
        pw = parts[1]

    if ip and pw:
        # ယခု IP နှင့် Password ကို ယာယီမှတ်ထားမည်
        user_data[chat_id] = {'ip': ip, 'user': user, 'pw': pw}

        confirm_msg = f"Server detail recorded\n\nIP: {ip}\nUser: {user}\nPassword: {pw}\n\nsend the backup file"
        bot.reply_to(message, confirm_msg)
    else:
        bot.reply_to(message, "⚠️ Format wrong")

# နောက်ကွယ်တွင် အလုပ်လုပ်မည့် Function (Background Task)
def process_server_setup(chat_id, ip, user, pw, file_id):
    try:
        # Unique File Name ဖန်တီးခြင်း (ဖိုင်နာမည်များ ထပ်မသွားစေရန်)
        unique_id = uuid.uuid4().hex[:6]
        local_db_path = f"backup_{ip}_{unique_id}.db"

        # Telegram မှ File ကို Download ဆွဲခြင်း
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open(local_db_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        bot.send_message(chat_id, f"[{ip}] 3x-ui installing and restore backup file")

        # SSH ချိတ်ဆက်ခြင်း
        # SSH ချိတ်ဆက်ခြင်း
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=user, password=pw, timeout=15)

        # 3x-ui Install
        install_cmd = 'printf "\\n2\\n\\n\\n" | bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh) v2.9.4 && printf "7\\ny\\nadmin\\n123\\n>
        stdin, stdout, stderr = ssh.exec_command(install_cmd)
        stdout.channel.recv_exit_status() # Install ပြီးဆုံးသည်အထိ စောင့်ရန်

        # SFTP ဖြင့် DB ဖိုင် အစားထိုးခြင်း
        sftp = ssh.open_sftp()
        sftp.put(local_db_path, '/etc/x-ui/x-ui.db')
        sftp.close()

        # Restart ချခြင်း
        ssh.exec_command('systemctl restart x-ui')
        ssh.close()

        # File ရှင်းလင်းခြင်း
        os.remove(local_db_path)

        bot.send_message(chat_id, f"✅✅ Successful! [{ip}] ")

    except Exception as e:
        bot.send_message(chat_id, f"❌ [{ip}] တွင် Error ဖြစ်ပေါ်နေပါသည်: {str(e)}")
        # Error တက်လျှင်လည်း File ကျန်မနေစေရန် ဖျက်မည်
        if os.path.exists(local_db_path):
            os.remove(local_db_path)

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    chat_id = message.chat.id

    
    # User မှ IP/Password အရင်ပို့ထားခြင်း ရှိ/မရှိ စစ်ဆေးခြင်း
    if chat_id not in user_data:
        bot.reply_to(message, "⚠️ send the detail first")
        return

    # လက်ရှိ မှတ်ထားသော Server အချက်အလက်များကို ယူမည်
    server_info = user_data[chat_id]
    ip = server_info['ip']
    user = server_info['user']
    pw = server_info['pw']
    file_id = message.document.file_id

    # ယူပြီးသည်နှင့် နောက်ထပ် Server အသစ်အတွက် ချက်ချင်း ထပ်ပို့နိုင်ရန် Data ကို ဖျက်ပေးလိုက်မည်
    del user_data[chat_id]

    # အသုံးပြုသူကို အသိပေးခြင်း
    bot.reply_to(message, f"⏳ [{ip}] processing and u can send another one")

    # Threading အသုံးပြု၍ Background တွင် Run ခြင်း
    task_thread = threading.Thread(target=process_server_setup, args=(chat_id, ip, user, pw, file_id))
    task_thread.start()

if __name__ == '__main__':
    print("Bot is successfully running with Threading support...")
    bot.infinity_polling()
