#!/usr/bin/env python3
#
# Copyright (C) 2018  Maurice van der Pot <griffon26@kfk4ever.com>
#
# This file is part of taserver
# 
# taserver is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# taserver is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with taserver.  If not, see <http://www.gnu.org/licenses/>.
#

import struct


class TcpMessageReader:
    def __init__(self, socket, max_message_size = 0xFFFF):
        self.socket = socket
        self.max_message_size = max_message_size
        if self.max_message_size > 0xFFFF:
            raise ValueError('max_message_size is not allowed to be greater than 0xFFFF')

    def _recvall(self, size):
        remaining_size = size
        msg = bytes()
        while remaining_size > 0:
            chunk = self.socket.recv(remaining_size)
            if not chunk:
                raise ConnectionResetError()
            remaining_size -= len(chunk)
            msg += chunk
        return msg

    def receive(self):
        packet_size_bytes = self._recvall(2)
        packet_size = struct.unpack('<H', packet_size_bytes)[0]
        if packet_size == 0:
            packet_size = self.max_message_size
        elif packet_size > self.max_message_size:
            raise RuntimeError('Received a packet size that is larger than the TcpMessageReader was created for')

        packet_body_bytes = self._recvall(packet_size)
        if len(packet_body_bytes) != packet_size:
            raise RuntimeError('Received %d bytes, but expected %d. What happened?' %
                               (len(packet_body_bytes), packet_size))
        return packet_body_bytes


class TcpMessageWriter:
    def __init__(self, socket, max_message_size = 0xFFFF):
        self.socket = socket
        self.max_message_size = max_message_size
        if self.max_message_size > 0xFFFF:
            raise ValueError('max_message_size is not allowed to be greater than 0xFFFF')

    def send(self, data):
        size = len(data)
        if size == 0:
            raise ValueError('TcpMessageWriter: Sending empty messages is not allowed')
        if size > self.max_message_size:
            raise ValueError('TcpMessageWriter: Can only send messages up to %d bytes in size' % self.max_message_size)
        size_bytes = struct.pack('<H', size)
        self.socket.sendall(size_bytes + data)

    def close(self):
        self.socket.close()