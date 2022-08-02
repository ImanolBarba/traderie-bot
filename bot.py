###########################################################################
#   bot.py  --  This file is part of traderie-bot.                        #
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
import re
import threading
import traceback
from typing import Callable, Dict, List, Optional

import telegram
import telegram.ext

import blocklist
import dclone
import log
import lru
import traderie

# Constants
# Put your Telegram Bot API key here
APIKEY = ""
# Put your own chat ID here (Telegram user ID)
TARGET_CHAT_ID = 0
# Put your Traderie seller ID here
TRADERIE_SELLER_ID = 0

NOTIFICATION_POLLING_INTERVAL = 10
STATUS_INTERVAL = 1800
DCLONE_POLLING_INTERVAL = 60
MAX_MESSAGES_FETCH = 10

DEFAULT_RELIST_TIME_HOUR = 19
DEFAULT_RELIST_TIME_MINUTE = 00
MINUTES_SHIFT_PER_DAY = 5

DEFAULT_MODE = "softcore"
DEFAULT_LADDER = "NONLADDER"
DEFAULT_PLATFORM = "PC"
GREETING_TEXT = "Hello! wanna trade? which region are you in?"

# Global vars
logger = log.getLogger(__name__)
relistTime = datetime.time(
    hour=DEFAULT_RELIST_TIME_HOUR,
    minute=DEFAULT_RELIST_TIME_MINUTE,
    tzinfo=datetime.timezone.utc
)
exitEvent = threading.Event()
conversationCache = lru.LRUCache(10)
userCache = lru.LRUCache(10)
offersPerDay = 0
dclonePreviousStatus = {
    "Americas": 1,
    "Asia": 1,
    "Europe": 1,
}


def monitoringLoop(bot: telegram.Bot, threadList: Dict[str, Callable]) -> None:
    monitoredThreads = {}
    runningThreads = threading.enumerate()

    # Populate already running threads
    for thread in runningThreads:
        if thread.name in threadList:
            monitoredThreads[thread.name] = thread

    while not exitEvent.is_set():
        runningThreads = list(map(lambda x: x.name, threading.enumerate()))
        for thread in threadList:
            if thread not in runningThreads:
                logger.error(f"Uh oh, {thread} was not found in running thread list. Restarting...")
                monitoredThreads[thread] = threadList[thread](bot)
        exitEvent.wait(10)

    for thread in monitoredThreads:
        monitoredThreads[thread].join()
        logger.info(f"{thread} thread shutdown!")


def startStatusThread(bot: telegram.Bot) -> threading.Thread:
    statusThread = threading.Thread(target=statusLoop, args=(bot, STATUS_INTERVAL))
    statusThread.name = "status_thread"
    statusThread.start()
    return statusThread


def startNotificationThread(bot: telegram.Bot) -> threading.Thread:
    notificationThread = threading.Thread(target=pollNotificationsLoop, args=(bot, NOTIFICATION_POLLING_INTERVAL))
    notificationThread.name = "notification_thread"
    notificationThread.start()
    return notificationThread


def startRelistThread(bot: telegram.Bot) -> threading.Thread:
    relistThread = threading.Thread(target=relistLoop, args=(bot,))
    relistThread.name = "relist_thread"
    relistThread.start()
    return relistThread


def startDcloneThread(bot: telegram.Bot) -> threading.Thread:
    dcloneThread = threading.Thread(target=dcloneLoop, args=(bot, DCLONE_POLLING_INTERVAL))
    dcloneThread.name = "dclone_thread"
    dcloneThread.start()
    return dcloneThread


def calculateEffectiveRelistTime(relistTime: datetime.datetime) -> datetime.datetime:
    todayDate = datetime.date.today()
    currentWeekday = datetime.datetime.utcnow().weekday()
    return (
        datetime.datetime.combine(todayDate, relistTime) + datetime.timedelta(minutes=(MINUTES_SHIFT_PER_DAY * currentWeekday))
    ).time()


def helpHandler(update: telegram.Update, context: telegram.ext.CallbackContext):
    context.bot.send_message(
        chat_id=TARGET_CHAT_ID,
        text="\n".join([
            "/help: Show this message",
            "/relist_all: Relist all listings older than 24 hours",
            "/auth AUTH_HEADER_DATA: Set authentication header for requests",
            "/notifications: Print the last 10 notifications received",
            "/relist_time HH:MM: Set the current absolute listing time to HH:MM",
            "/relist_time: Print current absolute and effective listing time",
            "/send_msg USERNAME MESSAGE: Send MESSAGE to USERNAME",
            "/offers_recv: List offers received by the trader",
            "/offers_sent: List offers made by the trader",
            "/dclone: Get dclone status",
        ])
    )


def notificationPostActions(bot: telegram.Bot, notification: traderie.Notification, notificationMessage: telegram.Message) -> None:
    global offersPerDay
    if re.search("^You got a new message from .*$", notification.text) is not None:
        username = re.search("^You got a new message from (.*)$", notification.text).group(1)
        userCache.put(username, str(notification.fromUserID))
        lastMessages = doLastMessagesFrom(notification.fromUserID)
        if lastMessages is None:
            logger.error(f"Unable to get last messages from user {notification.fromUserID}")
            return
        if len(lastMessages) != 0:
            lastMessagesText = '\n' + '\n'.join(list(map(lambda x: x.text, lastMessages)))
            bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Last messages from {username}:{lastMessagesText}",
                reply_to_message_id=notificationMessage.message_id,
            )
            logger.info(f"Last messages from {username}:{lastMessagesText}")
    elif re.search("^.*? made an ? offer for .*$", notification.text) is not None:
        offers = doOffersForListing(notification.listingID, TRADERIE_SELLER_ID)
        if offers is None:
            logger.error("Unable to get offers for listing")
            return
        targetOffer = None
        for offer in offers:
            if offer.buyerID == notification.fromUserID:
                targetOffer = offer
        if targetOffer is None:
            logger.error("Unable to find the offer mentioned in the notification")
            return
        lst = traderie.getListing(notification.listingID)
        if lst is None:
            logger.error(f"Unable to find the listing the notification is mentioning: {notification.listingID}")
            return
        offersPerDay += 1
        offerStr = ' OR '.join(list(map(lambda x: str(x), targetOffer.offer)))
        listingStr = ' OR '.join(list(map(lambda x: str(x), lst.price)))
        msgText = f"Their offer {offerStr}\nYour Price {listingStr}"
        bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=msgText,
            reply_to_message_id=notificationMessage.message_id,
            reply_markup=telegram.InlineKeyboardMarkup(
                inline_keyboard=[[
                    telegram.InlineKeyboardButton(text="Accept", callback_data=f"accept:{targetOffer.offerID}"),
                    telegram.InlineKeyboardButton(text="Decline", callback_data=f"decline:{targetOffer.offerID}"),
                ]]
            )
        )
        logger.info(msgText)
    elif re.search("^.*? completed their offer for your .*?\\. Leave them a review$", notification.text) is not None:
        notificationMessage.edit_reply_markup(
            reply_markup=telegram.InlineKeyboardMarkup(
                inline_keyboard=[[
                    telegram.InlineKeyboardButton(text="Send 5 star", callback_data=f"review:{notification.fromUserID}"),
                ]]
            )
        )
    elif re.search("^You just got a 5 star review from .*$", notification.text) is not None:
        res = traderie.sendReview(notification.fromUserID, 5, "")
        if res is not None:
            logger.error(f"Unable to send review: {res}")
    elif re.search("^You have a chat request from .*$", notification.text) is not None:
        res = traderie.acceptChatRequest(notification.notificationID)
        if res is not None:
            logger.error(f"Unable to automatically accept conversation request: {res}")
        username = re.search("^You have a chat request from (.*)$", notification.text).group(1)
        userCache.put(username, str(notification.fromUserID))
        lastMessages = doLastMessagesFrom(notification.fromUserID)
        if lastMessages is None:
            logger.error(f"Unable to get last messages from user {notification.fromUserID}")
            return
        for msg in lastMessages:
            reason = blocklist.assholeBlocklist(msg.text)
            if reason is not None:
                traderie.archiveChat(notification.notificationID)
                traderie.blockUser(notification.fromUserID)
                bot.send_message(
                    chat_id=TARGET_CHAT_ID,
                    text=f"Asshole detected: {username}. Reason: {reason}",
                    reply_to_message_id=notificationMessage.message_id,
                )
                return
        if len(lastMessages) != 0:
            lastMessagesText = '\n' + '\n'.join(list(map(lambda x: x.text, lastMessages)))
            bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Last messages from {username}:{lastMessagesText}",
                reply_to_message_id=notificationMessage.message_id,
            )
            logger.info(f"Last messages from {username}:{lastMessagesText}")


def doSendMessage(bot: telegram.Bot, username: str, message: str) -> None:
    userID = userCache.get(username)
    if userID is None:
        userID = traderie.searchUser(username)
        if userID is None:
            logger.error(f"Searching for username '{username}' yielded no results")
            bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Unable to send message: '{username}' not found"
            )
            return
        userCache.put(username, str(userID))
    res = traderie.sendMessage(userID, message)
    if res is not None:
        logger.error(f"Unable to send message: {res}")
        bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"Unable to send message: {res}"
        )
    else:
        # TODO(ibarba): it'd be so cool if we could do something like answer_callback_query here
        pass


def doOffersForListing(listingID: int, seller: int) -> Optional[List[traderie.Offer]]:
    ret = []
    offers = traderie.getOffers(toSellerID=seller)
    if offers is None:
        return None
    for o in offers:
        offer = offers[o]
        if offer.listingID == listingID:
            ret.append(offer)
    return ret


def doRelist(bot: telegram.Bot) -> None:
    listings = traderie.getAllListings(TRADERIE_SELLER_ID)
    if listings is None:
        bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text="Unable to get all listings from user",
        )
        return
    possibleListings = list(filter(lambda x: traderie.isListingRelistable(x), list(listings.values())))
    logger.debug(f"{len(possibleListings)} out of {len(listings)} listings are relistable")

    errors = 0
    for listing in possibleListings:
        res = traderie.relistItem(listing.listingID)
        if res is not None:
            logger.error(f"Unable to relist listing {listing.listingID}: {res}")
            errors += 1
        else:
            logger.info(f"Successfully relisted listing {listing.listingID}")
    if errors != 0:
        bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"Completed. Some listings failed to relist ({errors} out of {len(possibleListings)})",
        )
        logger.info(f"Completed. Some listings failed to relist ({errors} out of {len(possibleListings)})")
        return
    bot.send_message(
        chat_id=TARGET_CHAT_ID,
        text=f"All listings ({len(possibleListings)}) refreshed successfully!",
    )
    logger.info(f"All listings ({len(possibleListings)}) refreshed successfully!")


def doLastMessagesFrom(fromUserID: int) -> Optional[List[traderie.Message]]:
    conversations = traderie.getConversations(True, TRADERIE_SELLER_ID)

    if conversations.get(fromUserID) is None:
        logger.error(f"Unable to find an active conversation with user {fromUserID}")
        return None

    messages = traderie.getMessages(fromUserID, MAX_MESSAGES_FETCH, conversations[fromUserID].conversationID)
    if messages is None or len(messages) == 0:
        logger.error(f"Unable to get messages from user {fromUserID}: {messages}")
        return None

    lastMessages = []
    index = -1
    lastMessageID = conversationCache.get(str(fromUserID))
    if lastMessageID is not None:
        for i in range(len(messages)):
            if messages[i].msgID == lastMessageID:
                index = i
                break
    else:
        index = len(messages)
    if index == -1:
        logger.error(f"Unable to find last message {lastMessageID} from {fromUserID}, too many messages received?")
        index = len(messages)
    if index == 0:
        logger.info("No new messages")
        return []
    for i in range(index - 1, -1, -1):
        if messages[i].fromID == fromUserID:
            lastMessages.append(messages[i])
    if len(lastMessages) == 0:
        logger.error(f"No last messages found for user {fromUserID}. Last message index: {index}. Last message ID: {lastMessageID}")
        return None
    conversationCache.put(str(fromUserID), lastMessages[-1].msgID)
    return lastMessages


def doNotifications(bot: telegram.Bot, new: bool) -> None:
    allNotifications = traderie.getNotifications(False, 10)
    newNotifications = traderie.getNotifications(True, 10)
    if allNotifications is None or newNotifications is None:
        bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text="Error getting notification list",
        )
        return
    if len(newNotifications) != 0:
        res = traderie.markNewNotificationsAsRead(newNotifications)
        if res is not None:
            bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Error marking notifications as read: {res}",
            )

    notifications = newNotifications
    if not new:
        notifications = allNotifications

    notifications.reverse()
    for notification in notifications:
        if new:
            notificationMessage = bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"⚠️ ALERT ⚠️: [{notification.date}] {notification.text}",
            )
            logger.info(f"⚠️ ALERT ⚠️: [{notification.date}] {notification.text}")
            notificationPostActions(bot, notification, notificationMessage)
        else:
            bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"[{notification.date}] {notification.text}",
            )


def authHandler(update: telegram.Update, context: telegram.ext.CallbackContext):
    if len(context.args) < 1:
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"/auth needs an argument: {len(context.args)}",
        )
        logger.error(f"Invalid args for /auth: {context.args}")
        return
    traderie.httpHeaders['authorization'] = ' '.join(context.args)
    context.bot.send_message(
        chat_id=TARGET_CHAT_ID,
        text="Successfully set auth data",
    )
    logger.info("Successfully set auth data")


def relistAllHandler(update: telegram.Update, context: telegram.ext.CallbackContext):
    if traderie.httpHeaders['authorization'] == "":
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text="Authentication data has not been set. Please do so with the /auth command",
        )
        return
    doRelist(context.bot)


def notificationsHandler(update: telegram.Update, context: telegram.ext.CallbackContext):
    if traderie.httpHeaders['authorization'] == "":
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text="Authentication data has not been set. Please do so with the /auth command",
        )
        return
    doNotifications(context.bot, False)
    context.bot.send_message(
        chat_id=TARGET_CHAT_ID,
        text="Finished listing notifications",
    )


def relistTimeHandler(update: telegram.Update, context: telegram.ext.CallbackContext):
    global relistTime

    if len(context.args) > 1:
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"Invalid arguments supplied to /relist_time: {len(context.args)}",
        )
        logger.error(f"Invalid args for /relist_time: {context.args}")
        return
    if len(context.args) == 0:
        effectiveTime = calculateEffectiveRelistTime(relistTime)
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"Current time for relisting: {relistTime.hour:02}:{relistTime.minute:02}\nEffective relisting time: {effectiveTime.hour:02}:{effectiveTime.minute:02}",
        )
        return
    try:
        newTime = datetime.time.fromisoformat(context.args[0])
        relistTime = datetime.time(hour=newTime.hour, minute=newTime.minute, tzinfo=datetime.timezone.utc)
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"Successfully set new relist time to {relistTime.hour:02}:{relistTime.minute:02} UTC",
        )
    except ValueError:
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text="Invalid format. Needs to be HH:MM",
        )
        logger.error(f"Invalid time format for /relist_time: {context.args[0]}")


def sendMessageHandler(update: telegram.Update, context: telegram.ext.CallbackContext):
    if traderie.httpHeaders['authorization'] == "":
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text="Authentication data has not been set. Please do so with the /auth command",
        )
        return
    if len(context.args) < 2:
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"Incorrect arguments for /send_msg: {context.args}",
        )
        return
    doSendMessage(context.bot, context.args[0], ' '.join(context.args[1:]))


def callbackQueryHandler(update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    query = update.callback_query
    action = query.data.split(":")[0]
    if action == "accept":
        query.edit_message_reply_markup(reply_markup=telegram.InlineKeyboardMarkup(inline_keyboard=[[]]))
        offerID = int(query.data.split(":")[1])
        offers = traderie.getOffers(toSellerID=TRADERIE_SELLER_ID)
        offer = offers.get(offerID)
        if offer is None:
            logger.error(f"Unable to find offer from callback data: {offerID}")
            context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Unable to find offer from callback data: {offerID}",
            )
            return
        res = traderie.acceptOffer(offer.offerID, offer.buyerID, offer.listingID, offer.amount, offer.itemID)
        if res is None:
            logger.info("Successfully accepted offer")
            lst = traderie.getListing(offer.listingID)
            greetingCallbackData = f"greeting:{offer.buyerUsername}"
            if lst is None:
                logger.error(f"Unable to find the listing the offer is about: {offer.listingID}")
            else:
                mode = DEFAULT_MODE
                ladder = DEFAULT_LADDER
                platform = DEFAULT_PLATFORM
                if lst.properties.get("Mode") is not None:
                    mode = lst.properties.get("Mode").value
                if lst.properties.get("Ladder") is not None and lst.properties["Ladder"].value == "True":
                    ladder = "LADDER"
                if lst.properties.get("Platform") is not None:
                    platform = lst.properties.get("Platform").value
                greetingCallbackData += f":{platform}:{mode}:{ladder}"
            context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text="Successfully accepted offer",
                reply_markup=telegram.InlineKeyboardMarkup(
                    inline_keyboard=[[
                        telegram.InlineKeyboardButton(text="Send greeting", callback_data=greetingCallbackData),
                    ]]
                )
            )
        else:
            context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Unable to accept offer: {res}",
            )
            return
        res = traderie.openConversation(offer.buyerID, offer.buyerUsername, offer.offerID)
        if res is not None:
            logger.error("Unable to start conversation: {res}")

    elif action == "decline":
        query.edit_message_reply_markup(reply_markup=telegram.InlineKeyboardMarkup(inline_keyboard=[[]]))
        offerID = int(query.data.split(":")[1])
        offers = traderie.getOffers(toSellerID=TRADERIE_SELLER_ID)
        offer = offers.get(offerID)
        if offer is None:
            logger.error(f"Unable to find offer from callback data: {offerID}")
            context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Unable to find offer from callback data: {offerID}",
            )
            return
        res = traderie.declineOffer(offer.offerID, offer.buyerID, offer.listingID)
        if res is None:
            logger.info("Successfully declined offer")
            context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text="Successfully declined offer",
            )
        else:
            context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Unable to decline offer: {res}",
            )
    elif action == "review":
        query.edit_message_reply_markup(reply_markup=telegram.InlineKeyboardMarkup(inline_keyboard=[[]]))
        userID = int(query.data.split(":")[1])
        res = traderie.sendReview(userID, 5, "")
        if res is not None:
            logger.error(f"Unable to send review: {res}")
            context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Unable to send review: {res}"
            )
        else:
            context.bot.answer_callback_query(update.callback_query.id, "Success!")
    elif action == "greeting":
        query.edit_message_reply_markup(reply_markup=telegram.InlineKeyboardMarkup(inline_keyboard=[[]]))
        args = query.data.split(":")[1:]
        username = args[0]
        preface = ""
        if len(args) == 4:
            preface = f"⚠️⚠️⚠️ This listing is for {args[1]} {args[2]} {args[3]} ⚠️⚠️⚠️\n\n"
        doSendMessage(context.bot, username, preface + GREETING_TEXT)
    else:
        logger.warning(f"Unknown action requested: {action}")


def messageHandler(update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    if update.message.reply_to_message is not None:
        originalMessageText = update.message.reply_to_message.text
        if re.search("^Last messages from (.*?):$", originalMessageText.split("\n")[0]) is not None:
            username = re.search("^Last messages from (.*?):$", originalMessageText.split("\n")[0]).group(1)
            doSendMessage(context.bot, username, update.message.text)
        else:
            logger.warning("Message didn't match any patterns")


def dcloneHandler(update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    softcore = True
    ladder = False
    if len(context.args) != 0:
        if len(context.args) != 2:
            context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Incorrect arguments for /dclone: {context.args}",
            )
            return
        if context.args[0] != "soft" and context.args[0] != "hard":
            context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Incorrect first argument. Must be either 'hard' or 'soft': {context.args}",
            )
            return
        if context.args[1] != "ladder" and context.args[1] != "nonladder":
            context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Incorrect second argument. Must be either 'ladder' or 'nonladder': {context.args}",
            )
            return
        if context.args[0] == "hard":
            softcore = False

        if context.args[1] == "ladder":
            ladder = True

    status = dclone.getDcloneStatus(softcore, ladder)
    if status is None:
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text="Unable to get dclone status. Check logs",
        )
        return
    message = ""
    for region in status:
        message += f"{region}: {dclone.DCLONE_STATUS[status[region]]}\n"
    if message == "":
        message = "No data!"
    context.bot.send_message(
        chat_id=TARGET_CHAT_ID,
        text=message,
    )


def offersReceivedHandler(update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    if traderie.httpHeaders['authorization'] == "":
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text="Authentication data has not been set. Please do so with the /auth command",
        )
        return
    offers = traderie.getOffers(toSellerID=TRADERIE_SELLER_ID)
    if len(offers) == 0:
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text="No offers received"
        )
        return
    for o in offers:
        offer = offers[o]
        lst = traderie.getListing(offer.listingID)
        if lst is None:
            logger.error(f"Can't find listing {offer.listingID} for offer {offer.offerID}")
            context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Can't find listing {offer.listingID} for offer {offer.offerID}"
            )
            return
        offerStr = ' OR '.join(list(map(lambda x: str(x), offer.offer)))
        listingStr = ' OR '.join(list(map(lambda x: str(x), lst.price)))
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"Offer for {offer.itemName} from {offer.buyerUsername}:\nTheir offer {offerStr}\nYour Price {listingStr}",
        )


def offersSentHandler(update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    if traderie.httpHeaders['authorization'] == "":
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text="Authentication data has not been set. Please do so with the /auth command",
        )
        return
    offers = traderie.getOffers(fromUserID=TRADERIE_SELLER_ID)
    if len(offers) == 0:
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text="No offers sent"
        )
        return
    for o in offers:
        offer = offers[o]
        lst = traderie.getListing(offer.listingID)
        if lst is None:
            logger.error(f"Can't find listing {offer.listingID} for offer {offer.offerID}")
            context.bot.send_message(
                chat_id=TARGET_CHAT_ID,
                text=f"Can't find listing {offer.listingID} for offer {offer.offerID}"
            )
            return
        offerStr = ' OR '.join(list(map(lambda x: str(x), offer.offer)))
        listingStr = ' OR '.join(list(map(lambda x: str(x), lst.price)))
        context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"Offer for {offer.itemName} from {offer.sellerUsername}:\nYour offer {offerStr}\nTheir Price {listingStr}",
        )


def telegramErrorHandler(update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    if context.error is not None:
        logger.error(f"Error while getting updates (or running handler): {str(context.error)}")
        logger.error(f"Stacktrace:\n{''.join(traceback.format_exception(type(context.error), context.error, context.error.__traceback__))}")
        return


def pollNotificationsLoop(bot: telegram.Bot, frequency: int) -> None:
    global exitEvent
    while not exitEvent.is_set():
        if traderie.httpHeaders['authorization'] != "":
            try:
                doNotifications(bot, True)
            except telegram.error.NetworkError as e:
                logger.error(f"Failed to read notifications: {str(e)}")
                logger.error(f"Stacktrace:\n{traceback.format_exc()}")
            exitEvent.wait(frequency)
        else:
            logger.warning("Skipping notification polling since auth data is unset")
            exitEvent.wait(10)


def relistLoop(bot: telegram.Bot) -> None:
    global exitEvent
    global relistTime
    global offersPerDay

    while not exitEvent.is_set():
        if traderie.httpHeaders['authorization'] != "":
            currentTime = datetime.datetime.utcnow()
            effectiveTime = calculateEffectiveRelistTime(relistTime)
            if currentTime.hour == effectiveTime.hour and currentTime.minute == effectiveTime.minute:
                logger.info("Time to relist!")
                try:
                    if offersPerDay == 0:
                        logger.warning("No offers in 24h! Notifying user...")
                        bot.send_message(
                            chat_id=TARGET_CHAT_ID,
                            text="No offers received in 24h. Please check that everything is running correctly",
                        )
                    offersPerDay = 0
                    doRelist(bot)
                except telegram.error.NetworkError as e:
                    logger.error(f"Failed to relist listings: {str(e)}")
                    logger.error(f"Stacktrace:\n{traceback.format_exc()}")
            exitEvent.wait(60)
        else:
            logger.warning("Skipping automatic relisting since auth data is unset")
            exitEvent.wait(10)


def dcloneLoop(bot: telegram.Bot, frequency: int) -> None:
    global exitEvent
    global dclonePreviousStatus
    while not exitEvent.is_set():
        status = dclone.getDcloneStatus(True, False)
        if status is None:
            logger.error("Unable to get dclone status")
        else:
            for region in status:
                if status[region] > dclonePreviousStatus[region]:
                    dcloneText = f"{'❗' * (status[region] - 1)} Region {region} dclone status: {dclone.DCLONE_STATUS[status[region]]} {'❗' * (status[region] - 1)}"
                    bot.send_message(
                        chat_id=TARGET_CHAT_ID,
                        text=dcloneText,
                    )
                    logger.info(dcloneText)
                elif (status[region] < dclonePreviousStatus[region]) and (dclonePreviousStatus[region] != 6):
                    dcloneText = f"Region {region} dclone status went back to {status[region]}/6. Likely a false alarm"
                    bot.send_message(
                        chat_id=TARGET_CHAT_ID,
                        text=dcloneText
                    )
                    logger.info(dcloneText)

            dclonePreviousStatus = status
        exitEvent.wait(frequency)


def statusLoop(bot: telegram.Bot, frequency: int) -> None:
    global exitEvent
    while not exitEvent.is_set():
        if traderie.httpHeaders['authorization'] != "":
            status = traderie.getStatus(TRADERIE_SELLER_ID)
            if status is None:
                logger.error("Unable to get status")
            elif status != "online":
                logger.info(f"Status is {status}, switching to online")
                res = traderie.setStatus("online")
                if res is None:
                    logger.info("Successfully set status to online")
                else:
                    logger.error("Unable to set status to online")
            exitEvent.wait(frequency)
        else:
            logger.warning("Skipping status polling since auth data is unset")
            exitEvent.wait(10)


def initBot(bot: telegram.Bot) -> None:
    bot.send_message(
        chat_id=TARGET_CHAT_ID,
        text="Hello! Please input the authorization header using the /auth command, following the example below",
    )
    bot.send_message(
        chat_id=TARGET_CHAT_ID,
        text="/auth AUTH_HEADER_DATA",
    )


def start() -> None:
    updater = telegram.ext.Updater(token=APIKEY, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(telegram.ext.CommandHandler('help', helpHandler))
    dispatcher.add_handler(telegram.ext.CommandHandler('relist_all', relistAllHandler))
    dispatcher.add_handler(telegram.ext.CommandHandler('auth', authHandler))
    dispatcher.add_handler(telegram.ext.CommandHandler('notifications', notificationsHandler))
    dispatcher.add_handler(telegram.ext.CommandHandler('relist_time', relistTimeHandler))
    dispatcher.add_handler(telegram.ext.CommandHandler('send_msg', sendMessageHandler))
    dispatcher.add_handler(telegram.ext.CommandHandler('offers_recv', offersReceivedHandler))
    dispatcher.add_handler(telegram.ext.CommandHandler('offers_sent', offersSentHandler))
    dispatcher.add_handler(telegram.ext.CommandHandler('dclone', dcloneHandler))
    dispatcher.add_handler(telegram.ext.CallbackQueryHandler(callbackQueryHandler))
    dispatcher.add_error_handler(telegramErrorHandler)
    dispatcher.add_handler(telegram.ext.MessageHandler(telegram.ext.Filters.all, messageHandler))
    updater.start_polling()
    initBot(updater.bot)

    threadMap = {
        "status_thread": startStatusThread,
        "notification_thread": startNotificationThread,
        "relist_thread": startRelistThread,
        "dclone_thread": startDcloneThread,
    }

    startStatusThread(updater.bot)
    startNotificationThread(updater.bot)
    startRelistThread(updater.bot)
    startDcloneThread(updater.bot)

    monitoringThread = threading.Thread(target=monitoringLoop, args=(updater.bot, threadMap))
    monitoringThread.start()

    while True:
        monitoringThread.join()
        logger.info("Monitoring thread shutdown!")
        if not exitEvent.is_set():
            logger.error("Monitoring thread exited WITHOUT shutdown being triggered. This is real bad. Restarting thread...")
            monitoringThread = threading.Thread(target=monitoringLoop, args=(updater.bot, threadMap))
            monitoringThread.start()
        else:
            break

    logger.info("Stopping updater...")
    updater.stop()
    logger.info("Shutting down...")
