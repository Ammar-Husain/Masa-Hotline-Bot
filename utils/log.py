import os

is_production = os.getenv("PRODUCTION", None)
if not is_production or is_production == "0":
    import dotenv

    dotenv.load_dotenv()

LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))


async def log(client, message):
    if len(message) >= 4096:
        message = message[:4000]
    return await client.send_message(LOG_CHANNEL_ID, message)
