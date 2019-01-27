#!/usr/bin/env python3
#
# Copyright (C) 2018-2019  Maurice van der Pot <griffon26@kfk4ever.com>
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

import configparser
import gevent
import gevent.queue
import logging
import os

from common.errors import FatalError
from common.logging import set_up_logging
from .authbot import handle_authbot
from .hirezloginserverhandler import handle_hirez_login_server

INI_PATH = os.path.join('data', 'authbot.ini')


def main():
    set_up_logging('authbot.log')
    logger = logging.getLogger(__name__)
    config = configparser.ConfigParser()
    with open(INI_PATH) as f:
        config.read_file(f)

    restart = True
    restart_delay = 10
    tasks = []
    try:
        while restart:
            incoming_queue = gevent.queue.Queue()

            tasks = [
                gevent.spawn(handle_authbot, config['authbot'], incoming_queue),
                gevent.spawn(handle_hirez_login_server, config['authbot'], incoming_queue),
            ]

            # Wait for any of the tasks to terminate
            finished_greenlets = gevent.joinall(tasks, count=1)

            logger.warning('The following greenlets terminated: %s' % ','.join([g.name for g in finished_greenlets]))

            fatal_errors = ['  %s' % g.exception for g in finished_greenlets
                            if isinstance(g.exception, FatalError)]
            if fatal_errors:
                logger.critical('\n' +
                    '\n-------------------------------------------\n' +
                    'The following fatal errors occurred:\n' +
                    '\n'.join(fatal_errors) +
                    '\n-------------------------------------------\n'
                )
                restart = False

            logger.info('Killing all tasks...')
            gevent.killall(tasks)
            logger.info('Waiting %s seconds before %s...' %
                        (restart_delay, ('restarting' if restart else 'exiting')))
            gevent.sleep(restart_delay)

    except KeyboardInterrupt:
        logger.info('Keyboard interrupt received. Exiting...')
        gevent.killall(tasks)
    except Exception:
        logger.exception('Main authbot thread exited with an exception')