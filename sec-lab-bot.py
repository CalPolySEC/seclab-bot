#!/usr/bin/env python3
""" SecLab Bot client """

import sys
import os
import time
import curses
import logging
from typing import Optional
import requests
from pyfiglet import Figlet


LOG_FILE = 'files/client.log'
MAX_LOG_ENTRIES = 1024

API_USER = os.environ.get("API_USER")
API_PASS = os.environ.get("API_PASS")
API_URL = "https://cpsecurity.club/api/v1/status"
# API_URL = "http://localhost:3000/api/v1/status"

WEBHOOK_URL = os.environ.get("WEBHOOK")
WEBHOOK_MESSAGES = {
    "open": "Lab is OPEN :)",
    "closed": "Lab is CLOSED :(",
    "fire": "Lab is ON FIRE 🔥",
    "coffee": "Out for coffee ☕"
}

FIGLET_FONT = 'doh'
FIGLET_WIDTH = 154
FIGLET = Figlet(font=FIGLET_FONT, width=FIGLET_WIDTH)
BANNER_OPEN = FIGLET.renderText('Lab is OPEN :)'.strip())
BANNER_CLOSE = FIGLET.renderText('Lab is CLOSED :('.strip())

with open('fire.txt', 'r') as f:
    fire = f.read()

BANNER_FIRE = FIGLET.renderText(('Lab is\n').strip()) + fire

with open('coffee.txt', 'r') as c:
    coffee = c.read()

BANNER_COFFEE = FIGLET.renderText(('Out for\n').strip()) + coffee

STATE_CLOSED = 0
STATE_OPEN = 1

PRE_DEF_COLORS = {
    "open": "brightgreen",
    "closed": "red",
    "fire": "orange",
    "coffee": "8f7369"
}


def api_request(reqtype, statcolor: Optional[str] = None):
    """ Takes a request type (open, closed, etc.) and makes the request """
    logging.info("client sent " + reqtype + " request")
    if statcolor is None:
        if reqtype in PRE_DEF_COLORS:
            statcolor = PRE_DEF_COLORS[reqtype]
        else:
            statcolor = "purple"
    data = {"StatusName": reqtype, "StatusColor": statcolor}
    try:
        resp = requests.post(API_URL, json=data, auth=(API_USER, API_PASS))
    except Exception:
        return False
    if resp.status_code != 200:
        return False
    if WEBHOOK_URL:
        text = WEBHOOK_MESSAGES.get(reqtype, f"Lab is {reqtype}")
        try:
            webhook_resp = requests.post(WEBHOOK_URL, json={"content": text})
            if webhook_resp.status_code != 200:
                return False
        except Exception:
            return False
    return True


def ncurses_write(win, msg):
    """ Takes an ncurses screen and a string and writes to the screen """
    try:
        win.clear()
        win.addstr(msg, curses.A_BOLD)
    except Exception as exc:
        logging.warning("NCurses exception: " + str(exc))


def main(win):
    """ ncurses loop """
    logging.info("client init")

    # ncurses init
    win.clear()
    curses.curs_set(0)
    win.nodelay(0)
    win.addstr("Use any key to toggle, or control-c to quit")
    win.refresh()
    win.timeout(120000)
    success = True
    gotchar = 0

    while True:
        ch = win.getch()  # wait for keypress
        try:
            if ch == -1:
                banner = get_remote_status()
            else:
                banner = set_status(win, ch, success, gotchar)
        except KeyboardInterrupt:
            logging.info("client exit")
            return
        if banner:
            ncurses_write(win, banner)


def get_status() -> str:
    logging.info("client getting status")
    try:
        resp = requests.get(API_URL)
    except Exception:
        return "error"
    if resp.status_code != 200:
        return "error"
    return resp.json().get("data", "error").get("status", "error")


def get_state():
    status = get_status()
    if status == "open":
        return 1
    return 0


def set_status(win, ch: str, success: bool, gotchar: float):
    state = get_state()
    logging.error(state)
    if not truncate_log():
        return
    if time.time() - gotchar < 0.1:
        return
    if ch == ord('f') and state == STATE_OPEN:  # the lab is burning
        reqtype = "fire"
        success = api_request(reqtype)
        if success:
            return BANNER_FIRE
    elif ch == ord('c') and state == STATE_OPEN:  # coffee mode
        reqtype = "coffee"
        success = api_request(reqtype)
        if success:
            return BANNER_COFFEE
    elif ch == ord('|') and state == STATE_OPEN:
        curses.echo()
        win.addstr(0, 0, "Status: ")
        win.refresh()
        reqtype = win.getstr(0, 8, 6)
        win.addstr(1, 0, "Color: ")
        win.refresh()
        statcolor = win.getstr(1, 7, 6)
        curses.noecho()
        try:
            statcolor = statcolor.decode('utf-8')
            reqtype = reqtype.decode('utf-8')
        except Exception:
            return
        if not reqtype or not statcolor:
            return
        success = api_request(reqtype, statcolor)
        if success:
            return FIGLET.renderText(f'Lab is {reqtype.upper()}'.strip())
    elif state == STATE_CLOSED:
        reqtype = "open"
        success = api_request(reqtype)
        if success:
            return BANNER_OPEN
    elif state == STATE_OPEN:
        reqtype = "closed"
        success = api_request(reqtype)
        if success:
            return BANNER_CLOSE
    if success:
        logging.info(f"{reqtype} request success")
    else:
        curses.flash()
        curses.beep()
        logging.warning(f"{reqtype} request failed")
    gotchar = time.time()


def get_remote_status():
    status = get_status()
    if status == "open":
        return BANNER_OPEN
    elif status == "closed":
        return BANNER_CLOSE
    elif status == "coffee":
        return BANNER_COFFEE
    elif status == "fire":
        return BANNER_FIRE
    else:
        return FIGLET.renderText(f'Lab is {status.upper()}'.strip())


def show_help():
    """ Print help information """
    print("SecLab Bot usage: python3 sec-lab-bot.py")
    print()
    print("The following env vars are required for operation:")
    print("\tAPI_USER\t[api username]")
    print("\tAPI_PASS\t[api password]")
    print("Use any key to toggle open/close, or control-c to quit")


def truncate_log():
    """ Dump the log file if it's gotten too long """
    try:
        with open(LOG_FILE, 'w+') as log_file:
            if len(log_file.readlines()) > MAX_LOG_ENTRIES:
                log_file.write("")
        return True
    except Exception:
        print("Error truncating log file")
        return False


if __name__ == '__main__':
    if "-h" in sys.argv or "--help" in sys.argv:
        show_help()
        sys.exit(0)

    logging.basicConfig(filename=LOG_FILE,
                        format='[%(asctime)s] %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p',
                        level=logging.DEBUG)

    curses.wrapper(main)

    logging.shutdown()
    sys.exit(0)
