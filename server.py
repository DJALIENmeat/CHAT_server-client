#!/usr/bin/env python3

import socket
import threading
import time
import logging
import sys
from util import safe_send, string_t

HOST = ''
PORT = 8031
TIMEOUT = 20
BUF_SIZE = 1024

class WhatsUpAccount():
    def __init__(self, conn, name, password):
        self.name = name
        self.password = password
        self.last_login = None
        self.mentions = []
        self.connection = conn

    def mention(self, src_account, msg):
        self.mentions.append((
            src_account, msg, False
        ))

    def iter_mentions(self):
        for mention in self.mentions:
            acct, msg, has_read = mention
            if has_read:
                yield '      {}: {}'.format(acct.name, msg)
            else:
                yield '(NEW) {}: {}'.format(acct.name, msg)

            mention = (acct, msg, True)

    def __eq__(self, other):
        return self.name == other.name

    def __bool__(self):
        return self.connection != None


class WhatsUpConnection(threading.Thread):
    def __init__(self, server, conn, addr):
        threading.Thread.__init__(self)
        self.server = server
        self.conn = conn
        self.addr = addr
        self.ip = self.addr[0]
        self.account = None

        logging.info('Connected from: %s:%s' %
                     (self.addr[0], self.addr[1]))

    def print_indicator(self, prompt):
        string_t("{0}\n>> ".format(prompt)).send(self.conn)

    def login(self):
        global name
        msg = '\n## Welcome to WhatsUp\n## Enter `!q` to quit\n'

        # new user
        if self.ip not in self.server.accounts:
            msg += 'Please enter your name: '
            self.print_indicator(msg)
            while 1:
                name = string_t.recv(self.conn).strip()
                if name in messages:
                    self.print_indicator(
                        'This name already exists, please try another!')
                else:
                    break

            self.print_indicator(
                'Hello %s, please enter your password:' % (self.name,))
            password = string_t.recv(self.conn).strip()

            self.account = WhatsUpAccount(self, name, password)
            self.account.last_login = time.ctime()
            self.server.accounts[self.ip] = self.account

            self.print_indicator('## Welcome, enjoy your chat')
            logging.info('%s logged as %s' % (self.addr[0], self.name))
        else:
            self.account = self.server.accounts[self.ip]
            msg += '## Hello %s, please enter your password:' % (self.name,)
            # print accounts
            self.print_indicator(msg)
            while 1:
                password = string_t.recv(self.conn).strip()
                if password != accounts[self.ip]['pass']:
                    self.print_indicator(
                        '## Incorrect password, please enter again')
                else:
                    self.print_indicator(
                        '## Welcome back, last login: %s' %
                        (self.account.last_login,))
                    self.account.last_login = time.ctime()
                    break

            mentions = "\n".join(list(self.account.iter_mentions())) + "\n"
            string_t(mentions).send(self.conn)

        self.server.broadcast('`%s` is online now' % (self.name,))

    def logout(self):
        string_t("## Bye!\n").send(self.conn)
        self.server.broadcast("## `{}` is offline now".format(self.name))
        self.account = None
        self.conn.close()

    def check_keyword(self, buf):

        if buf.find('!q') == 0:
            self.logout()

        if buf.find('#') == 0:
            group_keyword = buf.split(' ')[0][1:]
            group_component = group_keyword.split(':')

            # to post in a group
            if len(group_component) == 1:
                group_name = group_component[0]
                try:
                    msg = '[%s]%s: %s' % (
                        group_name, self.name, buf.split(' ', 1)[1])
                    self.group_post(group_name, msg)
                except IndexError:
                    self.print_indicator(
                        '## What do you want to do with `#%s`?' % (group_name))

            # to join / leave a group
            elif len(group_component) == 2:
                group_name = group_component[0]
                if group_component[1] == 'join':
                    self.group_join(group_name)
                elif group_component[1] == 'leave':
                    self.group_leave(group_name)
            return True

        if buf.find('@') == 0:
            to_user = buf.split(' ')[0][1:]
            from_user = self.name
            msg = buf.split(' ', 1)[1]

            # if user is online
            if to_user in self.logged_in:
                string_t('@%s: %s\n>> ' % (from_user, msg)).send(self.logged_in[to_user])
                self.mention(from_user, to_user, msg, 1)
            # offline
            else:
                self.mention(from_user, to_user, msg)
            return True

    def run(self):
        self.login()
        self.conn.settimeout(TIMEOUT)

        try:
            while 1:
                buf = string_t.recv(self.conn).strip()
                logging.info('%s@%s: %s' % (self.name, self.addr[0], buf))
                # check features
                if not self.check_keyword(buf):
                    # client broadcasts message to all
                    self.broadcast('%s: %s' % (self.name, buf), self.logged_in)
                else:
                    string_t("").send(self.conn)

        except KeyboardInterrupt:
            print('Quited')
            sys.exit(0)
        except Exception as e:
            # timed out
            pass

    def __bool__(self):
        return self.account != None


class WhatsUpServer(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

        self.sock = None
        self.name = ''

        self.clients = []
        self.accounts = {}
        self.groups = {}

        self.logged_in = {}

    # def logoff(self):
    #     global clients
    #     string_t('## Bye!\n').send(self.conn)
    #     del self.logged_in[self.name]
    #     clients.remove((self.conn, self.addr))
    #     if self.logged_in:
    #         self.broadcast('## `%s` is offline now' %
    #                        (self.name,), self.logged_in)
    #     self.conn.close()
    #     exit()

    def group_post(self, acct, group_name, msg):
        # if the group does not exist, create it
        self.groups.setdefault(group_name, set())

        # if current user is a member of the group
        if acct in groups[group_name]:
            self.broadcast(msg, groups[group_name])
        else:
            acct.print_indicator(
                '## You are current not a member of group `%s`' % (group_name,))

    def group_join(self, acct, group_name):
        self.groups.setdefault(group_name, set())

        if acct not in self.groups[group_name]:
            self.groups[group_name].add(acct)
            self.print_indicator('## You have joined the group `%s`' %
                                 (group_name,))

    def group_leave(self, acct, group_name):
        if acct in groups[group_name]:
            groups[group_name].remove(acct)
            self.print_indicator('## You have left the group `%s`' %
                                 (group_name,))

    def broadcast(self, msg, receivers=None, to_self=True):
        if not receivers: receivers = self.accounts

        for ip, acct in receivers.items():
            # if the client is not the current user
            # if ip != self.ip:
            string_t(msg + '\n>> ').send(acct.connection.conn)
            # if current user
            # elif to_self:
            #    string_t('{}\n>> '.format(msg)).send(self.conn)

        print("end broadcast")

    def run(self):
        print('-= WhatsUp Server =-')
        print('>> Listening on:'), PORT
        print(PORT)

        # set up socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((HOST, PORT))
        self.sock.listen(5)

        while 1:
            print("in loop before accept")
            sock, addr = self.sock.accept()
            print("in loop after accept")
            conn = WhatsUpConnection(self, sock, addr)
            self.clients.append(conn)
            conn.start()


def main():
    global clients
    global messages
    global accounts
    global groups

    # logging setup
    logging.basicConfig(level=logging.INFO,
                        format='[%(asctime)s] %(levelname)s: %(message)s',
                        datefmt='%d/%m/%Y %I:%M:%S %p')

    # initialize global vars
    clients = set()
    messages = {}
    accounts = {}
    groups = {}

    server = WhatsUpServer()
    server.start()


if __name__ == '__main__':
    main()
