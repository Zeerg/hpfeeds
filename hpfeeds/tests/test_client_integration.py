import asyncio
import logging
import threading
import unittest

from hpfeeds.broker.auth.memory import Authenticator
from hpfeeds.broker.server import Server
from hpfeeds.client import Client
from hpfeeds.protocol import readpublish


class TestClientIntegration(unittest.TestCase):

    log = logging.getLogger('hpfeeds.testserver')

    def _server_thread(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.server_future = loop.create_future()

        async def inner():
            authenticator = Authenticator({
                'test': {
                    'secret': 'secret',
                    'subchans': ['test-chan'],
                    'pubchans': ['test-chan'],
                    'owner': 'some-owner',
                }
            })

            self.server = Server(authenticator, '127.0.0.1', 20000)

            self.log.debug('Starting server')
            future = asyncio.ensure_future(self.server.serve_forever())

            self.log.debug('Awaiting test teardown')
            await self.server_future

            self.log.debug('Stopping test server')
            future.cancel()
            await future

        loop.run_until_complete(inner())

    def setUp(self):
        self.server_thread = threading.Thread(
            target=self._server_thread,
        )
        self.server_thread.start()

    def test_subscribe_and_publish(self):
        c = Client('127.0.0.1', 20000, 'test', 'secret')
        c.subscribe('test-chan')
        c._subscribe()
        c.publish('test-chan', b'data')
        opcode, data = c._read_message()
        assert opcode == 3
        assert readpublish(data) == ('test', 'test-chan', b'data')
        self.log.debug('Stopping client')
        c.stop()
        self.log.debug('Closing client')
        c.close()

    def tearDown(self):
        self.log.debug('Cancelling future')
        self.server_future.set_result(None)
        self.log.debug('Waiting')
        self.server_thread.join()
        assert len(self.server.connections) == 0, 'Connection left dangling'
