#!/usr/bin/python3
from secure_socket import secure_socket
from multiprocessing import Process
from threading import Thread
import threading
from socketserver import ThreadingTCPServer, StreamRequestHandler, TCPServer
from log import get_logger
from protocol import list_update_packet, data_packet, mqtt_info_packet
import socket
from access_policy import monitored_dict
from params import params
import traceback
import time
import signal
from mqtt_client import mqtt_client

LOGGER = get_logger()


class peers_handler(StreamRequestHandler):
    def handle(self):
        try:
            sock = secure_socket(self.request)
            while True:
                obj = sock.recv_obj()
                if isinstance(obj, data_packet):
                    if params.test_mode:
                        LOGGER.critical('Data from peer:' + str(obj))
        except:
            pass
        finally:
            sock.close()


class device_handler(StreamRequestHandler):
    def __init__(self, *args, **kwargs):
        self._logger = get_logger()
        self._availiable_hosts = {}
        self._peer_socks_lock = threading.Lock()
        self._peer_socket = {}
        self._mqtt_client = mqtt_client()
        StreamRequestHandler.__init__(self, *args, **kwargs)

    def connect_peer(self, ID, addr):
        ip = addr.split(':')[0]
        port = int(params.peer_port)  # int(addr.split(':')[1])

        addr = ip + str(port)

        with self._peer_socks_lock:
            if ID in self._peer_socket:
                self._peer_socket[ID].close()
            self._peer_socket[ID] = secure_socket()

        for _ in range(5):
            try:
                with self._peer_socks_lock:
                    self._peer_socket[ID].connect((ip, port), timeout=5)
            except TimeoutError:
                time.sleep(5)
            except:
                return
            else:
                self._logger.info("Connected to peer %s on %s." % (ID, addr))
                return

        self._logger.warning("Fail to connect to peer %s on %s." % (ID, addr))

    def add_peer(self, ID, addr):
        Thread(target=self.connect_peer, args=(ID, addr), daemon=True).start()

    def handle(self):
        try:
            self._logger.info("Device connected.")

            sock = secure_socket(self.request, secure=False)

            while True:
                obj = sock.recv_obj()

                if isinstance(obj, mqtt_info_packet):
                    self._logger.info(
                        "Receive mqtt info packet from device:\n%s" % str(obj))
                    self._mqtt_client.connect(obj.username, obj.password)

                elif isinstance(obj, data_packet):
                    self._logger.info(
                        "Receive data packet from device:\n%s" % str(obj))
                    self._mqtt_client.publish(obj.data)
                    with self._peer_socks_lock:
                        for peer_sock in self._peer_socket.values():
                            try:
                                peer_sock.send_obj(obj)
                            except:
                                pass

                elif isinstance(obj, list_update_packet):
                    available_hosts = obj.available_hosts
                    self._logger.info(
                        "Receive list update packet from proxy:\n%s" % str(obj))

                    if 'add' in available_hosts:
                        for ID, addr in available_hosts['add'].items():
                            self.add_peer(ID, addr)
                    if 'remove' in available_hosts:
                        for ID, addr in available_hosts['remove'].items():
                            with self._peer_socks_lock:
                                peer_sock = self._peer_socket.pop(ID, None)
                            if peer_sock:
                                peer_sock.close()
                    if 'refresh' in available_hosts:
                        with self._peer_socks_lock:
                            for peer_sock in self._peer_socket.values():
                                peer_sock.close()
                            self._peer_socket.clear()
                        for ID, addr in available_hosts['refresh'].items():
                            self.add_peer(ID, addr)
        except BaseException as e:
            self._logger.info("Device monitor handler closed.(%s)" % str(e))
            traceback.print_exc()
        finally:
            self._mqtt_client.disconnect()
            with self._peer_socks_lock:
                for s in self._peer_socket.values():
                    s.close()
                self._peer_socket.clear()
            sock.close()


class device_monitor(Process):
    def __init__(self):
        super().__init__()
        addr = params.proxy_address_inside
        self._proxy_addr = addr
        self._proxy_ip = addr.split(':')[0]
        self._proxy_port = int(addr.split(':')[1])
        self._logger = get_logger()

    def run(self):
        def signal_func(sig, stack):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, signal_func)
        try:
            self._logger.info("Start listening for other host's access.")
            addr = params.peer_address
            access_ip = addr.split(':')[0]
            access_port = int(addr.split(':')[1])
            peer_server = ThreadingTCPServer(
                (access_ip, access_port), peers_handler)
            peer_server.socket = secure_socket(sock=peer_server.socket, server_side=True)

            listening_thread = threading.Thread(target=peer_server.serve_forever)
            listening_thread.setDaemon(True)
            listening_thread.start()

            self._logger.info(
                "Device monitor start, listening %s." % self._proxy_addr)
            device_server = TCPServer(
                (self._proxy_ip, self._proxy_port), device_handler)
            device_server.serve_forever()
        except KeyboardInterrupt:
            self._logger.info("Device monitor receive KeyboardInterrupt.")
            device_server.shutdown()
            device_server.server_close()
            peer_server.shutdown()
            peer_server.server_close()
            self._logger.info("Device monitor closed.")

if __name__ == '__main__':
    monitor = device_monitor()
    monitor.run()
