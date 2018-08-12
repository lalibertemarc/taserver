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

from common.messages import Login2LauncherSetPlayerLoadoutsMessage


class ServerInfo:
    def __init__(self, first_id, second_id, ip, queue):
        self.serverid1 = first_id
        self.serverid2 = second_id
        self.ip = ip
        self.port = None
        self.description = None
        self.motd = None
        self.playerbeingkicked = None
        self.joinable = False
        self.queue = queue

    def set_info(self, port, description, motd):
        self.port = port
        self.description = description
        self.motd = motd
        self.joinable = True

    def player_loadouts_changed(self, player):
        # TODO: Instead of using the player ID determined from the greenlet, use a generated
        # player ID that is also communicated to the client through enumfield m0348. At the
        # moment though, all those IDs are coming from
        msg = Login2LauncherSetPlayerLoadoutsMessage(player.id, player.loadout.loadout_dict)
        self.queue.put(msg)

