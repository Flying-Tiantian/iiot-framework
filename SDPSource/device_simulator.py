#!/usr/bin/python3

from multiprocessing import Process
from secure_socket import secure_socket
from authentication import client_end, auth_packet
from protocol import data_packet, mqtt_info_packet
from log import get_logger
import traceback
import socket
import os
import sys
import time
import signal
import random
from params import params
from threading import Thread
from iptables_api import *


class device(Thread):
    def __init__(self, ID=None, addr=None, data_interval=5, fault_interval=5):
        super().__init__()
        self._ID = ID
        self._addr = addr
        self._data_interval = data_interval
        self._fault_interval = fault_interval
        # self._sock = secure_socket()
        self._logger = get_logger()

    def run(self):
        # time.sleep(5)
        def signal_func(sig, stack):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, signal_func)
        self._logger.info("Device simulator start.")
        firewall_init(None)
        while True:
            try:
                self._sock = secure_socket()
                if self._ID:
                    device_ID = self._ID
                else:
                    device_ID = params.device_ID

                if self._addr:
                    addr = self._addr
                else:
                    addr = params.update_monitor_addr()

                ip = addr.split(':')[0]
                port = int(addr.split(':')[1])

                self._logger.info("Connect to %s." % addr)
                self._sock.connect((ip, port), timeout=5)

                self._logger.info("Connected to %s, send auth_info..." % addr)
                auth_obj = client_end(self._sock)

                if auth_obj.auth_to_server():
                    self._sock.send_obj(mqtt_info_packet(str(device_ID), str(device_ID), str(device_ID)))
                    while True:
                        self._logger.info("Device send data to monitor.")
                        self._sock.send_obj(data_packet(
                            'Data from ' + str(device_ID)))
                        time.sleep(self._data_interval)
                else:
                    raise Exception
            except KeyboardInterrupt:
                self._logger.info(
                    "Device simulator receive KeyboardInterrupt, quit.")
                break
            except BaseException as e:
                self._addr = None
                self._logger.warning(
                    "Device simulator %s fail to connect docker %s!(%s)" % (device_ID, addr, str(e)))
                traceback.print_exc()
                time.sleep(self._fault_interval * (1 + random.random()))
            finally:
                self._sock.close()
                # firewall_open_all()

    def shutdown(self):
        self._sock.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        monitor_addr = sys.argv[1]
    else:
        monitor_addr = None
    simulator = device(ID=params.device_ID, addr=monitor_addr)
    simulator.run()
