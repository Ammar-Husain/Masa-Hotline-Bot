import dns.resolver
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi


def connect_to_db(db_uri: str) -> MongoClient:
    dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers = ["8.8.8.8"]

    client = MongoClient(db_uri, server_api=ServerApi("1"))
    return client
