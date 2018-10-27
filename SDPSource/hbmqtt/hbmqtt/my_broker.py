import logging
import asyncio
from .plugins.authority_chain import authority_chain
from .broker import Broker


class my_broker(Broker):
    def __init__(self, config=None, loop=None, plugin_namespace=None):
        Broker.__init__(self, config=config, loop=loop, plugin_namespace=plugin_namespace)
        self._authority_chain = authority_chain()

    def del_subscription(self, a_filter, session):
        self._del_subscription(a_filter, session)

    def del_authority(self, topic, users, recursive=True):
        members = self._get_topic(topic)
        
        for member in members:
            member.del_users(users, recursive=recursive)
            for user in users:
                session = self._sessions.get(user)
                if session:
                    self._del_subscription(topic, session)

    def __getattr__(self, attr):
        return getattr(self._authority_chain, attr)
