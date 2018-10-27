import socket
import os
import threading
from log import get_logger

LOGGER = get_logger()

def valid_ip(address):
    try:
        socket.inet_aton(address)
    except:
        return False
    else:
        return True

def get_addr(env_name, default_ip, default_port):
    addr = os.getenv(env_name)
    if not addr:
        port = str(default_port)
        ip = default_ip
    else:
        if ':' in addr:
            ip = addr.split(':')[0]
            port = addr.split(':')[1]
        else:
            ip = addr
            port = str(default_port)
    if not valid_ip(ip):
        try:
            ip = socket.gethostbyname(ip)
        except BaseException as e:
            LOGGER.error("Can't resolve hostname %s.(%s)" % (ip, str(e)))
            ip = socket.gethostbyname('localhost')

    return ip + ':' + port

class params_class:
    _instance_lock = threading.Lock()

    def __init__(self):
        if not hasattr(self, 'device_ID'):
            self.device_ID = socket.gethostname()

            self.broker_port = os.getenv('M_MQTT_BROKER_PORT')
            if self.broker_port is None:
                self.broker_port = 5555

            self.broker_address = get_addr('M_MQTT_BROKER_ADDRESS', 'mqtt-broker', self.broker_port)

            # controller listening port
            self.controller_port = os.getenv('M_SDP_CONTROLLER_PORT')
            if self.controller_port is None:
                self.controller_port = 2222

            # controller address
            self.controller_address = get_addr('M_SDP_CONTROLLER_ADDRESS', 'sdp-controller', self.controller_port)

            # device monitor should listen to this address for device connection
            self.proxy_port_inside = os.getenv('M_SDP_PROXY_PORT_INSIDE')
            if self.proxy_port_inside is None:
                self.proxy_port_inside = 3333
            self.proxy_address_inside = socket.gethostbyname('localhost') + ':' + str(self.proxy_port_inside)

            # sdp proxy listen to this address for device connection
            self.proxy_port_outside = os.getenv('M_SDP_PROXY_PORT_OUTSIDE')
            if self.proxy_port_outside is None:
                self.proxy_port_outside = 4444
            self.proxy_address_outside = socket.gethostbyname(socket.gethostname()) + ':' + str(self.proxy_port_outside)

            # where sdp proxy provide service to device
            self.monitor_address = get_addr('M_SDP_MONITOR_ADDRESS', 'sdp-monitor', self.proxy_port_outside)

            # device monitor should listen to this address for other monitor connection
            self.peer_port = os.getenv('M_SDP_PEER_PORT')
            if self.peer_port is None:
                self.peer_port = 6666
            self.peer_address = socket.gethostbyname(socket.gethostname()) + ':' + str(self.peer_port)

            is_test = os.getenv('M_SDP_TEST')
            if is_test is None:
                self.test_mode = False
            else:
                self.test_mode = is_test == 'True'

            self.test_group_num = 1

    def update_controller_addr(self):
        self.controller_address = get_addr('M_SDP_CONTROLLER_ADDRESS', 'sdp-controller', self.controller_port)
        return self.controller_address

    def update_monitor_addr(self):
        self.monitor_address = get_addr('M_SDP_MONITOR_ADDRESS', 'sdp-monitor', self.proxy_port_outside)
        return self.monitor_address

    def __new__(cls, *args, **kwargs):
        if not hasattr(params_class, "_instance"):
            with params_class._instance_lock:
                if not hasattr(params_class, "_instance"):
                    params_class._instance = object.__new__(cls)
        return params_class._instance

params = params_class()