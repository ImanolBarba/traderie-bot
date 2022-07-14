###########################################################################
#   traderie_test.py  --  This file is part of traderie-bot.              #
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

import datetime
import unittest
from unittest import mock

import traderie


class MockDatetime(datetime.datetime):
    fake_now = None

    @classmethod
    def now(self, param):
        return self.fake_now


class TestIsRelistable(unittest.TestCase):
    @mock.patch('traderie.datetime.datetime', MockDatetime)
    def testRelistable(self):
        MockDatetime.fake_now = datetime.datetime(
            day=27,
            month=3,
            year=2022,
            hour=21,
            minute=30,
            second=1,
            microsecond=0,
            tzinfo=datetime.timezone.utc
        )

        cases = [
            (
                traderie.Listing(
                    listingID=1,
                    updated="2022-02-21T23:11:02.503Z",
                    price=[["Asking Price"]],
                ),
                True
            ),
            (
                traderie.Listing(
                    listingID=2,
                    updated="2022-03-26T21:30:00.000Z",
                    price=[["Asking Price"]],
                ),
                True
            ),
            (
                traderie.Listing(
                    listingID=3,
                    updated="2022-03-26T21:30:00.999Z",
                    price=[["Asking Price"]],
                ),
                True
            ),
            (
                traderie.Listing(
                    listingID=4,
                    updated="2022-03-26T21:30:01.000Z",
                    price=[["Asking Price"]],
                ),
                False
            ),
            (
                traderie.Listing(
                    listingID=5,
                    updated="2022-03-26T21:30:01.001Z",
                    price=[["Asking Price"]],
                ),
                False
            ),
            (
                traderie.Listing(
                    listingID=6,
                    updated="2022-03-26T21:31:00.000Z",
                    price=[["Asking Price"]],
                ),
                False
            ),
            (
                traderie.Listing(
                    listingID=7,
                    updated="2022-03-27T21:30:01.001Z",
                    price=[["Asking Price"]],
                ),
                False
            ),
            (
                traderie.Listing(
                    listingID=8,
                    updated="2022-03-28T21:30:01.001Z",
                    price=[["Asking Price"]],
                ),
                False
            ),
            (
                traderie.Listing(
                    listingID=9,
                    updated="2023-03-28T21:30:01.001Z",
                    price=[["Asking Price"]],
                ),
                False
            ),
        ]

        for c in cases:
            res = traderie.isListingRelistable(c[0])
            self.assertEqual(res, c[1], f"returned {res}, expected {c[1]}\ncase #{c[0].listingID}")


if __name__ == '__main__':
    unittest.main()
