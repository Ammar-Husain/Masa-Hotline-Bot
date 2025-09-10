from threading import Thread

from flask import Flask


def run_server():
    server = Flask(__name__)

    @server.route("/", methods=["GET"])
    def greet():
        print("Request")
        return "MASA Hotline Bot is UP!"

    def flask_thread():
        server.run("0.0.0.0", port=8000)

    thread = Thread(target=flask_thread)
    thread.start()
