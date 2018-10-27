import asyncio
from .authority_chain import authority_chain


class BaseTopicPlugin:
    def __init__(self, context):
        self.context = context
        try:
            self.topic_config = self.context.config['topic-check']
        except KeyError:
            self.context.logger.warning("'topic-check' section not found in context configuration")

    def topic_filtering(self, *args, **kwargs):
        if not self.topic_config:
            # auth config section not found
            self.context.logger.warning("'topic-check' section not found in context configuration")
            return False
        return True

class TopicTabooPlugin(BaseTopicPlugin):
    def __init__(self, context):
        super().__init__(context)
        self._taboo = ['prohibited', 'top-secret', 'data/classified']

    @asyncio.coroutine
    def topic_filtering(self, *args, **kwargs):
        filter_result = super().topic_filtering(*args, **kwargs)
        if filter_result:
            session = kwargs.get('session', None)
            topic = kwargs.get('topic', None)
            if session.username and topic:
                if session.username != 'admin' and topic in self._taboo:
                    return False
                return True
            else:
                return False
        return filter_result

class MTopicFilterPlugin(BaseTopicPlugin):
    def __init__(self, context):
        super().__init__(context)
        self._authority_chain = authority_chain()

    def _topic_filtering(self, topic, username):
        filter_result = super().topic_filtering()
        if filter_result:
            r = self._authority_chain.check_authority(topic, username)
            self.context.logger.debug("Accessing my topic filter, topic: %s, username: %s, result %s" % (topic, username, str(r)))
            return r

    @asyncio.coroutine
    def subscribe_topic_filtering(self, *args, **kwargs):
        self.context.logger.debug("Accessing subscribe topic filter")
        session = kwargs.get('session', None)
        topic = kwargs.get('topic', None)
        r = self._topic_filtering(topic, session.username)
        if not r:
            self.context.logger.warning("Unauthorized access: phase subscribe, username %s, topic %s" % (session.username, topic))
        return r

    @asyncio.coroutine
    def publish_topic_filtering(self, *args, **kwargs):
        self.context.logger.debug("Accessing publish topic filter")
        session = kwargs.get('session', None)
        topic = kwargs.get('topic', None)
        r = self._topic_filtering(topic, session.username)
        if not r:
            self.context.logger.warning("Unauthorized access: phase publish, username %s, topic %s" % (session.username, topic))
        return r

    @asyncio.coroutine
    def on_broker_client_connected(self, *args, **kwargs):
        session = kwargs.get('session', None)
        topic = 'devices/' + session.username
        self._authority_chain.add_topic(topic, inherit=False)
        self._authority_chain.add_authority(topic, [session.username])
        self.context.logger.debug("Client connected: username %s\n[AUTHORITY_CHAIN]:\n%s" % (session.username, str(self._authority_chain)))

    @asyncio.coroutine
    def on_broker_client_disconnected(self, *args, **kwargs):
        session = kwargs.get('session', None)
        self._authority_chain.del_topic('devices/' + session.username)
        self.context.logger.debug("Client disconnected: username %s\n[AUTHORITY_CHAIN]:\n%s" % (session.username, str(self._authority_chain)))
