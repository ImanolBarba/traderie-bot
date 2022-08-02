###########################################################################
#   blocklist_test.py  --  This file is part of traderie-bot.             #
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

import blocklist


class TestBlocklist(unittest.TestCase):
    def testRelistable(self):
        blocklist.blocklist = ["teststring", "verybaduser"]
        cases = [
            (
                "teststring",
                "teststring"
            ),
            (
                "teststrin",
                None
            ),
            (
                "very bad user",
                "very bad user",
            ),
            (
                """
                v e r     y b
                a
                d us
                e                r
                """,
                """v e r     y b
                a
                d us
                e                r"""
            ),
            (
                "very🅱️aduser",
                None
            ),
            (
                "some random fucking text, and then v e r y  b a d  u s e r and some more trailing crap",
                "v e r y  b a d  u s e r"
            ),
        ]

        for c in cases:
            res = blocklist.assholeBlocklist(c[0])
            self.assertEqual(res, c[1], f"returned {res}, expected {c[1]}\ncase #{c[0]}")


if __name__ == '__main__':
    unittest.main()
