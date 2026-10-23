"""Chai Catch: tea leaves fall, catch them in the cup. Joystick left/right, Confirm to start again."""
import json
import os
import random

from chaipi import app

W, H = app.width, app.height
BEST = os.path.join(app.data_dir, 'best.json')
state = {}


def best():
    try:
        return json.load(open(BEST))['best']
    except (OSError, ValueError, KeyError):
        return 0


def reset():
    state.update(cup=W / 2, leaves=[], score=0, lives=3, over=False, spawn=0.0)


reset()


@app.loop(fps=30)
def frame(screen, keys):
    s = state
    if s['over']:
        if keys.pressed('ok'):
            reset()
    else:
        if keys.down('left'):
            s['cup'] = max(18, s['cup'] - 6)
        if keys.down('right'):
            s['cup'] = min(W - 18, s['cup'] + 6)
        s['spawn'] -= 1 / 30
        if s['spawn'] <= 0:
            s['leaves'].append([random.uniform(12, W - 12), -6, random.uniform(1.4, 2.2) + s['score'] * 0.04, random.random() < 0.15])
            s['spawn'] = max(0.35, 1.1 - s['score'] * 0.02)
        for leaf in s['leaves']:
            leaf[1] += leaf[2]
        for leaf in [l for l in s['leaves'] if l[1] > H - 34]:
            s['leaves'].remove(leaf)
            if abs(leaf[0] - s['cup']) < 22:
                s['score'] += 3 if leaf[3] else 1
                app.buzz(12)
            elif not leaf[3]:
                s['lives'] -= 1
                app.buzz(40)
        if s['lives'] <= 0:
            s['over'] = True
            if s['score'] > best():
                json.dump({'best': s['score']}, open(BEST, 'w'))

    screen.clear()
    screen.text('Chai Catch', 10, 20, 'fg', 15, bold=True)
    screen.text('%d  ·  best %d' % (s['score'], max(best(), s['score'])), W - 10, 20, 'accent', 13, mono=True, align='right')
    for i in range(max(0, s['lives'])):
        screen.circle(15 + i * 13, 33, 4, 'berry')
    for x, y, _, gold in s['leaves']:
        screen.circle(x, y, 5, 'warn' if gold else 'good')
    cx = s['cup']
    screen.rect(cx - 18, H - 30, 36, 20, 'accent', radius=5)
    screen.rect(cx + 16, H - 26, 7, 10, 'accent', fill=False, radius=3, width=2)
    if s['over']:
        screen.rect(40, H / 2 - 30, W - 80, 56, 'surface', radius=12)
        screen.text('Spilled!  Score %d' % s['score'], W / 2, H / 2 - 5, 'fg', 15, bold=True, align='center')
        screen.text('Confirm plays again · Esc quits', W / 2, H / 2 + 15, 'muted', 11, align='center')
