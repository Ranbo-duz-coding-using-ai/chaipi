"""python3 -m chaipi.run main.py  -- how ChAIpi starts a custom app: run the file, then its @app.loop."""
import os
import runpy
import sys

from chaipi import app


def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: python3 -m chaipi.run main.py')
    path = os.path.abspath(sys.argv[1])
    sys.path.insert(0, os.path.dirname(path))
    sys.argv = [path] + sys.argv[2:]
    runpy.run_path(path, run_name='__main__')
    if app.fn and not app.running:
        app.run()


if __name__ == '__main__':
    main()
