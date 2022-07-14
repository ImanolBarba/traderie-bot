###########################################################################
#   lru_test.py  --  This file is part of traderie-bot.                   #
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

import unittest

import lru


class TestLRU(unittest.TestCase):
    def testPutAndGet(self):
        cache = lru.LRUCache(10)
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        self.assertEqual(cache.numItems(), 2)
        self.assertEqual(cache.get("key1"), "value1")
        self.assertEqual(cache.get("key2"), "value2")
        self.assertEqual(cache.get("key3"), None)

        cache.put("key1", "value3")
        self.assertEqual(cache.numItems(), 2)
        self.assertEqual(cache.get("key1"), "value3")

    def testEvict(self):
        cache = lru.LRUCache(5)
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.evict("key1")
        self.assertEqual(cache.numItems(), 1)
        self.assertEqual(cache.get("key1"), None)
        self.assertEqual(cache.get("key2"), "value2")

        cache.evict("key3")
        self.assertEqual(cache.numItems(), 1)
        self.assertEqual(cache.get("key2"), "value2")

        cache.put("key1", "value1")
        cache.put("key3", "value3")
        cache.put("key4", "value4")
        cache.put("key5", "value5")
        cache.put("key6", "value6")
        self.assertEqual(cache.get("key1"), "value1")
        self.assertEqual(cache.get("key2"), None)
        self.assertEqual(cache.get("key3"), "value3")
        self.assertEqual(cache.get("key4"), "value4")
        self.assertEqual(cache.get("key5"), "value5")
        self.assertEqual(cache.get("key6"), "value6")
        self.assertEqual(cache.numItems(), 5)

    def testCache(self):
        cache = lru.LRUCache(5)
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")
        cache.put("key1", "value4")
        self.assertEqual(cache.numItems(), 3)
        self.assertEqual(cache.get("key1"), "value4")
        self.assertEqual(cache.get("key2"), "value2")
        self.assertEqual(cache.get("key3"), "value3")

        self.assertEqual(cache.itemList[0], "key1")
        self.assertEqual(cache.itemList[1], "key3")
        self.assertEqual(cache.itemList[2], "key2")


if __name__ == '__main__':
    unittest.main()
