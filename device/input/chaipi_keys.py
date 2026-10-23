#!/usr/bin/env python3
"""chaipi-keys: drive ChAIpi from a terminal (over SSH), before the buttons are wired or for testing.

  arrows / w a s d   joystick        Enter or Space  Confirm         j   joystick press
  Backspace          Backspace       Esc             Esc             Tab Tab
  m                  Menu            M               hold Menu (quick panel)
  f                  Fn              `               typing mode: keys become letters for Wi-Fi passwords
  Ctrl-C             quit

Terminals don't report key releases, so each key is a short press. Uppercase C holds Confirm (long press).
"""
import json
import os
import socket
import sys
import termios
import time
import tty

KEYS = {'\x1b[A': 'UP', '\x1b[B': 'DOWN', '\x1b[C': 'RIGHT', '\x1b[D': 'LEFT', 'w': 'UP', 's': 'DOWN', 'a': 'LEFT', 'd': 'RIGHT',
        '\r': 'OK', ' ': 'OK', 'j': 'STICK', '\x7f': 'BKSP', '\x1b': 'ESC', '\t': 'TAB', 'm': 'MENU', 'f': 'FN'}
HOLD = {'M': 'MENU', 'C': 'OK'}


def read_key(fd):
    ch = os.read(fd, 1).decode(errors='ignore')
    if ch == '\x1b':
        # Arrow keys arrive as ESC [ X; a lone ESC is the Esc key.
        import select
        if select.select([fd], [], [], 0.03)[0]:
            ch += os.read(fd, 2).decode(errors='ignore')
    return ch


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else '/run/chaipi/input.sock'
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(path)
    send = lambda m: s.sendall((json.dumps(m) + '\n').encode())
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    typing = False
    print(__doc__)
    try:
        tty.setraw(fd)
        while True:
            k = read_key(fd)
            if k == '\x03':
                break
            if k == '`':
                typing = not typing
                sys.stdout.write('\r\n[typing mode %s]\r\n' % ('on: keys are letters, Enter submits, ` to leave' if typing else 'off'))
                sys.stdout.flush()
                continue
            if typing and len(k) == 1 and k.isprintable():
                send({'inject': 'char', 'c': k})
                continue
            if typing and k == '\r':
                send({'inject': 'submit'})
                continue
            b = HOLD.get(k)
            if b:
                send({'inject': 'down', 'b': b}); time.sleep(0.9); send({'inject': 'up', 'b': b})
                continue
            b = KEYS.get(k)
            if b:
                send({'inject': 'down', 'b': b}); time.sleep(0.06); send({'inject': 'up', 'b': b})
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print()


if __name__ == '__main__':
    main()
