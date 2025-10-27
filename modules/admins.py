import asyncio

from pymongo import MongoClient
from pyrogram import Client, enums, errors, filters, types

from utils.log import log


def admin_keyboard(is_super_admin: bool = False):
    set_staff_chat_button = types.InlineKeyboardButton(
        "Set Staff Chat  👥", "set_staff_chat"
    )

    set_assesment_form_link_button = types.InlineKeyboardButton(
        "Set Assessment Form Link  📋", "set_assessment_form_link"
    )

    set_ga_chat_button = types.InlineKeyboardButton(
        "Set General Assembly Chat  👥", "set_ga_chat"
    )

    broadcast_button = types.InlineKeyboardButton(
        "Broadcast a Message To All Bot Users  📢", "broadcast"
    )

    ban_user_button = types.InlineKeyboardButton("Ban a Bot User  🚫", "ban_user")

    unban_user_button = types.InlineKeyboardButton("Unban a Bot User  ✅", "unban_user")

    add_admin_button = types.InlineKeyboardButton("Add an Admin  ➕👤", "add_admin")

    # only superadmin can remove other admins
    manage_admins_button = types.InlineKeyboardButton(
        "Manage Bot Admins 🔧👤", "manage_admins"
    )

    statistics_button = types.InlineKeyboardButton(
        "Show Bot Statistics  📊", "statistics"
    )

    admin_options_keyboard = types.InlineKeyboardMarkup(
        [
            [set_staff_chat_button],
            [set_assesment_form_link_button],
            [set_ga_chat_button],
            [broadcast_button],
            [ban_user_button],
            [unban_user_button],
            [add_admin_button] + ([manage_admins_button] if is_super_admin else []),
            [statistics_button],
        ]
    )

    return admin_options_keyboard


def back_keyboard():
    back_button = types.InlineKeyboardButton("Go Back", "back")
    back_keyboard = types.InlineKeyboardMarkup([[back_button]])
    return back_keyboard


async def current_settings(client: Client, db_client: MongoClient):
    config = db_client.masaBotDB.config.find_one({})
    if not config:
        return "Error getting settings ❌"

    if config["staff_chat_id"]:
        try:
            staff_chat = await client.get_chat(config["staff_chat_id"])
            staff_chat_title = staff_chat.title
        except Exception as e:
            await log(client, f"Staff chat not Accesible, it says: {e}")
            staff_chat_title = "Not Accesible."

    else:
        staff_chat_title = "Not set yet ⚠️"

    if "ga_chat_id" in config and config["ga_chat_id"]:
        try:
            ga_chat = await client.get_chat(config["ga_chat_id"])
            ga_chat_title = ga_chat.title
        except Exception as e:
            await log(client, f"GA chat not Accesible, it says: {e}")
            ga_chat_title = "Not Accesible."

    else:
        ga_chat_title = "Not set ⚠️"

    assessment_form_link = (
        config["assessment_form_link"]
        if config["assessment_form_link"]
        else "Not set yet ⚠️"
    )

    current_settings = (
        f"<b>Staff Chat</b> 👥: {staff_chat_title}.\n\n"
        f"<b>Assessment Form Link</b> 📋: {assessment_form_link}.\n\n"
        f"<b>General Assembly Chat</b> 👥: {ga_chat_title}."
    )
    return current_settings


async def start_handler(client: Client, message: types.Message, db_client: MongoClient):
    admin = message.from_user
    await client.stop_listening(chat_id=admin.id)
    await client.stop_listening(
        listener_type=enums.ListenerTypes.CALLBACK_QUERY, chat_id=admin.id
    )

    reply_text = (
        f"Hello {admin.first_name}!, How is work going in MASA office?\n\n"
        "<b><u>Bot Current Settings</u></b>:\n\n"
        f"{await current_settings(client, db_client)}"
    )

    super_admin_id = db_client.masaBotDB.config.find_one({}, {"super_admin_id"})[
        "super_admin_id"
    ]
    is_super_admin = admin.id == super_admin_id
    await message.reply(reply_text, reply_markup=admin_keyboard(is_super_admin))


async def set_staff_chat_handler(
    client: Client, callback_query: types.CallbackQuery, db_client: MongoClient
):
    admin = callback_query.from_user
    await callback_query.message.delete()
    chat_criteria = types.RequestPeerTypeChat(is_bot_participant=True)
    request_group_button = types.KeyboardButton(
        text="Choose group", request_chat=chat_criteria
    )
    cancel_button = types.KeyboardButton(text="Cancel")

    request_group_keyboard = types.ReplyKeyboardMarkup(
        [[request_group_button], [cancel_button]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )

    await client.send_message(
        admin.id,
        "Please use the button to choose the staff chat and share it with the bot",
        reply_markup=request_group_keyboard,
    )
    while True:
        try:
            staff_chat_message = await client.listen(
                chat_id=callback_query.from_user.id,
                user_id=callback_query.from_user.id,
            )
        except (errors.ListenerStopped, asyncio.TimeoutError):
            return

        if not staff_chat_message or (
            staff_chat_message.text != "Cancel" and not staff_chat_message.chats_shared
        ):
            await staff_chat_message.reply("Please use one of the two buttons.")
            continue

        elif staff_chat_message.text == "Cancel":
            return await start_handler(client, staff_chat_message, db_client)

        staff_chat_id = staff_chat_message.chats_shared.chats[0].chat_id
        db_client.masaBotDB.config.update_one(
            {}, {"$set": {"staff_chat_id": staff_chat_id}}
        )
        break

    staff_chat = await client.get_chat(staff_chat_id)

    super_admin_id = db_client.masaBotDB.config.find_one({}, {"super_admin_id"})[
        "super_admin_id"
    ]
    is_super_admin = admin.id == super_admin_id

    try:
        await client.set_bot_commands(
            [
                types.BotCommand("reply", "send a reply to a bot user"),
                types.BotCommand(
                    "send", "send a message to a bot user (can contain media and files)"
                ),
                types.BotCommand("assign", "assign a custom name to a bot user"),
                types.BotCommand("help", "show bot manual"),
            ],
            scope=types.BotCommandScopeChat(staff_chat_id),
        )

        await client.send_message(
            staff_chat_id,
            "Hey <b>MASA team</b>!, I am your Hotline Manager Bot 🤖!\n\n"
            "I am looking forward to work with you 😇\n\n"
            "use /help to know how to use me!",
        )
    except errors.ChatWriteForbidden:
        await staff_chat_message.reply(
            "Please give the bot the right to send messages in staff group and try again ❌\n\n"
            "<b><u>Bot Current Settings</u></b>:\n\n"
            f"{await current_settings(client, db_client)}",
            reply_markup=admin_keyboard(is_super_admin),
        )
        return

    await staff_chat_message.reply(
        f"{staff_chat.title} has been set as the new staff chat ✅\n\n"
        "<b><u>Bot Current Settings</u></b>:\n\n"
        f"{await current_settings(client, db_client)}",
        reply_markup=admin_keyboard(is_super_admin),
    )


async def set_assesment_form_link_handler(
    client: Client, callback_query: types.CallbackQuery, db_client: MongoClient
):
    await callback_query.message.edit_text(
        "Please send the assessment form link", reply_markup=back_keyboard()
    )

    admin = callback_query.from_user
    try:
        assesssment_form_link_message = await client.listen(
            filters.text, chat_id=admin.id
        )
    except (errors.ListenerStopped, asyncio.TimeoutError):
        return

    form_link = assesssment_form_link_message.text

    confirm_button = types.InlineKeyboardButton(
        "Confirm ✅", callback_data="confirm_assessment_form_set"
    )
    cancel_button = types.InlineKeyboardButton(
        "Cancel ❌", callback_data="cancel_assessment_form_set"
    )
    options_keyboard = types.InlineKeyboardMarkup([[confirm_button], [cancel_button]])

    await callback_query.message.delete()

    await assesssment_form_link_message.reply(
        "Are you sure you want to set:\n\n"
        f"{form_link}\n\n"
        "As the new assesssment form link?",
        reply_markup=options_keyboard,
    )

    while True:
        try:
            callback_answer = await client.listen(
                filters=filters.regex(
                    r"^confirm_assessment_form_set$|^cancel_assessment_form_set$"
                ),
                chat_id=admin.id,
                user_id=admin.id,
                listener_type=enums.ListenerTypes.CALLBACK_QUERY,
            )
        except (errors.ListenerStopped, asyncio.TimeoutError):
            return

        if callback_answer and callback_answer.data == "confirm_assessment_form_set":
            db_client.masaBotDB.config.update_one(
                {}, {"$set": {"assessment_form_link": form_link}}
            )

            super_admin_id = db_client.masaBotDB.config.find_one(
                {}, {"super_admin_id"}
            )["super_admin_id"]
            is_super_admin = admin.id == super_admin_id
            return await callback_answer.message.edit_text(
                "New assessment form link has been set succefully ✅\n\n",
                reply_markup=back_keyboard(),
            )

        elif callback_answer.data == "cancel_assessment_form_set":
            return await back_handler(client, callback_answer, db_client)


async def set_ga_chat_handler(
    client: Client, callback_query: types.CallbackQuery, db_client: MongoClient
):
    admin = callback_query.from_user

    await callback_query.message.delete()
    chat_criteria = types.RequestPeerTypeChat(is_bot_participant=True)
    request_group_button = types.KeyboardButton(
        text="Choose group", request_chat=chat_criteria
    )
    remove_button = types.KeyboardButton(text="Remove GA membership check")
    cancel_button = types.KeyboardButton(text="Cancel")

    request_group_keyboard = types.ReplyKeyboardMarkup(
        [[request_group_button], [remove_button], [cancel_button]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )

    await client.send_message(
        admin.id,
        "Please use the buttons to change or remove the general assembly group chat (the bot must be in the group)\n\n"
        "<b><u>WARNING</u>: REMOVING THE GA GROUP CHECK WILL DISABLE THE GENERAL ASSEMBLY GROUP CHECK AND ANY USER CAN USE THE BOT.</b>",
        reply_markup=request_group_keyboard,
    )
    while True:
        try:
            ga_chat_message = await client.listen(
                chat_id=callback_query.from_user.id,
                user_id=callback_query.from_user.id,
            )
        except (errors.ListenerStopped, asyncio.TimeoutError):
            return

        if not ga_chat_message or (
            ga_chat_message.text not in ["Cancel", "Remove GA membership check"]
            and not ga_chat_message.chats_shared
        ):
            await ga_chat_message.reply("Please use one of the buttons.")
            continue

        elif ga_chat_message.text == "Remove GA membership check":
            db_client.masaBotDB.config.update_one({}, {"$set": {"ga_chat_id": None}})
            return await ga_chat_message.reply(
                "General assembly memebership check is disabled ✅\n\n"
                "Anyone can use the bot now, to re-enable the check set a GA group chat.",
                reply_markup=back_keyboard(),
            )

        elif ga_chat_message.text == "Cancel":
            return await start_handler(client, ga_chat_message, db_client)

        ga_chat_id = ga_chat_message.chats_shared.chats[0].chat_id
        db_client.masaBotDB.config.update_one({}, {"$set": {"ga_chat_id": ga_chat_id}})
        break

    ga_chat = await client.get_chat(ga_chat_id)

    await ga_chat_message.reply(
        f"<b>{ga_chat.title}</b> has been set as the new general assembly chat ✅\n\n"
        "Only members of this chat can use the bot, to disable the check:\n"
        'in the admin panel press "Set General Assembly Group" > "Remove GA membership check"',
        reply_markup=back_keyboard(),
    )


async def set_assesment_form_link_handler(
    client: Client, callback_query: types.CallbackQuery, db_client: MongoClient
):
    await callback_query.message.edit_text(
        "Please send the assessment form link", reply_markup=back_keyboard()
    )

    admin = callback_query.from_user
    try:
        assesssment_form_link_message = await client.listen(
            filters.text, chat_id=admin.id
        )
    except (errors.ListenerStopped, asyncio.TimeoutError):
        return

    form_link = assesssment_form_link_message.text

    confirm_button = types.InlineKeyboardButton(
        "Confirm ✅", callback_data="confirm_assessment_form_set"
    )
    cancel_button = types.InlineKeyboardButton(
        "Cancel ❌", callback_data="cancel_assessment_form_set"
    )
    options_keyboard = types.InlineKeyboardMarkup([[confirm_button], [cancel_button]])

    await assesssment_form_link_message.reply(
        "Are you sure you want to set:\n\n"
        f"{form_link}\n\n"
        "As the new assesssment form link?",
        reply_markup=options_keyboard,
    )

    while True:
        try:
            callback_answer = await client.listen(
                filters=filters.regex(
                    r"^confirm_assessment_form_set$|^cancel_assessment_form_set$"
                ),
                chat_id=admin.id,
                user_id=admin.id,
                listener_type=enums.ListenerTypes.CALLBACK_QUERY,
            )
        except (errors.ListenerStopped, asyncio.TimeoutError):
            return

        if callback_answer and callback_answer.data == "confirm_assessment_form_set":
            db_client.masaBotDB.config.update_one(
                {}, {"$set": {"assessment_form_link": form_link}}
            )

            super_admin_id = db_client.masaBotDB.config.find_one(
                {}, {"super_admin_id"}
            )["super_admin_id"]
            is_super_admin = admin.id == super_admin_id
            return await callback_answer.message.edit_text(
                "New assessment form link has been set succefully ✅\n\n",
                reply_markup=back_keyboard(),
            )

        elif callback_answer.data == "cancel_assessment_form_set":
            return await back_handler(client, callback_answer, db_client)


async def broadcast_handler(
    client: Client, callback_query: types.CallbackQuery, db_client: MongoClient
):
    await callback_query.message.edit_text(
        "Please Send the message you want to forward to all bot users.",
        reply_markup=back_keyboard(),
    )

    admin = callback_query.from_user
    try:
        mess_to_brod = await client.listen(chat_id=admin.id, user_id=admin.id)
    except (errors.ListenerStopped, asyncio.TimeoutError):
        return

    if not mess_to_brod:
        return

    confirm_button = types.InlineKeyboardButton(
        "Confirm ✅", callback_data="confirm_broadcast"
    )
    cancel_button = types.InlineKeyboardButton(
        "Cancel ❌", callback_data="cancel_broadcast"
    )
    options_keyboard = types.InlineKeyboardMarkup([[confirm_button], [cancel_button]])

    users_count = db_client.masaBotDB.users.count_documents({})
    await mess_to_brod.copy(admin.id)
    await mess_to_brod.reply(
        f"Are you sure you want to broadcast the previous message to all bot users ({users_count} users)?",
        reply_markup=options_keyboard,
    )

    while True:
        try:
            callback_answer = await client.listen(
                filters=filters.regex(r"^confirm_broadcast$|^cancel_broadcast$"),
                chat_id=admin.id,
                user_id=admin.id,
                listener_type=enums.ListenerTypes.CALLBACK_QUERY,
            )
        except (errors.ListenerStopped, asyncio.TimeoutError):
            return

        if not callback_answer:
            return

        elif callback_answer.data == "confirm_broadcast":
            await callback_answer.message.edit_text(
                "Broadcast started, I will notify you when I finish."
            )
            bot_users = db_client.masaBotDB.users.find({})
            sent = 0
            for user in bot_users:
                try:
                    await mess_to_brod.copy(user["_id"])
                    sent += 1
                except errors.FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                    await mess_to_brod.copy(user["_id"])
                    sent += 1
                except Exception as e:
                    print(e)

            await mess_to_brod.reply(
                f"This message has been succefully broadcasted to {sent} of bot users  ✅",
                reply_markup=back_keyboard(),
                quote=True,
            )
            return

        else:
            return await back_handler(client, callback_answer, db_client)


async def ban_user_handler(
    client: Client, callback_query: types.CallbackQuery, db_client: MongoClient
):
    admin = callback_query.from_user

    await callback_query.message.edit_text(
        "Please send the serial number of the user to ban from the bot",
        reply_markup=back_keyboard(),
    )

    while True:
        try:
            user_serial_message = await client.listen(
                filters.text, chat_id=admin.id, user_id=admin.id
            )
        except (errors.ListenerStopped, asyncio.TimeoutError):
            return

        if not user_serial_message:
            return

        elif not user_serial_message.text.isnumeric():
            await user_serial_message.reply(
                "Please send a valid serial number, you can try again.",
                reply_markup=back_keyboard(),
            )
            continue

        user_in_db = db_client.masaBotDB.users.find_one(
            {"serial_number": int(user_serial_message.text)}
        )

        if not user_in_db:
            await user_serial_message.reply(
                f"There is no a bot user with the serial number: {user_serial_message.text}, you can try again.",
                reply_markup=back_keyboard(),
            )
            continue
        user_name = f"<b>#{user_in_db['serial_number']}{' ('+user_in_db['custom_name']+')' if user_in_db['custom_name'] else ''}</b>"

        banned_users = db_client.masaBotDB.config.find_one({}, {"banned_users": 1})[
            "banned_users"
        ]
        if user_in_db["_id"] in banned_users:
            return await user_serial_message.reply(
                f"This user {user_name} is already banned from the bot"
            )

        db_client.masaBotDB.config.update_one(
            {}, {"$push": {"banned_users": user_in_db["_id"]}}
        )

        return await user_serial_message.reply(
            f"User {user_name} Has been banned from using the bot"
        )


async def add_admin_handler(
    client: Client, callback_query: types.CallbackQuery, db_client: MongoClient
):
    admin = callback_query.from_user
    await callback_query.message.edit_text(
        "Please send the username of the user to add as an admin for the bot",
        reply_markup=back_keyboard(),
    )

    while True:
        try:
            new_admin_username_message = await client.listen(
                filters.text, chat_id=admin.id, user_id=admin.id
            )
        except (errors.ListenerStopped, asyncio.TimeoutError):
            return

        try:
            new_admin = await client.get_users(new_admin_username_message.text)
        except Exception as e:
            print(f"fail to resolve new admin username, {e}")
            await new_admin_username_message.reply("Please send a valid username.")
        else:
            db_client.masaBotDB.config.update_one(
                {}, {"$push": {"admins_list": new_admin.id}}
            )
            await new_admin_username_message.reply(
                f"@{new_admin.username} is now one of the bot admins."
            )
            return


async def manage_admins_handler(
    client: Client, callback_query: types.CallbackQuery, db_client: MongoClient
):
    config = db_client.masaBotDB.config.find_one(
        {}, {"admins_list": 1, "super_admin_id": 1}
    )
    admins_ids_list, super_admin_id = config["admins_list"], config["super_admin_id"]

    if not callback_query.from_user.id == super_admin_id:
        return

    admins = await client.get_users(admins_ids_list)

    admins_list_text = "<b><u>Bot admins:</u></b>\n\n" + "\n\n".join(
        [
            (
                f"{'@'+admin.username if admin.username else admin.first_name}:\n/remove_admin_{admin.id}\n/transfer_super_admin_{admin.id}"
                if admin.id != callback_query.from_user.id
                else f"{'@'+admin.username if admin.username else admin.first_name} (You)"
            )
            for admin in admins
        ]
    )

    await callback_query.message.edit_text(
        admins_list_text, reply_markup=back_keyboard()
    )


async def remove_admin_handler(message: types.Message, db_client: MongoClient):
    config = db_client.masaBotDB.config.find_one(
        {}, {"admins_list": 1, "super_admin_id": 1}
    )
    admins_ids_list, super_admin_id = config["admins_list"], config["super_admin_id"]

    if not message.from_user.id == super_admin_id:
        return

    admin_to_remove_id = message.text.split("/remove_admin_")[-1]
    if not admin_to_remove_id.isnumeric():
        await message.reply("Invalid admin id.")
        return

    admin_to_remove_id = int(admin_to_remove_id)
    if admin_to_remove_id not in admins_ids_list:
        await message.reply("There is no an admin with the specified id.")
        return

    if admin_to_remove_id == message.from_user.id:
        return await message.reply(
            "You can't remove yourself from administratorship, transfer it to other user if you want."
        )

    db_client.masaBotDB.config.update_one(
        {}, {"$pull": {"admins_list": admin_to_remove_id}}
    )

    await message.reply(f"Admin removed succefully ✅.")


async def transfer_super_admin_handler(
    client: Client, message: types.Message, db_client: MongoClient
):
    config = db_client.masaBotDB.config.find_one(
        {}, {"admins_list": 1, "super_admin_id": 1}
    )
    admins_ids_list, super_admin_id = config["admins_list"], config["super_admin_id"]

    if not message.from_user.id == super_admin_id:
        return

    admin_to_promote_id = message.text.split("/transfer_super_admin_")[-1]
    if not admin_to_promote_id.isnumeric():
        await message.reply("Invalid admin id.")
        return

    admin_to_promote_id = int(admin_to_promote_id)
    if admin_to_promote_id not in admins_ids_list:
        await message.reply("There is no an admin with the specified id.")
        return

    if admin_to_promote_id == message.from_user.id:
        return await message.reply("You are already the superadmin.")

    confirm_button = types.InlineKeyboardButton(
        "Confirm ✅", callback_data="confirm_super_admin_transfer"
    )
    cancel_button = types.InlineKeyboardButton(
        "Cancel ❌", callback_data="cancel_super_admin_transfer"
    )
    options_keyboard = types.InlineKeyboardMarkup([[confirm_button], [cancel_button]])

    try:
        new_superadmin = await client.get_users(admin_to_promote_id)
        new_superadmin_name = (
            "@" + new_superadmin.username
            if new_superadmin.username
            else f"{new_superadmin.first_name} {new_superadmin.last_name or ''}"
        )
    except:
        new_superadmin_name = "This Admin"

    await message.reply(
        f"Are you sure you want to transfer the SuperAdmin powers to {new_superadmin_name}?\n\n"
        "This will make you a regular admin and he/she will be able to remove you from administiration.",
        reply_markup=options_keyboard,
    )

    while True:
        try:
            callback_answer = await client.listen(
                filters=filters.regex(
                    r"^confirm_super_admin_transfer$|^cancel_super_admin_transfer$"
                ),
                chat_id=message.from_user.id,
                user_id=message.from_user.id,
                listener_type=enums.ListenerTypes.CALLBACK_QUERY,
            )
        except (errors.ListenerStopped, asyncio.TimeoutError):
            return

        if callback_answer and callback_answer.data == "confirm_super_admin_transfer":
            db_client.masaBotDB.config.update_one(
                {}, {"$set": {"super_admin_id": admin_to_promote_id}}
            )
            return await callback_answer.message.edit_text(
                f"Superadmin powers transferred succefully ✅",
                reply_markup=back_keyboard(),
            )

        elif callback_answer.data == "cancel_super_admin_transfer":
            return await back_handler(client, callback_answer, db_client)


async def statistics_handler(
    callback_query: types.CallbackQuery, db_client: MongoClient
):
    await callback_query.message.edit_text(
        "<b><i>Preparing Hotline statistics ⏳</i></b>"
    )
    stats = db_client.masaBotDB.statistics.find_one({})
    users_count = db_client.masaBotDB.users.count_documents({})
    form_fillers_count = db_client.masaBotDB.users.count_documents(
        {"filled_form": True}
    )
    form_fillers = db_client.masaBotDB.users.find({"filled_form": True})
    form_non_fillers = db_client.masaBotDB.users.find({"filled_form": False})

    form_fillers_user_names = (
        ".\n".join(
            [
                f"<b>#{user['serial_number']}{' ('+user['custom_name']+')' if user['custom_name'] else ''}</b>"
                for user in form_fillers
            ]
        )
        or "No users."
    )

    form_non_fillers_user_names = (
        ".\n".join(
            [
                f"<b>#{user['serial_number']}{' ('+user['custom_name']+')' if user['custom_name'] else ''}</b>"
                for user in form_non_fillers
            ]
        )
        or "No users"
    )

    stats_report_text = (
        "<b><u>Hotline Statistics:</u></b>\n\n"
        f"<b>Users who started the bot</b>: {users_count}.\n"
        f"<b>Users who filled the form</b>: {form_fillers_count}.\n"
        f"<b>Messages sent by the staff to bot users</b>: {stats['staff_replies_counter']}.\n"
        f"<b>Messages sent by bot users to staff</b>: {stats['users_messages_counter']}.\n\n\n"
        f"<b>Users who filled the form</b>:\n{form_fillers_user_names}.\n\n"
        f"<b>Users who didn't fill the form</b>:\n{form_non_fillers_user_names}."
    )

    await callback_query.message.edit_text(
        stats_report_text, reply_markup=back_keyboard()
    )


async def unban_button_handler(
    callback_query: types.CallbackQuery, db_client: MongoClient
):
    banned_users_ids = db_client.masaBotDB.config.find_one({}, {"banned_users": 1})[
        "banned_users"
    ]
    banned_users = db_client.masaBotDB.users.find({"_id": {"$in": banned_users_ids}})
    banned_users = [user for user in banned_users]

    if banned_users:
        banned_users_text = "<b><u>Banned Users</u></b>:\n\n" + "\n\n".join(
            [
                f"<b>#{user['serial_number']}{' ('+user['custom_name']+')' if user['custom_name'] else ''}</b>\t/unban_{user['serial_number']}"
                for user in banned_users
            ]
        )
    else:
        banned_users_text = "<b>No Banned Users</b>"

    await callback_query.message.edit_text(
        banned_users_text, reply_markup=back_keyboard()
    )


async def unban_user_handler(message: types.Message, db_client: MongoClient):
    serial_number = message.text.split("/unban_")[-1]
    if not serial_number.isnumeric():
        await message.reply(
            "Please use the unban command like `/unban_serialnumber` e.g `/unban_1`"
        )
        return

    banned_users_ids = db_client.masaBotDB.config.find_one({}, {"banned_users": 1})[
        "banned_users"
    ]
    user_to_unban = db_client.masaBotDB.users.find_one(
        {"serial_number": int(serial_number)}
    )

    if not user_to_unban or user_to_unban["_id"] not in banned_users_ids:
        await message.reply(
            f"Ther is no banned user with the serial number: {serial_number}"
        )
        return

    db_client.masaBotDB.config.update_one(
        {}, {"$pull": {"banned_users": user_to_unban["_id"]}}
    )

    await message.reply(f"User #{serial_number} has been unbanned succefully ✅")


async def back_handler(
    client: Client, callback_query: types.CallbackQuery, db_client: MongoClient
):
    admin = callback_query.from_user
    await client.stop_listening(chat_id=admin.id)
    await client.stop_listening(
        listener_type=enums.ListenerTypes.CALLBACK_QUERY, chat_id=admin.id
    )

    settings = (
        "<b><u>Bot Current Settings</u></b>:\n\n"
        f"{await current_settings(client, db_client)}"
    )

    super_admin_id = db_client.masaBotDB.config.find_one({}, {"super_admin_id"})[
        "super_admin_id"
    ]
    is_super_admin = admin.id == super_admin_id
    await callback_query.message.edit_text(
        settings, reply_markup=admin_keyboard(is_super_admin)
    )
