#!/usr/bin/env python3

###########################################################################
#   main.py  --  This file is part of traderie-bot.                       #
#                                                                         #
#   Copyright (C) 2022 Imanol-Mikel Barba Sabariego                       #
#                                                                         #
#   traderie-bot is free software: you can redistribute it and/or modify  #
#   it under the terms of the GNU General Public License as published     #
#   by the Free Software Foundation, either version 3 of the License,     #
#   or (at your option) any later version.                                #
#                                                                         #
#   traderie-bot is distributed in the hope that it will be useful,       #
#   but WITHOUT ANY WARRANTY; without even the implied warranty           #
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.               #
#   See the GNU General Public License for more details.                  #
#                                                                         #
#   You should have received a copy of the GNU General Public License     #
#   along with this program.  If not, see http://www.gnu.org/licenses/.   #
#                                                                         #
###########################################################################

import argparse
import logging
import signal
import sys

import bot
import log


# Global vars
logger = log.getLogger(__name__)


def signalHandler(signo, stackFrame):
    bot.exitEvent.set()


def main():
    if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 9):
        logger.error("This bot requires at least Python 3.9 to run")
        exit(1)
    signal.signal(signal.SIGINT, signalHandler)
    signal.signal(signal.SIGTERM, signalHandler)
    parser = argparse.ArgumentParser(description="Telegram Traderie D2 Bot!")
    parser.add_argument("--debug", default=False, action="store_true")
    args = parser.parse_args()
    if args.debug:
        log.setSeverity(logging.DEBUG)
        logger.debug("Debug logs enabled")
    bot.start()


if __name__ == "__main__":
    main()
