import asyncio
import os

from pymongo import MongoClient
from pyrogram import Client, enums, errors, filters, types

from models.user import User
from utils.log import log

is_production = os.getenv("PRODUCTION", None)
if not is_production or is_production == "0":
    import dotenv

    dotenv.load_dotenv()

GA_CHAT_ID = int(os.getenv("GA_CHAT_ID", "0"))


def user_keyboard():
    contact_staff_button = types.InlineKeyboardButton(
        "التواصل مع أعضاء فريق الدعم  😇", callback_data="contact_staff"
    )
    refill_form_button = types.InlineKeyboardButton(
        "ملْء الفورم مجدداً  🔄", callback_data="refill_form"
    )
    keyboard = types.InlineKeyboardMarkup(
        [[contact_staff_button], [refill_form_button]]
    )
    return keyboard


def filled_form_keyboard(refill: bool = False):
    filled_form_button = types.InlineKeyboardButton(
        "لقد ملأتُ الفورم ✅", callback_data="filled_form"
    )

    back_button = types.InlineKeyboardButton("رجوع", callback_data="user_back")

    keyboard = types.InlineKeyboardMarkup(
        [[filled_form_button]] + ([[back_button]] if refill else [[]])
    )
    return keyboard


def back_keyboard():
    back_button = types.InlineKeyboardButton("رجوع", callback_data="user_back")
    keyboard = types.InlineKeyboardMarkup([[back_button]])
    return keyboard


async def start_handler(
    client: Client, message: types.Message, db_client: MongoClient
) -> None:
    user = message.from_user
    await client.stop_listening(chat_id=user.id)
    await client.stop_listening(
        listener_type=enums.ListenerTypes.CALLBACK_QUERY, chat_id=user.id
    )

    config = db_client.masaBotDB.config.find_one({})

    # Bot is not configured yet
    if not config or not config["assessment_form_link"] or not config["staff_chat_id"]:
        return await message.reply("عذراً، البوت تحت الصيانة الرجاء المحاولة لاحقاً 😇.")

    # general assembly chat membership check is required
    if GA_CHAT_ID:
        try:
            await client.get_chat_member(GA_CHAT_ID, user.id)
        except errors.UserNotParticipant:
            await message.reply(
                """عذراً ❌، هذه الخدمة متاحة حالياً لطلبة كلية الطب جامعة الخرطوم، إذا كنت طالباّ في كلية الطب جامعة الخرطوم الرجاء التأكد بإنك تراسل البوت عن طريق حسابك الموجود في مجموعة الجمعية العمومية لرابطة طلاب كلية الطب جامعة الخرطوم."""
            )
            return
        except Exception as e:
            await log(client, str(e))

    user_in_db = db_client.masaBotDB.users.find_one({"_id": user.id})

    # user is starting the bot for the first time
    if not user_in_db:
        user_serial = db_client.masaBotDB.users.count_documents({}) + 1
        new_user = User(id=user.id, serial_number=user_serial, filled_form=False)
        db_client.masaBotDB.users.insert_one(new_user.as_dict())

        await message.reply(
            "أهلاً بك في بوت الخط الساخن الخاص ب MASA!\n"
            "إذا كنت تحتاج إلى المساعدة فنحن هنا دائماً لأجلك.\n\n"
            "الرجاء ملء الفورم التالي لمساعدتنا في معرفة ما تمرّ به وكيف يمكننا مساعدتك 😇\n"
            f"{config["assessment_form_link"]}\n\n"
            f"<b><u>your serial number is:</u></b> {user_serial}\n\n\n"
            "نحيطكم علماً بأن هويتكم وجميع البيانات التي تقدمونها يتم التعامل بها بمجهولية تامة ولا يستطيع حتى العاملون في MASA معرفة هوية مقدمي الطلبات 👤.",
            reply_markup=filled_form_keyboard(),
        )
        return

    # user has started the bot before, but didn't fill the form yet
    elif not user_in_db["filled_form"]:
        await message.reply(
            "مرحباً, الرجاء ملء الفورم التالي لمساعدتنا في معرفة ما تمرّ به وكيف يمكننا مساعدتك 😇\n"
            f"{config["assessment_form_link"]}\n\n"
            f"<b><u>your serial number is:</u></b> {user_in_db["serial_number"]}",
            reply_markup=filled_form_keyboard(),
        )
        return

    # user filled the form before
    await message.reply(
        f"مرحباً المستخدم #<b>{user_in_db["serial_number"]}</b>!، نرجو أنك بخير 😇\n"
        "يمكنك دائماً التواصل بسرية مع فريق MASA على هذا الخط الساخن وسيجيبك أعضاء الفريق في أقرب وقت ممكن!",
        reply_markup=user_keyboard(),
    )


async def filled_form_handler(
    client: Client, callback_query: types.CallbackQuery, db_client: MongoClient
):
    user_in_db = db_client.masaBotDB.users.find_one(
        {"_id": callback_query.from_user.id}
    )
    if not user_in_db:
        return

    # ensure staff chat is configured
    config = db_client.masaBotDB.config.find_one({})
    if not config or not config["staff_chat_id"]:
        return callback_query.message.edit_text(
            "عذراً، البوت تحت الصيانة حاليا ❌.\n" "الرجاء المحاولة لاحقاً."
        )

    user_name = f"<b>#{user_in_db['serial_number']}{' ('+user_in_db['custom_name']+')' if user_in_db['custom_name'] else ''}</b>"

    try:
        # inform staff chat that the user filled the form
        await client.send_message(
            config["staff_chat_id"],
            f"""
                User {user_name} Says that he/she filled the form, please check and reply to him with the reply command.
            """,
        )
    except Exception as e:
        await log(client, f"Error sending message in staff chat {e}")

        # tell the admins that the bot wasn't able to send messsages in staff chat
        for admin_id in config["admins_list"]:
            try:
                await client.send_message(
                    admin_id,
                    f"User {user_name} said he/she filled the form\n."
                    "Bot wasn't able to access the staff chat, please ensure that "
                    "the staff chat is set and that the bot is a member in the staff chat and has the permission to send messages there.",
                )
            except Exception as e:
                await log(client, f"Failed to message admin {admin_id}, it says: {e}")

    else:
        # the staff chat was notified succeffuly
        await callback_query.message.edit_text(
            "شكراً جزيلاً، سيقوم فريق MASA بالرد عليك في أقرب وقت ممكن 😇",
            reply_markup=back_keyboard(),
        )

    db_client.masaBotDB.users.update_one(
        {"_id": callback_query.from_user.id}, {"$set": {"filled_form": True}}
    )


async def refill_form_handler(
    callback_query: types.CallbackQuery, db_client: MongoClient
):
    user_in_db = db_client.masaBotDB.users.find_one(
        {"_id": callback_query.from_user.id}
    )
    if not user_in_db:
        return

    # ensure staff chat is confiugred
    config = db_client.masaBotDB.config.find_one({})
    if not config or not config["assessment_form_link"]:
        return callback_query.message.edit_text(
            "عذراً، البوت تحت الصيانة حاليا ❌.\n" "الرجاء المحاولة لاحقاً."
        )

    filled_form_button = types.InlineKeyboardButton(
        "لقد ملأتُ الفورم ✅", callback_data="filled_form"
    )

    # send the form the user
    await callback_query.message.edit_text(
        "يمكن إعادة ملء الفورم على الرابط التالي:\n"
        f"{config["assessment_form_link"]}\n\n"
        f"your serial number is {user_in_db["serial_number"]}",
        reply_markup=filled_form_keyboard(refill=True),
    )


async def contact_staff_handler(
    client: Client, callback_query: types.CallbackQuery, db_client: MongoClient
):
    user_in_db = db_client.masaBotDB.users.find_one({})
    if not user_in_db:
        return

    # ensure the staff chat is configured
    config = db_client.masaBotDB.config.find_one({})
    if not config or not config["staff_chat_id"]:
        return await callback_query.message.edit_text(
            "عذراً، البوت تحت الصيانة حاليا ❌.\n" "الرجاء المحاولة لاحقاً.",
            reply_markup=back_keyboard(),
        )

    user = callback_query.from_user

    await callback_query.message.edit_text(
        "الرجاء إرسال رسالتك النصية وسيتم تحويلها إلى فريق MASA بسرية 😇",
        reply_markup=back_keyboard(),
    )
    try:
        message_to_staff = await client.listen(
            filters.text, chat_id=user.id, user_id=user.id
        )
    except (errors.ListenerStopped, asyncio.TimeoutError):
        return
    if not message_to_staff:
        return

    confirm_button = types.InlineKeyboardButton("تأكيد ✅", callback_data="confirm")
    cancel_button = types.InlineKeyboardButton("إلغاء ❌", callback_data="user_back")
    options_keyboard = types.InlineKeyboardMarkup([[confirm_button], [cancel_button]])

    await client.send_message(
        user.id,
        "الرجاء التأكيد بإنك ترغب بإرسال:\n\n"
        f'"<b>{message_to_staff.text}"</b>\n\n'
        "إلى العاملين في فريق MASA 😇",
        reply_markup=options_keyboard,
    )

    try:
        callback_answer = await client.listen(
            filters=filters.regex(r"^confirm$|^user_back$"),
            chat_id=user.id,
            user_id=user.id,
            listener_type=enums.ListenerTypes.CALLBACK_QUERY,
        )
    except (errors.ListenerStopped, asyncio.TimeoutError):
        return

    if not callback_answer:
        return

    user_in_db = db_client.masaBotDB.users.find_one({"_id": user.id})
    if not user_in_db:
        return

    if callback_answer.data == "user_back":
        return await back_handler(client, callback_answer, db_client)

    user_name = f"<b>#{user_in_db['serial_number']}{' ('+user_in_db['custom_name']+')' if user_in_db['custom_name'] else ''}</b>"
    message_text = (
        f"Hey MASA staff!, User {user_name} sended this message to you!\n\n"
        f'<b>"{message_to_staff.text}"</b>\n\n'
        "you can reply to him using the /reply command."
    )
    try:
        await client.send_message(config["staff_chat_id"], message_text)
    except Exception as e:
        print(f"Bot wasn't able to send message in staff chat, it says: {e}")
        callback_answer.message.edit_text(
            "عذراً، البوت تحت الصيانة حاليا ❌.\n" "الرجاء المحاولة لاحقاً."
        )
    else:
        db_client.masaBotDB.statistics.update_one(
            {}, {"$inc": {"users_messages_counter": 1}}
        )
        await callback_answer.message.edit_text(
            """
                استلم أعضاء فريق MASA رسالتك، وسيتم الرد عليك في أقرب وقت ممكن ✅
            """,
            reply_markup=back_keyboard(),
        )
    finally:
        return


async def back_handler(
    client: Client, callback_query: types.CallbackQuery, db_client: MongoClient
):
    user = callback_query.from_user
    await client.stop_listening(chat_id=user.id)
    await client.stop_listening(
        listener_type=enums.ListenerTypes.CALLBACK_QUERY, chat_id=user.id
    )

    config = db_client.masaBotDB.config.find_one({})

    # Bot is not configured yet
    if not config or not config["assessment_form_link"] or not config["staff_chat_id"]:
        return

    # general assembly chat membership check is required
    if GA_CHAT_ID:
        try:
            await client.get_chat_member(ga_chat_id, user.id)
        except Exception as e:
            return

    user_in_db = db_client.masaBotDB.users.find_one({"_id": user.id})

    if not user_in_db or not user_in_db["filled_form"]:
        return

    await callback_query.message.edit_text(
        f"مرحباً المستخدم <b>#{user_in_db["serial_number"]}</b>!، نرجو أنك بخير 😇\n"
        "يمكنك دائماً التواصل بسرية مع فريق MASA على هذا الخط الساخن وسيجيبك أعضاء الفريق في أقرب وقت ممكن!",
        reply_markup=user_keyboard(),
    )
