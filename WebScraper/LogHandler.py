import time
from time import sleep
from colorama import init
from colorama import Fore
from colorama import Style
from datetime import datetime
init(autoreset=True)


def get_current_time():
    current_time = datetime.now()
    c_hr = current_time.hour
    c_min = current_time.minute
    c_sec = current_time.second
    if c_sec < 10:
        c_sec = str(c_sec)
        c_sec = "0" + c_sec
    if c_min < 10:
        c_min = str(c_min)
        c_min = "0" + c_min
    if c_hr < 10:
        c_hr = str(c_hr)
        c_hr = "0" + c_hr
    c_sec = str(c_sec)
    c_min = str(c_min)
    c_hr = str(c_hr)
    time_formatted = c_hr + ":" + c_min + ":" + c_sec
    return time_formatted


def log(message, type_msg):
    global done_message
    if type_msg == "error":
        print(f"{Fore.LIGHTBLUE_EX}[{get_current_time()}]{Style.RESET_ALL}{Fore.RED}  [!]-{message}")
    elif type_msg == "warn":
        print(f"{Fore.LIGHTBLUE_EX}[{get_current_time()}]{Style.RESET_ALL}{Fore.YELLOW}  [i]-{message}")
    elif type_msg == "log":
        print(f"{Fore.LIGHTBLUE_EX}[{get_current_time()}]{Style.RESET_ALL}{Fore.WHITE}  [-]-{message}")
        done_message = f"\r{Fore.LIGHTBLUE_EX}[{get_current_time()}]{Style.RESET_ALL}{Fore.WHITE}  [-]-{message} - DONE"
    else:
        print("[!]-MSG PRINT ERROR")


def log_done():
    print(done_message)
