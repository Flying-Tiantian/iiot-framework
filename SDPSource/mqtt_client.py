#!/usr/bin/python3

import logging
import asyncio

from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

from hbmqtt.session import ApplicationMessage
from mqtt_config import CONFIG_CLIENT as CONFIG

from params import params

import pickle

logger = logging.getLogger()

class mqtt_client(MQTTClient):
    def __init__(self, client_id=None, config=CONFIG, loop=None):
        MQTTClient.__init__(self, client_id, config, loop)

    def connect(self, username=None, password=None):
        if username and password:
            uri = CONFIG['broker']['uri']
            header = uri.split(':')[0]
            addr = uri.split('@')[-1]
            uri = header + '://' + str(username) + ':' + str(password) + '@' + addr
        else:
            uri = self.config['broker']['uri']
        self.logger.debug("MQTT client connect to %s" % uri)
        # yield from MQTTClient.connect(self, uri=uri)
        self._loop.run_until_complete(MQTTClient.connect(self, uri=uri))

    def publish(self, message, topic=None, qos=None, retain=None):
        if not topic:
            topic = 'devices/' + self.session.username

        if isinstance(message, str):
            message = bytes(message, encoding='utf-8')
        elif isinstance(message, object):
             message = pickle.loads(message)
        else:
            message = bytes(str(message), encoding='utf-8')
        # yield from MQTTClient.publish(self, topic, message, qos=qos, retain=retain)
        self._loop.run_until_complete(MQTTClient.publish(self, topic, message, qos=qos, retain=retain))

    def disconnect(self):
        self._loop.run_until_complete(MQTTClient.disconnect(self))

@asyncio.coroutine
def test_coro():
    C = mqtt_client(client_id='test', config=CONFIG)
    yield from C.connect()
    tasks = [
        asyncio.ensure_future(C.publish(b'TEST MESSAGE WITH QOS_0', qos=QOS_0)),
        asyncio.ensure_future(C.publish(b'TEST MESSAGE WITH QOS_1', qos=QOS_1)),
        asyncio.ensure_future(C.publish(b'TEST MESSAGE WITH QOS_2', qos=QOS_2)),
        asyncio.ensure_future(C.publish(b'TEST MESSAGE WITH QOS_2', topic='devices/a', qos=QOS_2)),
    ]
    yield from asyncio.wait(tasks)
    logger.info("messages published")
    yield from C.disconnect()

def test():
    C = mqtt_client(client_id='test', config=CONFIG)
    C.connect('test', 'test')
    C.publish('TEST MESSAGE WITH QOS_0', topic='devices/test', qos=QOS_0)
    C.publish('TEST MESSAGE WITH QOS_1', topic='devices/test', qos=QOS_1)
    C.publish('TEST MESSAGE WITH QOS_2', topic='devices/test', qos=QOS_2)
    C.disconnect()

if __name__ == '__main__':
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=formatter)
    # asyncio.get_event_loop().run_until_complete(test_coro())
    # asyncio.get_event_loop().run_forever()
    test()

    
