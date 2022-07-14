###########################################################################
#   lru.py  --  This file is part of traderie-bot.                        #
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

from typing import Optional

import log

logger = log.getLogger(__name__)


class LRUCache:
    data = {}
    itemList = []
    length = 0

    def __init__(self, length):
        self.length = length
        self.data = {}
        self.itemList = []

    def get(self, key: str) -> Optional[str]:
        return self.data.get(key)

    def numItems(self) -> int:
        return len(self.itemList)

    def put(self, key: str, value: str) -> None:
        if key in self.data:
            for i in range(len(self.itemList)):
                if self.itemList[i] == key:
                    del self.itemList[i]
                    self.itemList.insert(0, key)
                    self.data[key] = value
                    return
            logger.error("Inconsistency between cache map and list")
        else:
            self.itemList.insert(0, key)
            self.data[key] = value
            for evictedKey in self.itemList[self.length:]:
                del self.data[evictedKey]
            self.itemList = self.itemList[:self.length]

    def evict(self, key: str) -> None:
        if key in self.data:
            for i in range(len(self.itemList)):
                if self.itemList[i] == key:
                    del self.itemList[i]
                    del self.data[key]
                    return
        else:
            logger.warning(f"Asked to evict key {key}, which is not cached")
