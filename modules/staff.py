import asyncio
import re

from pymongo import MongoClient
from pyrogram import Client, enums, errors, filters, types


async def reply_handler(client: Client, message: types.Message, db_client: MongoClient):
    bot_username = client.me.username
    cleaned_text = message.text.replace(f"@{bot_username}", "")
    pattern = r"(?s)/reply (\d+)\s+(.+)"
    text_match = re.match(pattern, cleaned_text)
    if not text_match:
        return await message.reply(
            "Please use the reply command like this:\n"
            "/reply <i>serial_number</i> <i>message</i>\n\n"
            "For example:\n"
            "/reply 1 مرحباً، يمكنك التواصل مع اختصاصي على الرقم التالي 01xxxxxxx\n\n"
            'this will send:\n"<b>مرحباً، يمكنك التواصل مع اختصاصي على الرقم التالي 01xxxxxxx</b>"\n to the user with serial number <b>1</b>.'
        )

    serial_number, reply_text = text_match.groups()
    user_in_db = db_client.masaBotDB.users.find_one(
        {"serial_number": int(serial_number)}
    )

    if not user_in_db:
        return await message.reply(
            f"Sorry, There is no user with the serial number: {serial_number}"
        )

    confirm_button = types.InlineKeyboardButton(
        "Confirm ✅", callback_data="confirm_reply"
    )
    cancel_button = types.InlineKeyboardButton(
        "Cancel ❌", callback_data="cancel_reply"
    )
    options_keyboard = types.InlineKeyboardMarkup([[confirm_button], [cancel_button]])

    user_name = f"<b>#{user_in_db['serial_number']}{' ('+user_in_db['custom_name']+')' if user_in_db['custom_name'] else ''}</b>"

    await message.reply(
        "Are you sure you want to send:\n"
        f'"<b>{reply_text}</b>"\n\n'
        f"To the user {user_name}?",
        reply_markup=options_keyboard,
    )

    callback_answer = await client.listen(
        filters=filters.regex(r"^confirm_reply$|^cancel_reply$"),
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        listener_type=enums.ListenerTypes.CALLBACK_QUERY,
    )

    if callback_answer.data == "confirm_reply":
        try:
            await client.send_message(
                user_in_db["_id"], "<b>لقد استلمت رداً من فريق MASA:</b>"
            )
            await client.send_message(user_in_db["_id"], reply_text)
        except errors.UserIsBlocked:
            print(
                f"Bot wasn't able to send message to user {user_in_db['_id']}, it says: {e}"
            )
            return await callback_answer.message.edit_text(
                f"""
                    Bot wasn't able to reply to the user {user_name}, User Blocked the Bot.
                """
            )
        except Exception as e:
            print(
                f"Bot wasn't able to send the message to user {user_in_db['_id']}, it says: {e}"
            )
            return await callback_answer.message.edit_text(
                f"Failed to send the message to {user_name}.\n\n"
                f"Show this error message to the bot developer:\n{e}"
            )
        else:
            db_client.masaBotDB.statistics.update_one(
                {}, {"$inc": {"staff_replies_counter": 1}}
            )
            return await callback_answer.message.edit_text(
                f"""
                    Reply sent to the user {user_name} succefully ✅
                """
            )

    else:
        return await callback_answer.message.edit_text("Reply cancelled ✅")


async def send_handler(client: Client, message: types.Message, db_client: MongoClient):
    bot_username = client.me.username
    cleaned_text = message.text.replace(f"@{bot_username}", "")
    pattern = r"(?s)/send (\d+)"
    text_match = re.match(pattern, cleaned_text)
    if not text_match:
        return await message.reply(
            "Please use the send command like this:\n"
            "/send <i>serial_number</i>\n\n"
            "For example:\n"
            "/send 1"
        )

    # extract serial number
    serial_number = text_match.groups()[0]
    user_in_db = db_client.masaBotDB.users.find_one(
        {"serial_number": int(serial_number)}
    )

    if not user_in_db:
        return await message.reply(
            f"Sorry, There is no user with the serial number: {serial_number}"
        )

    user_name = f"<b>#{user_in_db['serial_number']}{' ('+user_in_db['custom_name']+')' if user_in_db['custom_name'] else ''}</b>"

    request_message = await message.reply(
        f"Please reply to <b>THIS MESSAGE</b> with the message to send to user {user_name} (your message can contain media and files with or without caption) or reply with `cancel`"
    )

    def is_reply_to_message(_, __, m):
        return m.reply_to_message_id == request_message.id

    reply_to_filter = filters.create(is_reply_to_message)

    try:
        message_to_user = await client.listen(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            filters=reply_to_filter,
        )
    except (errors.ListenerStopped, asyncio.TimeoutError):
        return
    if not message_to_user:
        return

    if message_to_user.text and message_to_user.text.lower() == "cancel":
        return await message_to_user.reply("Sending Cancelled ✅")

    confirm_button = types.InlineKeyboardButton(
        "Confirm ✅", callback_data="confirm_send"
    )
    cancel_button = types.InlineKeyboardButton("Cancel ❌", callback_data="cancel_send")
    options_keyboard = types.InlineKeyboardMarkup([[confirm_button], [cancel_button]])

    sample_message = await message_to_user.copy(message.chat.id)
    await sample_message.reply(
        f"Are you sure you want to send this message to user {user_name}?",
        reply_markup=options_keyboard,
    )

    try:
        callback_answer = await client.listen(
            filters=filters.regex(r"^confirm_send$|^cancel_send$"),
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            listener_type=enums.ListenerTypes.CALLBACK_QUERY,
        )
    except (errors.ListenerStopped, asyncio.TimeoutError):
        return

    if not callback_answer:
        return

    if callback_answer.data == "cancel_send":
        return await callback_answer.message.edit_text("Sending Cancelled ✅")

    if callback_answer.data == "confirm_send":
        try:
            await client.send_message(
                user_in_db["_id"], "<b>لقد استلمت رسالة من فريق MASA:</b>"
            )
            await sample_message.copy(user_in_db["_id"])
        except errors.UserIsBlocked:
            print(
                f"Bot wasn't able to send message to user {user_in_db['_id']}, it says: {e}"
            )
            return await callback_answer.message.edit_text(
                f"""
                    Bot wasn't able to reply to the user {user_name}, User Blocked the Bot.
                """
            )
        except Exception as e:
            print(
                f"Bot wasn't able to send the message to user {user_in_db['_id']}, it says: {e}"
            )
            return await callback_answer.message.edit_text(
                f"Failed to send the message to {user_name}.\n\n"
                f"Show this error message to the bot developer:\n{e}"
            )
        else:
            db_client.masaBotDB.statistics.update_one(
                {}, {"$inc": {"staff_replies_counter": 1}}
            )
            return await callback_answer.message.edit_text(
                f"""
                    Message sent to the user {user_name} succefully ✅
                """
            )

    else:
        return await callback_answer.message.edit_text("Message cancelled ✅")


async def assign_name_handler(
    client: Client, message: types.Message, db_client: MongoClient
):
    bot_username = client.me.username
    cleaned_text = message.text.replace(f"@{bot_username}", "")

    pattern = r"/assign (\d+) (.+)"
    text_match = re.match(pattern, cleaned_text)
    if not text_match:
        return await message.reply(
            "Please use the assign command like this:\n"
            "/assign <i>serial_number</i> <i>name</i>\n\n"
            "For example:\n"
            "/assign 1 PTSD + OCD\n"
            "this will assign the name <b>PTSD + OCD</b> to the user with the serial number 1."
        )

    serial_number, custom_name = text_match.groups()
    user_in_db = db_client.masaBotDB.users.find_one(
        {"serial_number": int(serial_number)}
    )

    if not user_in_db:
        return await message.reply(
            f"Sorry, There is no user with the serial number: {serial_number}"
        )

    name_used = db_client.masaBotDB.users.find_one({"custom_name": custom_name})

    if name_used:
        return await message.reply(
            f"Sorry, There is already a user with the name: {custom_name}"
        )

    confirm_button = types.InlineKeyboardButton(
        "Confirm ✅", callback_data="confirm_assign"
    )
    cancel_button = types.InlineKeyboardButton(
        "Cancel ❌", callback_data="cancel_assign"
    )
    options_keyboard = types.InlineKeyboardMarkup([[confirm_button], [cancel_button]])

    user_name = f"<b>#{user_in_db['serial_number']}{' (Currently ' + user_in_db['custom_name']+')' if user_in_db['custom_name'] else ''}</b>"

    await message.reply(
        "Are you sure you want to assing the name: "
        f'"<b>{custom_name}</b>" '
        f"To the user {user_name}?",
        reply_markup=options_keyboard,
    )

    while True:
        callback_answer = await client.listen(
            filters=filters.regex(r"^confirm_assign$|^cancel_assign$"),
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            listener_type=enums.ListenerTypes.CALLBACK_QUERY,
        )

        if callback_answer and callback_answer.data == "confirm_assign":
            db_client.masaBotDB.users.update_one(
                {"_id": user_in_db["_id"]}, {"$set": {"custom_name": custom_name}}
            )
            return await callback_answer.message.edit_text(
                f"""
                    User #{serial_number} Has been assigned the name {custom_name} succefully ✅
                """
            )
        else:
            return await callback_answer.message.edit_text(
                "Name assignment cancelled ✅"
            )


async def help_handler(message: types.Message):
    await message.reply(
        "<b><u>Bot Manual:</u></b>\n\n"
        "<b>Hotline workflow is as follow:</b>\n\n"
        "- A user who need help starts me and if he/she is a member of KMSA community I will give him the assessment form to fill else I will aoplogize politely.\n\n"
        "- When the user <b>tells me</b> that he filled the form, I will tell you in this chat to go check his response and reply to him with the /reply command.\n\n"
        "- The user who filled the form can conact you at any time through me and you can reply to him with the /reply command.\n\n"
        "You can send messages that contain media or files to users with the /send command.\n\n"
        "- You can assign <b>custom names</b> to users, these names will not visible for them.\n\n"
        "- More funcationalities are available for <b>bot admins</b>, (i.e, setting staff chat, setting assessment form link, banning/unbanning users, seeing bot statistics and adding/removing other admins)."
    )
