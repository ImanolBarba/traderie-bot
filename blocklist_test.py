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
                """teststring""",
                True
            ),
            (
                """teststrin""",
                False
            ),
            (
                """very bad user""",
                True
            ),
            (
                """
                v e r     y b
                a
                d us
                e                r
                """,
                True
            ),
            (
                """very🅱️aduser""",
                False
            ),
        ]

        for c in cases:
            res = blocklist.assholeBlocklist(c[0])
            if not c[1]:
                self.assertIsNone(res, f"returned {res}, expected None\ncase #{c[0]}")
            else:
                self.assertEqual(res, c[0].strip(), f"returned {res}, expected {c[0]}\ncase #{c[0]}")


if __name__ == '__main__':
    unittest.main()
