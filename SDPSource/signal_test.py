#!/usr/bin/python3
import signal
import time

def main():
    def signal_func(sig, stack):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, signal_func)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('KeyboardInterrupt')

if __name__ == '__main__':
    main()