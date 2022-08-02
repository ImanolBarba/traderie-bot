###########################################################################
#   traderie.py  --  This file is part of traderie-bot.                   #
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

from dataclasses import dataclass
import datetime
import json
import traceback
from typing import Dict, List, Optional
import urllib3

import requests

import dateutil.parser

import log


@dataclass
class ListingProperty:
    id: str
    name: str
    value: str


@dataclass
class Listing:
    listingID: int
    updated: str
    price: List[List[str]]
    properties: Dict[str, ListingProperty]


@dataclass
class Notification:
    notificationID: str
    text: str
    date: str
    fromUserID: Optional[int]
    listingID: Optional[int]


@dataclass
class Message:
    msgID: str
    text: str
    fromID: int
    toID: int


@dataclass
class Conversation:
    conversationID: int
    userID: int


@dataclass
class Offer:
    itemName: str
    offerID: int
    listingID: int
    sellerID: int
    sellerUsername: str
    buyerID: int
    buyerUsername: str
    offer: List[List[str]]
    amount: int
    itemID: int


# Constants
LISTINGS_PER_PAGE = 50


# Global vars
logger = log.getLogger(__name__)
httpHeaders = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36',
    'accept': 'application/json',
    'authorization': '',
    'Content-Type': 'application/json; charset=utf-8'
}


def isListingRelistable(listing: Listing) -> bool:
    return (datetime.datetime.now(datetime.timezone.utc) - dateutil.parser.isoparse(listing.updated)) > datetime.timedelta(days=1)


def getStatus(user: int) -> str:
    params = {'user': user}
    try:
        response = requests.get("https://traderie.com/api/diablo2resurrected/accounts", params=params, headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to get user status: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return None
    if response.status_code != 200:
        logger.error(f"Failed to get user status: Request returned code {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return None

    data = json.loads(response.text)
    if data.get("user") is None or data.get("user").get("status") is None:
        logger.error("Invalid JSON data from status call")
        logger.debug(f"Raw response: {response.text}")
        return None
    return data.get("user").get("status")


def setStatus(newStatus: str) -> Optional[str]:
    params = {'status': newStatus}
    try:
        response = requests.put("https://traderie.com/api/diablo2resurrected/accounts/update", data=json.dumps(params), headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to set status {newStatus}: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return f"Failed to set status {newStatus}: {str(e)}"
    if response.status_code != 200:
        logger.error(f"Failed to set status {newStatus} {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return f"Failed to set status {newStatus}: API returned error {response.status_code}"

    data = json.loads(response.text)
    if data.get("msg") is None:
        if data.get("error") is None:
            logger.error("Invalid JSON data from status set call")
            logger.debug(f"Raw response: {response.text}")
            return f"Failed to set status {newStatus}: API returned unexpected response"
        else:
            logger.error(f"Error setting status: {data.get('error')}")
            return f"Failed to set status {newStatus}: {data.get('error')}"
    if data.get("msg") != "success":
        return f"Unexpected message when setting new status {newStatus}: {data.get('msg')}"
    return None


def getNotifications(new: bool, limit: int) -> Optional[List[Notification]]:
    ret = []
    params = {'limit': limit}
    if new:
        params['new'] = ''
    try:
        response = requests.get("https://traderie.com/api/diablo2resurrected/notifications", params=params, headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to get notifications: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return None
    if response.status_code != 200:
        logger.error(f"Failed to get notifications: Request returned code {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return None

    data = json.loads(response.text)
    if data.get("notifications") is None:
        logger.error("Invalid JSON data from notifications call")
        logger.debug(f"Raw response: {response.text}")
        return None
    for notification in data.get("notifications"):
        try:
            n = Notification(
                text=notification["message"],
                date=notification["created_at"],
                notificationID=notification["id"],
                fromUserID=int(notification.get("from_user_id")),
                listingID=None,
            )
            if notification.get("data") is not None and notification.get("data").get("listing_id") is not None:
                n.listingID = int(notification["data"]["listing_id"])
            ret.append(n)
        except KeyError:
            logger.error("Some notification is missing the message or date field")
            logger.debug(f"Raw notification: {notification}")
    return ret


def getConversations(active: bool, ownUserID: int) -> Optional[Dict[int, Conversation]]:
    ret = {}
    params = {'active': 'true' if active else 'false'}
    try:
        response = requests.get("https://traderie.com/api/diablo2resurrected/conversations", params=params, headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to get conversations: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return None
    if response.status_code != 200:
        logger.error(f"Failed to get conversations: Request returned code {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return None

    data = json.loads(response.text)
    if data.get("conversations") is None:
        logger.error("Invalid JSON data from conversations call")
        logger.debug(f"Raw response: {response.text}")
        return None
    for convo in data.get("conversations"):
        partnerUserID = 0
        if convo.get("users") is None:
            logger.error("Invalid JSON data from conversations call")
            logger.debug(f"Raw response: {response.text}")
            return None
        for userID in convo.get("users"):
            if int(userID) != ownUserID:
                partnerUserID = int(userID)
                break
        try:
            ret[partnerUserID] = Conversation(conversationID=int(convo["id"]), userID=int(partnerUserID))
        except KeyError:
            logger.error("Some conversation is missing a required field")
            logger.debug(f"Raw message: {convo}")
    return ret


def getMessages(fromUserID: int, limit: int, conversationID: int) -> Optional[List[Message]]:
    ret = []
    params = {'user': fromUserID, 'limit': limit, 'convoId': conversationID}
    try:
        response = requests.get("https://traderie.com/api/diablo2resurrected/messages", params=params, headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to get messages: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return None
    if response.status_code != 200:
        logger.error(f"Failed to get messages: Request returned code {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return None

    data = json.loads(response.text)
    if data.get("messages") is None:
        logger.error("Invalid JSON data from messages call")
        logger.debug(f"Raw response: {response.text}")
        return None
    for message in data.get("messages"):
        try:
            m = Message(text=message["content"], msgID=message["id"], toID=int(message["to"]), fromID=int(message["from"]))
            ret.append(m)
        except KeyError:
            logger.error("Some message is missing a required field")
            logger.debug(f"Raw message: {message}")
    return ret


def getItemsFromOfferPrices(prices: List[Dict[str, str]]) -> List[List[str]]:
    groups = {}
    items = []
    for price in prices:
        groupItems = groups.get(price["group"], [])
        groupItems.append(f'{price["quantity"]}x {price["name"]}')
        groups[price["group"]] = groupItems
    for group in groups:
        items.append(groups[group])
    return items


def getOffers(toSellerID: Optional[int] = None, fromUserID: Optional[int] = None) -> Optional[Dict[int, Offer]]:
    if toSellerID is None and fromUserID is None:
        logger.error("No parameters specified for getOffers")
        return None
    if toSellerID is not None and fromUserID is not None:
        logger.error("Can't specify both parameters for getOffers")
        return None

    ret = {}
    params = {}
    if toSellerID is not None:
        params = {'accepted': 'open', 'seller': toSellerID}
    else:
        params = {'accepted': 'open', 'user': fromUserID}
    try:
        response = requests.get("https://traderie.com/api/diablo2resurrected/offers", params=params, headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to get offers: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return None
    if response.status_code != 200:
        logger.error(f"Failed to get offers: Request returned code {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return None

    data = json.loads(response.text)
    if data.get("offers") is None:
        logger.error("Invalid JSON data from offers call")
        logger.debug(f"Raw response: {response.text}")
        return None
    for offer in data.get("offers"):
        try:
            items = [["Asking price"]]
            if offer["prices"] is not None:
                items = getItemsFromOfferPrices(offer["prices"])
            o = Offer(
                itemName=offer["listing"]["item"].get("name"),
                offerID=int(offer["id"]),
                listingID=int(offer["listing"].get("id")),
                buyerID=int(offer["buyer"].get("id")),
                sellerID=int(offer["listing"]["seller"].get("id")),
                buyerUsername=offer["buyer"].get("username"),
                sellerUsername=offer["listing"]["seller"].get("username"),
                offer=items,
                itemID=int(offer["listing"]["item"].get("id")),
                amount=int(offer["listing"].get("amount"))
            )
            ret[o.offerID] = o
        except KeyError:
            logger.error("Some offer is missing a required field")
            logger.debug(f"Raw offer: {offer}")
    return ret


def relistItem(listingID: int) -> Optional[str]:
    params = {'listing': str(listingID)}
    try:
        response = requests.put("https://traderie.com/api/diablo2resurrected/listings/refresh", data=json.dumps(params), headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to relist item {listingID}: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return f"Failed to relist item {listingID}: {str(e)}"
    if response.status_code != 200:
        logger.error(f"Failed to relist item {listingID} {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return f"Failed to relist item{listingID}: API returned error {response.status_code}"

    data = json.loads(response.text)
    if data.get("msg") is None:
        if data.get("error") is None:
            logger.error("Invalid JSON data from notifications call")
            logger.debug(f"Raw response: {response.text}")
            return f"Failed to relist item {listingID}: API returned unexpected response"
        else:
            logger.error(f"Error listing item: {data.get('error')}")
            return f"Failed to relist item {listingID}: {data.get('error')}"
    if data.get("msg") != "success":
        return f"Unexpected message when relisting {listingID}: {data.get('msg')}"
    return None


def parseListingProperty(propJSONData) -> Optional[ListingProperty]:
    prop = ListingProperty(id=propJSONData.get("id"), name=propJSONData.get("property"), value="")
    if propJSONData.get("type") == "string":
        prop.value = propJSONData.get("string")
    elif propJSONData.get("type") == "number":
        prop.value = str(propJSONData.get("number"))
    elif propJSONData.get("type") == "bool":
        prop.value = str(propJSONData.get("bool"))
    else:
        logger.error(f"Unrecognised property type: {propJSONData.get('type')}")
        return None
    return prop


def parseListing(listingJSONData) -> Optional[Listing]:
    try:
        items = [["Make an Offer"]] if listingJSONData["make_offer"] else [["Free"]]
        if listingJSONData["prices"] is not None:
            items = getItemsFromOfferPrices(listingJSONData["prices"])
        lst = Listing(listingID=int(listingJSONData["id"]), updated=listingJSONData["updated_at"], price=items, properties={})
        if listingJSONData.get("properties") is not None:
            for prop in listingJSONData["properties"]:
                parsedProp = parseListingProperty(prop)
                if parsedProp is not None:
                    lst.properties[parsedProp.name] = parsedProp
        return lst
    except KeyError:
        logger.error("Some listing is missing the message or date field")
        logger.debug(f"Raw listing: {listingJSONData}")
    return None


def getListings(seller: int, page: int, includeCompleted: bool) -> Optional[Dict[int, Listing]]:
    ret = {}
    params = {
        'selling': 'true',
        'auction': 'false',
        'page': str(page),
        'seller': str(seller),
        'completed': 'all' if includeCompleted else 'false',
        'active': 'all',
    }
    try:
        response = requests.get("https://traderie.com/api/diablo2resurrected/listings", params=params, headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to get listings: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return None
    if response.status_code != 200:
        logger.error(f"Failed to get listings: Request returned code {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return None

    data = json.loads(response.text)
    if data.get("listings") is None:
        logger.error("Invalid JSON data from listings call")
        logger.debug(f"Raw response: {response.text}")
        return None
    for listing in data.get("listings"):
        lst = parseListing(listing)
        if lst is not None:
            ret[lst.listingID] = lst
    return ret


def getListing(listingID: int) -> Optional[Listing]:
    params = {
        'selling': 'true',
        'completed': 'all',
        'active': 'all',
        'id': listingID,
    }
    try:
        response = requests.get("https://traderie.com/api/diablo2resurrected/listings", params=params, headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to get listings: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return None
    if response.status_code != 200:
        logger.error(f"Failed to get listings: Request returned code {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return None

    data = json.loads(response.text)
    if data.get("listings") is None:
        logger.error("Invalid JSON data from listings call")
        logger.debug(f"Raw response: {response.text}")
        return None
    if len(data["listings"]) > 1:
        logger.error(f"More than one listing returned for specified ID: {listingID}")
        return None
    return parseListing(data["listings"][0])


def getAllListings(seller: int, includeCompleted: bool = False) -> Optional[Dict[int, Listing]]:
    listings = {}
    currentPage = 0
    lastPage = False
    while not lastPage:
        pagedListings = getListings(seller, currentPage, includeCompleted)
        if pagedListings is None:
            return None
        listings |= pagedListings
        if len(pagedListings) != LISTINGS_PER_PAGE:
            lastPage = True
        currentPage += 1
    return listings


def markNewNotificationsAsRead(newNotif: List[Notification]) -> Optional[str]:
    params = {'newNotifications': list(map(lambda x: x.notificationID, newNotif))}
    try:
        response = requests.put("https://traderie.com/api/diablo2resurrected/notifications/read", data=json.dumps(params), headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to mark notifications as read: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return f"Failed to mark notifications as read: {str(e)}"
    if response.status_code != 200:
        logger.error(f"Failed to mark notifications as read {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return f"Failed to mark notifications as read: API returned error {response.status_code}"

    data = json.loads(response.text)
    if data.get("success") is None:
        if data.get("error") is None:
            logger.error("Invalid JSON data from read notifications call")
            logger.debug(f"Raw response: {response.text}")
            return "Failed to mark notifications as read: API returned unexpected response"
        else:
            logger.error(f"Failed to mark notifications as read: {data.get('error')}")
            return f"Failed to mark notifications as read: {data.get('error')}"
    if data.get("success") is not True:
        return "Unsuccessful while trying to read notifications"
    return None


def declineOffer(offerID: int, buyerID: int, listingID: int, reason: str = "the offer was too low") -> Optional[str]:
    params = {'offer': offerID, 'buyer': str(buyerID), 'listing': listingID, 'reason': reason}
    try:
        response = requests.put("https://traderie.com/api/diablo2resurrected/offers/deny", data=json.dumps(params), headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to decline offer: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return f"Failed to decline offer: {str(e)}"
    if response.status_code != 200:
        logger.error(f"Failed to decline offer {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return f"Failed to decline offer: API returned error {response.status_code}"

    data = json.loads(response.text)
    if data.get("success") is None:
        if data.get("error") is None:
            logger.error("Invalid JSON data from decline offer call")
            logger.debug(f"Raw response: {response.text}")
            return "Failed to decline offer: API returned unexpected response"
        else:
            logger.error(f"Failed to decline offer: {data.get('error')}")
            return f"Failed to decline offer: {data.get('error')}"
    if data.get("success") is not True:
        return "Unsuccessful while trying to decline offer"
    return None


def acceptOffer(offerID: int, buyerID: int, listingID: int, amount: int, itemID: int, isAuction: bool = False, parentUser: Optional[int] = None, offerAmount: Optional[int] = None) -> Optional[str]:
    params = {
        'offer': offerID,
        'parent_user': parentUser,
        'buyer': buyerID,
        'listing': listingID,
        'amount': amount,
        'item': itemID,
        'isAuction': isAuction,
        'offerAmount': offerAmount
    }
    try:
        response = requests.put("https://traderie.com/api/diablo2resurrected/offers/accept", data=json.dumps(params), headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to accept offer: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return f"Failed to accept offer: {str(e)}"
    if response.status_code != 200:
        logger.error(f"Failed to accept offer {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return f"Failed to accept offer: API returned error {response.status_code}"

    data = json.loads(response.text)
    if data.get("success") is None:
        if data.get("error") is None:
            logger.error("Invalid JSON data from accept offer call")
            logger.debug(f"Raw response: {response.text}")
            return "Failed to accept offer: API returned unexpected response"
        else:
            logger.error(f"Failed to accept offer: {data.get('error')}")
            return f"Failed to accept offer: {data.get('error')}"
    if data.get("success") is not True:
        return "Unsuccessful while trying to accept offer"
    return None


def sendMessage(userID: int, message: str) -> Optional[str]:
    params = {
        'body': {
            'to': str(userID),
            'content': message,
        }
    }
    try:
        response = requests.post("https://traderie.com/api/diablo2resurrected/messages", data=json.dumps(params), headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to send message: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return f"Failed to send message: {str(e)}"
    if response.status_code != 200:
        logger.error(f"Failed to send message {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return f"Failed to send message: API returned error {response.status_code}"

    data = json.loads(response.text)
    if data.get("msg") is None:
        if data.get("error") is None:
            logger.error("Invalid JSON data from send message call")
            logger.debug(f"Raw response: {response.text}")
            return "Failed to send message: API returned unexpected response"
        else:
            logger.error(f"Failed to send message: {data.get('error')}")
            return f"Failed to send message: {data.get('error')}"
    if data.get("msg") != "success":
        return "Unsuccessful while trying to send message"
    return None


def openConversation(userID: int, username: str, offerID: int) -> Optional[str]:
    params = {
        'to': str(userID),
        'toUsername': username,
        'offer': offerID,
    }
    try:
        response = requests.post("https://traderie.com/api/diablo2resurrected/conversations", data=json.dumps(params), headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to open conversation: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return f"Failed to open conversation: {str(e)}"
    if response.status_code != 200:
        logger.error(f"Failed to open conversation {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return f"Failed to open conversation: API returned error {response.status_code}"

    data = json.loads(response.text)
    if data.get("msg") is None:
        if data.get("error") is None:
            logger.error("Invalid JSON data from open conversation call")
            logger.debug(f"Raw response: {response.text}")
            return "Failed to open conversation: API returned unexpected response"
        else:
            logger.error(f"Failed to open conversation: {data.get('error')}")
            return f"Failed to open conversation: {data.get('error')}"
    if data.get("msg") != "success":
        return "Unsuccessful while trying to open conversation"
    return None


def searchUser(username: str) -> Optional[int]:
    params = {'username': username}
    try:
        response = requests.get("https://traderie.com/api/diablo2resurrected/users", params=params, headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to search user: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return None
    if response.status_code != 200:
        logger.error(f"Failed to search user: Request returned code {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return None

    data = json.loads(response.text)
    if data.get("users") is None or (not isinstance(data.get("users"), list)):
        logger.error("Invalid JSON data from status call")
        logger.debug(f"Raw response: {response.text}")
        return None
    userList = data.get("users")
    userID = None
    for user in userList:
        if user.get("username") == username:
            userID = user.get("id")
            if userID is not None:
                return int(userID)
    return userID


def sendReview(userID: int, stars: int, description: str) -> Optional[str]:
    params = {
        'rating': stars,
        'description': description,
        'user': str(userID),
    }
    try:
        response = requests.post("https://traderie.com/api/diablo2resurrected/reviews/add", data=json.dumps(params), headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to send review: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return f"Failed to send review: {str(e)}"
    if response.status_code != 200:
        logger.error(f"Failed to send review {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return f"Failed to send review: API returned error {response.status_code}"

    data = json.loads(response.text)
    if data.get("error") is not None:
        logger.error(f"Failed to send review: {data.get('error')}")
        return f"Failed to send review: {data.get('error')}"
    return None


def acceptChatRequest(conversationID: str) -> Optional[str]:
    params = {
        'id': conversationID,
        'active': True,
    }
    try:
        response = requests.put("https://traderie.com/api/diablo2resurrected/conversations", data=json.dumps(params), headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to accept chat request: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return f"Failed to accept chat request: {str(e)}"
    if response.status_code != 200:
        logger.error(f"Failed to accept chat request {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return f"Failed to accept chat request: API returned error {response.status_code}"

    data = json.loads(response.text)
    if data.get("error") is not None:
        logger.error(f"Failed to accept chat request: {data.get('error')}")
        return f"Failed to accept chat request: {data.get('error')}"
    return None


def archiveChat(conversationID: str) -> Optional[str]:
    params = {
        'id': conversationID,
        'active': False,
    }
    try:
        response = requests.put("https://traderie.com/api/diablo2resurrected/conversations", data=json.dumps(params), headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to archive chat: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return f"Failed to archive chat: {str(e)}"
    if response.status_code != 200:
        logger.error(f"Failed to archive chat {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return f"Failed to archive chat: API returned error {response.status_code}"

    data = json.loads(response.text)
    if data.get("error") is not None:
        logger.error(f"Failed to archive chat: {data.get('error')}")
        return f"Failed to archive chat: {data.get('error')}"
    return None


def blockUser(userID: int) -> Optional[str]:
    params = {
        'user': str(userID),
    }
    try:
        response = requests.post("https://traderie.com/api/diablo2resurrected/blocks", data=json.dumps(params), headers=httpHeaders)
    except (requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError) as e:
        logger.error(f"Failed to block user: {str(e)}")
        logger.error(f"Stacktrace:\n{traceback.format_exc()}")
        return f"Failed to block user: {str(e)}"
    if response.status_code != 200:
        logger.error(f"Failed to block user {response.status_code}: {response.reason}")
        logger.debug(f"Raw response: {response.text}")
        return f"Failed to block user: API returned error {response.status_code}"

    data = json.loads(response.text)
    if data.get("error") is not None:
        logger.error(f"Failed to block user: {data.get('error')}")
        return f"Failed to block user: {data.get('error')}"
    return None