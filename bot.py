import asyncio
import logging
import os
import signal

import requests
from pyrogram import Client, filters
from pyrogram.types import BotCommand, BotCommandScopeAllPrivateChats

from models.config import Config
from modules import admins, staff, users
from utils.flask_server import run_server
from utils.log import log
from utils.mongo import connect_to_db

# user dotenv file in development
is_production = os.getenv("PRODUCTION", None)
if not is_production or is_production == "0":
    import dotenv

    dotenv.load_dotenv()

# disable flask development server logging
logger = logging.getLogger("werkzeug")
logger.disabled = True

# this is to prevent the service from sleeping in free hostings ervices
run_server()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_URI = os.getenv("DB_URI", "")
ADMIN_ID = os.getenv("ADMIN_ID", "")

if ADMIN_ID.isnumeric():
    ADMIN_ID = int(ADMIN_ID)

# the url of the service in hosting platform
SERVICE_URL = os.getenv("SERVICE_URL")

client: Client = Client(
    "MASA_Hotline_Bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN
)


db_client = connect_to_db(DB_URI)
# Use a test database for development
if not is_production:
    db_client = db_client.test1


async def main() -> None:
    await client.start()

    # set commands for users
    await client.set_bot_commands(
        [BotCommand("start", "starts the bot")], scope=BotCommandScopeAllPrivateChats()
    )

    # NOTE: Staff commands are set when staff chat is set not here.

    # check config health
    config = db_client.masaBotDB.config.find_one({})
    if not config:
        config = Config(
            admins_list=[int(ADMIN_ID)],
            super_admin_id=int(ADMIN_ID),
        )
        db_client.masaBotDB.config.insert_one(config.as_dict())
        try:
            await client.send_message(
                ADMIN_ID,
                "Hey Admin!\n\n"
                "<b>Congratulation, The bot has been started for the first time 🥳</b>\n\n\n"
                "Let's set staff group, assessment form link and a general assembly chat if you want, please send /start.",
            )
        except Exception as e:
            await log(client, f"could not message the admin, it says: {e}")
            await log(client, "Tell the admin to start the bot!")

    else:
        admins_list = config["admins_list"]
        if not config["staff_chat_id"]:
            for admin_id in admins_list:
                await client.send_message(
                    admin_id,
                    "Hey!, staff group is not set!, please send /start to set it.",
                )

        if not config["assessment_form_link"]:
            for admin_id in admins_list:
                await client.send_message(
                    admin_id,
                    "Hey!, assessment form link is not set!, please send /start to set it.",
                )

    # create statistics documnet in the first bot run
    statistics = db_client.masaBotDB.statistics.find_one({})
    if not statistics:
        db_client.masaBotDB.statistics.insert_one(
            {"staff_replies_counter": 0, "users_messages_counter": 0}
        )

    # Filters
    def is_admin(_, __, update):
        config = db_client.masaBotDB.config.find_one({})
        return bool(
            config and update.from_user and update.from_user.id in config["admins_list"]
        )

    admin_chat_filter = filters.create(is_admin)

    def not_banned(_, client, update):
        banned_users = db_client.masaBotDB.config.find_one({}, {"banned_users": 1})[
            "banned_users"
        ]
        return bool(
            update.from_user
            and update.from_user.id not in banned_users
            and update.from_user.id != client.me.id
        )

    bot_user_filter = filters.create(not_banned) & ~admin_chat_filter

    def is_staff_chat(_, __, update):
        config = db_client.masaBotDB.config.find_one({})
        return bool(
            config and update.chat and update.chat.id == config["staff_chat_id"]
        )

    staff_chat_filter = filters.create(is_staff_chat)

    # User-Bot interaction
    @client.on_message(bot_user_filter & filters.command("start"))
    async def _(client, message):
        await users.start_handler(client, message, db_client)

    @client.on_callback_query(bot_user_filter & filters.regex("^filled_form$"))
    async def _(client, callback_query):
        await users.filled_form_handler(client, callback_query, db_client)

    @client.on_callback_query(bot_user_filter & filters.regex("^refill_form$"))
    async def _(client, callback_query):
        await users.refill_form_handler(callback_query, db_client)

    @client.on_callback_query(bot_user_filter & filters.regex("^contact_staff$"))
    async def _(client, callback_query):
        await users.contact_staff_handler(client, callback_query, db_client)

    @client.on_callback_query(bot_user_filter & filters.regex("^user_back$"))
    async def _(client, callback_query):
        await users.back_handler(client, callback_query, db_client)

    @client.on_message(filters.private & bot_user_filter & filters.text)
    async def _(client, message):
        await users.text_handler(message)

    # Staff-Bot interaction
    @client.on_message(staff_chat_filter & filters.command("reply"))
    async def _(client, message):
        await staff.reply_handler(client, message, db_client)

    @client.on_message(staff_chat_filter & filters.command("assign"))
    async def _(client, message):
        await staff.assign_name_handler(client, message, db_client)

    @client.on_message(staff_chat_filter & filters.command("help"))
    async def _(client, message):
        await staff.help_handler(message)

    # Admin-Bot interaction
    @client.on_message(admin_chat_filter & filters.command("start") & filters.private)
    async def _(client, message):
        await admins.start_handler(client, message, db_client)

    @client.on_callback_query(admin_chat_filter & filters.regex("^set_staff_chat$"))
    async def _(client, callback_query):
        await admins.set_staff_chat_handler(client, callback_query, db_client)

    @client.on_callback_query(
        admin_chat_filter & filters.regex("^set_assessment_form_link$")
    )
    async def _(client, callback_query):
        await admins.set_assesment_form_link_handler(client, callback_query, db_client)

    @client.on_callback_query(admin_chat_filter & filters.regex("^set_ga_chat$"))
    async def _(client, callback_query):
        await admins.set_ga_chat_handler(client, callback_query, db_client)

    @client.on_callback_query(admin_chat_filter & filters.regex("^broadcast$"))
    async def _(client, callback_query):
        await admins.broadcast_handler(client, callback_query, db_client)

    @client.on_callback_query(admin_chat_filter & filters.regex("^ban_user$"))
    async def _(client, callback_query):
        await admins.ban_user_handler(client, callback_query, db_client)

    @client.on_callback_query(admin_chat_filter & filters.regex("^unban_user$"))
    async def _(client, callback_query):
        await admins.unban_button_handler(callback_query, db_client)

    @client.on_message(
        admin_chat_filter & filters.private & filters.regex(r"^/unban_\d+$")
    )
    async def _(client, message):
        await admins.unban_user_handler(message, db_client)

    @client.on_callback_query(admin_chat_filter & filters.regex("^add_admin$"))
    async def _(client, callback_query):
        await admins.add_admin_handler(client, callback_query, db_client)

    @client.on_callback_query(admin_chat_filter & filters.regex("^manage_admins$"))
    async def _(client, callback_query):
        await admins.manage_admins_handler(client, callback_query, db_client)

    @client.on_message(
        admin_chat_filter & filters.private & filters.regex(r"^/remove_admin_\d+$")
    )
    async def _(client, message):
        await admins.remove_admin_handler(message, db_client)

    @client.on_message(
        admin_chat_filter
        & filters.private
        & filters.regex(r"^/transfer_super_admin_\d+$")
    )
    async def _(client, message):
        await admins.transfer_super_admin_handler(client, message, db_client)

    @client.on_callback_query(admin_chat_filter & filters.regex("^statistics$"))
    async def _(client, callback_query):
        await admins.statistics_handler(callback_query, db_client)

    @client.on_callback_query(admin_chat_filter & filters.regex("^back$"))
    async def _(client, callback_query):
        await admins.back_handler(client, callback_query, db_client)

    async def idle():
        shutdown_event = asyncio.Event()

        def handle_sigterm(_, __):
            asyncio.get_event_loop().call_soon_threadsafe(shutdown_event.set)

        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGINT, handle_sigterm)

        await shutdown_event.wait()
        await client.stop()

    print("Bot is running.")

    # prevent service sleep
    async def ping_server():
        if SERVICE_URL:
            res = requests.get(SERVICE_URL)
            return await log(client, res.text)
        else:
            return await log(
                client,
                "Warning: $SERVICE_URL is not set, the service can sleep at anytime.",
            )

    async def keep_up():
        m = await ping_server()
        while True:
            try:
                await asyncio.sleep(60)
                await m.delete()
                m = await ping_server()
            except Exception as e:
                await log(client, str(e))
                pass

    asyncio.create_task(keep_up())
    await idle()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
