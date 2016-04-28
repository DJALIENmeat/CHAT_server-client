#!/usr/bin/env python3

import re
import sys
import struct
import socket

class ProtocolError(Exception):
    pass

def safe_recv(sock, buflen):
    buf = bytearray()
    if buflen == 0:
        return buf

    try:
        while len(buf) < buflen:
            new_data = sock.recv(buflen - len(buf))
            if not new_data:
                break

            buf += new_data
    except (BrokenPipeError, OSError, socket.timeout) as e:
        print(e, file=sys.stderr)
        raise ProtocolError(e)

    if len(buf) < buflen:
        raise ProtocolError("connection closed")

    print(buf)

    return buf

def safe_send(sock, buf):
    if type(buf) is str:
        buf = buf.encode("utf8")

    print("send: {}".format(buf))

    try:
        sock.sendall(buf)
    except (BrokenPipeError, OSError, socket.timeout) as e:
        print(e, file=sys.stderr)
        raise ProtocolError(e)

class nettype:

    format = None

    @classmethod
    def recv(cls, sock):
        if not cls.format:
            raise NotImplementedError("type not specified")

        buf = safe_recv(sock, struct.calcsize(cls.format))

        (res,) = struct.unpack(cls.format, buf)

        return cls(res)

    @classmethod
    def read(cls, sock):
        if not cls.format:
            raise NotImplementedError("type not specified")

        buf = fp.read(struct.calcsize(cls.format))

        (res,) = struct.unpack(cls.format, buf)

        return cls(res)

    def __bytes__(self):
        if not self.format:
            raise NotImplementedError("type not specified")

        try:
            return struct.pack(self.format, self)
        except struct.error:
            raise ProtocolError("invalid value for nettype ({})".format(self.__class__.__name__))

    def bytes(self):
        return bytes(self)

    def send(self, sock):
        safe_send(sock, self.bytes())

class varint_t(nettype, int):

    @staticmethod
    def read(fp):
        buf = fp.read(1)

        while buf[0] & 0x80 and len(buf) < 32:
            buf = fp.read(1) + buf

        if len(buf) >= 32:
            raise ProtocolError("varint too long")

        if len(buf) == 1:
            return varint_t(buf[0])
        else:
            n = buf[0] & 0x7f
            for e in buf[1:]:
                n = (n << 7) | (e & 0x7f)

            return varint_t(n)

    @staticmethod
    def recv(sock):
        buf = safe_recv(sock, 1)
        while buf[0] & 0x80 and len(buf) < 32:
            buf = safe_recv(sock, 1) + buf

        if len(buf) >= 32:
            raise ProtocolError("varint too long")

        if len(buf) == 1:
            return varint_t(buf[0])
        else:
            n = buf[0] & 0x7f
            for e in buf[1:]:
                n = (n << 7) & (e & 0x7f)

            return varint_t(n)

    def __bytes__(self):
        length = len(self)
        buf = bytearray(length)
        for i,e in enumerate(buf):
            buf[i] = (self >> (7*i)) & 0x7f
            if i < length-1: buf[i] |= 0x80

        return bytes(buf)

    def __len__(self):
        length = 1
        while self >= (1 << (7*length)):
            length += 1

        return length

class string_t(nettype, str):

    @staticmethod
    def read(fp):
        length = varint_t.read(fp)

        try:
            s = fp.read(length).decode("utf8")
        except UnicodeDecodeError as e:
            print(e, file=sys.stderr)
            raise ProtocolError(e)

        return string_t(s)

    @staticmethod
    def recv(sock):
        length = varint_t.recv(sock)

        try:
            s = safe_recv(sock, length).decode("utf8")
        except UnicodeDecodeError as e:
            print(e, file=sys.stderr)
            raise ProtocolError(e)

        return string_t(s)

    def bytes(self):
        res = self.encode("utf8")
        return bytes(varint_t(len(res))) + res
