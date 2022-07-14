###########################################################################
#   dclone.py  --  This file is part of traderie-bot.                     #
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

from typing import Dict, Optional
import json
import requests
import traceback
import urllib3

import log

# Constants
DCLONE_STATUS = {
    1: "(1/6): Terror gazes upon Sanctuary",
    2: "(2/6): Terror approaches Sanctuary",
    3: "(3/6): Terror begins to form within Sanctuary",
    4: "(4/6): Terror spreads across Sanctuary",
    5: "(5/6): Terror is about to be unleashed upon Sanctuary.",
    6: "(6/6): Terror has invaded Sanctuary",
}
DCLONE_DIABLO2_IO_UA = 'trades Telegram bot (ibarba)'


class DcloneTracker():
    headers: Dict[str, str]
    url: str

    def __init__(self, baseURL: str, headers: Dict[str, str]):
        self.url = baseURL
        self.headers = headers

    def getData(self, softcore: bool, ladder: bool) -> Optional[Dict[str, int]]:
        pass


# Global vars
logger = log.getLogger(__name__)
DcloneTracker1 = DcloneTracker(
    "https://d2runewizard.com/api/diablo-clone-progress/", {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36',
    }
)
DcloneTracker2 = DcloneTracker(
    "https://diablo2.io/dclone_api.php", {
        'User-Agent': DCLONE_DIABLO2_IO_UA,
    }
)


def getDcloneStatusTracker1(self: DcloneTracker, softcore: bool, ladder: bool) -> Optional[Dict[str, int]]:
    status = {}
    effectiveURL = self.url
    if softcore and ladder:
        effectiveURL += "/ladder/softcore"
    elif softcore and not ladder:
        effectiveURL += "/nonLadder/softcore"
    elif not softcore and ladder:
        effectiveURL += "/ladder/hardcore"
    elif not softcore and not ladder:
        effectiveURL += "/nonLadder/hardcore"

    try:
        response = requests.get(effectiveURL, headers=self.headers)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to get dclone status: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return None
    if response.status_code != 200:
        logger.error(f"Failed to get dclone status: Request returned code {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return None

    data = json.loads(response.text)
    if data.get("servers") is None or (not isinstance(data.get("servers"), list)):
        logger.error("Invalid JSON data from dclone call")
        logger.debug(f"Raw response: {response.text}")
        return None
    serverList = data.get("servers")
    for server in serverList:
        if server.get("server").endswith("Asia"):
            status["Asia"] = server.get("progress")
        elif server.get("server").endswith("Americas"):
            status["Americas"] = server.get("progress")
        elif server.get("server").endswith("Europe"):
            status["Europe"] = server.get("progress")
    return status


DcloneTracker1.getData = getDcloneStatusTracker1


def getDcloneStatusTracker2(self: DcloneTracker, softcore: bool, ladder: bool) -> Optional[Dict[str, int]]:
    status = {}
    params = {'ladder': 1 if ladder else 2, 'hc': 1 if not softcore else 2}
    try:
        response = requests.get(self.url, params=params, headers=self.headers)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to get dclone status: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return None
    if response.status_code != 200:
        logger.error(f"Failed to get dclone status: Request returned code {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return None

    try:
        data = json.loads(response.text)
    except json.JSONDecodeError:
        logger.error("Unable to decode JSON data from API")
        logger.debug(f"Raw data: {response.text}")
        return None
    if not isinstance(data, list):
        logger.error("Invalid JSON data from dclone call")
        logger.debug(f"Raw response: {response.text}")
        return None
    for server in data:
        if server.get("region") == "1":
            status["Americas"] = int(server.get("progress"))
        elif server.get("region") == "2":
            status["Europe"] = int(server.get("progress"))
        elif server.get("region") == "3":
            status["Asia"] = int(server.get("progress"))
    return status


DcloneTracker2.getData = getDcloneStatusTracker2


def getDcloneStatus(softcore: bool, ladder: bool) -> Optional[Dict[str, str]]:
    return DcloneTracker2.getData(DcloneTracker2, softcore, ladder)
