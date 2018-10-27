#!/usr/bin/python3

import os
import sys
import time
import traceback
import threading
import socketserver
import socket
import select
from params import params
from socket import timeout as SOCKET_TIMEOUT
from protocol import *
from iptables_api import *
from authentication import client_end
from secure_socket import secure_socket, DisconnectException, valid_ip
from access_policy import monitored_dict
from log import get_logger
import device_simulator
import signal

class ControllerFault(Exception):
    pass


class UnknowndeviceException(Exception):
    pass


class LocalServiceFault(Exception):
    pass


def check_addr(addr):
    if isinstance(addr, str):
        ip = addr.split(':')[0]
        port = addr.split(':')[1]
        if valid_ip(ip):
            try:
                int(port)
            except:
                pass
            else:
                return True
    return False


class request_handler(socketserver.StreamRequestHandler):
    def __init__(self, *args, **kwargs):
        self._logger = get_logger()

        addr = params.controller_address
        if not addr:
            self._logger.error("Can't get controller address!")
            raise ControllerFault
        else:
            self.controller_address = addr

        self.proxy_address = params.proxy_address_inside

        self._accept_hosts = monitored_dict()
        self._availiable_hosts = monitored_dict()

        self._retry_times = 5
        self._retry_interval = 5

        socketserver.StreamRequestHandler.__init__(self, *args, **kwargs)

    @property
    def controller_address(self):
        return self._controller_address

    @controller_address.setter
    def controller_address(self, v):
        if check_addr(v):
            self._controller_address = v
        else:
            raise ValueError("Invalid controller address!")

    @property
    def proxy_address(self):
        return self._proxy_address

    @proxy_address.setter
    def proxy_address(self, v):
        if check_addr(v):
            self._proxy_address = v
        else:
            raise ValueError("Invalid proxy address!")

    def unknown_device(self):
        self._logger.warning("Unknown hardware connected!")
        raise UnknowndeviceException

    def update_lists(self, pack):
        self._logger.info("Updating firewall policy...\n" + str(pack))

        try:
            accept_hosts = pack.accept_hosts

            if 'add' in accept_hosts:
                to_add = accept_hosts['add']
                add_hosts(list(to_add.values()))
                self._accept_hosts.update(to_add)
            if 'remove' in accept_hosts:
                to_remove = accept_hosts['remove']
                addrs = list(
                    self._accept_hosts[k] for k in to_remove.keys() if k in self._accept_hosts)
                remove_hosts(addrs)
                self._accept_hosts.remove(to_remove)
            if 'refresh' in accept_hosts:
                to_refresh = accept_hosts['refresh']
                flush_hosts()
                add_hosts(list(to_refresh.values()))
                self._accept_hosts.refresh(to_refresh)

            """available_hosts = pack.available_hosts

            if 'add' in available_hosts:
                to_add = available_hosts['add']
                self._availiable_hosts.update(to_add)
            if 'remove' in available_hosts:
                to_remove = available_hosts['remove']
                self._availiable_hosts.remove(to_remove)
            if 'refresh' in available_hosts:
                to_refresh = available_hosts['refresh']
                self._availiable_hosts.refresh(to_refresh)"""
        except BaseException as e:
            self._logger.warning("Iptables error: %s." % str(e))

    def connect_to_controller(self):
        self.controller_address = params.update_controller_addr()

        controller_ip = self.controller_address.split(':')[0]
        controller_port = int(self.controller_address.split(':')[1])

        s = secure_socket()

        self._logger.info("Connecting to %s..." % self.controller_address)

        for i in range(self._retry_times):
            try:
                s.connect((controller_ip, controller_port))
            except SOCKET_TIMEOUT:
                self._logger.info(
                    "Connected to controller timeout, retrying...")
            except BaseException as e:
                self._logger.warning(
                    "Network error, retry after %d seconds.(%s)" % (self._retry_interval, str(e)))
                time.sleep(self._retry_interval)
            else:
                self._logger.info("Connected to controller succeed.")
                self._accept_hosts['controller'] = self.controller_address
                return s

        self._logger.warning("Connected to controller failed.")
        s.close()

        return None

    def handle(self):
        try:
            proxy_socket = secure_socket(secure=False)
            sock_device = secure_socket(sock=self.request)

            sock_controller = None

            device_ip, device_port = sock_device.getpeername()
            device_addr = device_ip + ':' + str(device_port)
            self._logger.info("Device from %s." % device_addr)

            self_ip, self_port = sock_device.getsockname()
            self_addr = self_ip + ':' + str(self_port)

            add_device(device_addr, self_addr)

            sock_controller = self.connect_to_controller()

            if sock_controller is None:
                raise ControllerFault

            auth_obj = client_end(sock_controller, device_sock=sock_device)
            if not auth_obj.auth_to_server():
                raise UnknowndeviceException

            self._logger.info("Auth to controller passed.")

            proxy_ip = self.proxy_address.split(':')[0]
            proxy_port = int(self.proxy_address.split(':')[1])

            try:
                self._logger.info(
                    "Try to connect local service for device on %s." % self.proxy_address)
                proxy_socket.connect((proxy_ip, proxy_port))
            except:
                raise LocalServiceFault

            self._logger.info(
                "Connected to local service for device on %s." % self.proxy_address)

            while True:
                ready_for_read, _, _ = select.select(
                    [sock_controller, sock_device, proxy_socket], [], [], 5)
                # print(sock_controller)
                # print(sock_device)
                # print(proxy_socket)
                for sock in ready_for_read:
                    # self._logger.info("Data coming in on %s." % str(sock))
                    pack = sock.recv_obj()
                    if sock is sock_controller:
                        if pack is None:
                            self._logger.info("Receive heartbeat packet.")
                        elif isinstance(pack, list_update_packet):
                            self._logger.info("Receive list update packet.")
                            self.update_lists(pack)
                            proxy_socket.send_obj(pack)
                        else:
                            self._logger.warning(
                                "Receive broken packet from controller.")
                    elif sock is sock_device:
                        self._logger.info(
                            "Receive data from device, send to monitor.")
                        proxy_socket.send_obj(pack)
                    elif sock is proxy_socket:
                        self._logger.info(
                            "Receive data from monitor, send to device.")
                        sock_device.send_obj(pack)
        except ControllerFault:
            self._logger.warning(
                "No controller detected on %s." % self.controller_address)
        except UnknowndeviceException:
            self._logger.warning("Unknown device on %s." % device_addr)
        except LocalServiceFault:
            self._logger.warning("No service detected on %s." %
                                 self.proxy_address)
        except DisconnectException:
            self._logger.info("Connection closed.")
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except BaseException:
            self._logger.error("Catch unhandled exception.")
            traceback.print_exc()
        finally:
            sock_device.close()
            if sock_controller:
                sock_controller.close()
            proxy_socket.close()

            remove_device(self_addr)
            self._logger.info("Flush hosts in firewall.")
            flush_hosts()

            self._logger.info("Device offline.")
            time.sleep(10)


def main(listening_addr):
    def signal_func(sig, stack):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, signal_func)
    try:
        server_up = False

        main_logger = get_logger()
        main_logger.info("SDP proxy up.")

        if listening_addr is None or not check_addr(listening_addr):
            listening_addr = params.proxy_address_outside

        main_logger.info("Init firewall.")
        firewall_init(listening_addr)

        listening_ip = listening_addr.split(':')[0]
        listening_port = int(listening_addr.split(':')[1])
        
        server = socketserver.TCPServer(
            (listening_ip, listening_port), request_handler)
        server.socket = secure_socket(sock=server.socket, server_side=True)

        server_up = True

        main_logger.info("Listening for device at %s." % listening_addr)
        server.serve_forever()

    except KeyboardInterrupt:
        main_logger.info("Receive KeyboardInterrupt.")
    except FileNotFoundError:
        main_logger.error("Can't find cert file for TLS.")
    except BaseException:
        main_logger.error("Catch unhandled exception.")
        traceback.print_exc()
    finally:
        if server_up:
            try:
                main_logger.info("Close socket...")
                server.shutdown()
                server.server_close()
            except:
                pass
        firewall_open_all()
        main_logger.info("Client down.")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        addr = sys.argv[1]
    else:
        addr = None
    main(addr)
