###########################################################################
#   blocklist.py  --  This file is part of traderie-bot.                  #
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

import re
from typing import Optional


blocklist = [
    "ClassicZon#4104",
    "HTTPS://DISCORD.GG/MagicFinder"
]


def assholeBlocklist(msg: str) -> Optional[str]:
    for word in blocklist:
        if re.search('\\s*'.join([c for c in word.lower()]), msg.lower()) is not None:
            return re.search('\\s*'.join([c for c in word.lower()]), msg.lower()).group(0)
