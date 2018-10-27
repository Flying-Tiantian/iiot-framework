#!/usr/bin/python3

import asyncio
import logging
from hbmqtt.my_broker import my_broker as Broker
from mqtt_config import CONFIG_BROKER as CONFIG

@asyncio.coroutine
def broker_coro():
    broker = Broker(config=CONFIG)
    yield from broker.start()


if __name__ == '__main__':
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=formatter)
    event_loop = asyncio.get_event_loop()
    event_loop.run_until_complete(broker_coro())
    asyncio.get_event_loop().run_forever()