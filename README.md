# traderie-bot
Telegram bot to automate trading Diablo II: Resurrected items in Traderie

Features:
- Alerts on all notifications
- Automatically relists all your items every 24 hours, with a weekly rolling delay with 5 minutes delta between days
- Alerts you of Dclone changes (community based trackers)
- Keeps your user always online
- Displays user messages if a message is received
- Displays trade offer details if one is received
- Has quick action buttons to accept, decline offers, and send 5 star reviews, as well as a greeting once an offer is accepted
- Replying to displayed messages from an user in Telegram will send them a message with the text from your reply, so you can have conversations within the bot without opening the website

To run this you need to specify constants in `bot.py`:
- `APIKEY`
- `TARGET_CHAT_ID`
- `TRADERIE_SELLER_ID`

TBD: Have these in a config file. Someday.

You'll need to create a Telegram Bot to obtain a Telegram Bot API for the `APIKEY` constant

Python 3.9 is required.
