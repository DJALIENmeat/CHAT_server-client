import socket
import time
import logging
import sys

HOST = '127.0.0.1'
PORT = 8018
TIMEOUT = 5
BUF_SIZE = 1024

try:
    input = raw_input
except NameError:
    pass

from util import string_t, safe_send

class WhatsUpClient():

    def __init__(self, host=HOST, port=PORT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        logging.info('Connecting to %s:%s' % (host, port))

        try:
            while 1:
                buf = string_t.recv(self.sock)
                sys.stdout.write(buf)
                cmd = input()
                if cmd.strip() == '!q':
                    sys.exit(1)
                string_t(cmd).send(self.sock)

        finally:
            self.sock.close()

    def run(self):
        pass


def main():
    logging.basicConfig(level=logging.INFO,
                        format='[%(asctime)s] %(levelname)s: %(message)s',
                        datefmt='%d/%m/%Y %I:%M:%S %p')
    client = WhatsUpClient()

if __name__ == '__main__':
    main()
