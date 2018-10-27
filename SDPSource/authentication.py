import socket
import threading
import time
import os
import pickle
import traceback
import shutil
from log import get_logger
from access_policy import access_table
from params import params

TIMEOUT = 10


class ReturnThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        threading.Thread.__init__(self, *args, **kwargs)
        self._return = None

    def run(self):
        if self._target is not None:
            self._return = self._target(*self._args, **self._kwargs)

    def join(self, timeout=None):
        threading.Thread.join(self, timeout)
        return self._return


def time_limited(time_limit):
    '''
    一个规定函数执行时间的装饰器
    '''
    def wrapper(func):
        def _wrapper(*args, **kwargs):
            # 通过设置守护线程强制规定函数的运行时间
            t = ReturnThread(target=func, args=args, kwargs=kwargs)
            t.setDaemon(True)
            t.start()
            r = t.join(time_limit)
            if t.is_alive():
                # 若在规定的运行时间未结束守护进程，则主动抛出异常
                raise TimeoutError
            else:
                return r
        return _wrapper
    return wrapper


class auth_packet:
    def __init__(self, deviceID, userID, key):
        self.deviceID = deviceID
        self.userID = userID
        self.key = key


class reply_packet:
    def __init__(self, passed, new_key=None):
        self.passed = passed
        self.new_key = new_key


class client_end:
    def __init__(self, server_sock, device_sock=None, pack=None, timeout=10):
        self._logger = get_logger()
        self._server_sock = server_sock
        self._device_sock = device_sock
        self._auth_info = pack
        self._timeout = timeout
        self._key_path = os.path.join('.', 'keyfile')
        self._backup_key_path = self._key_path + '.backup'
        global TIMEOUT
        TIMEOUT = timeout

    

    @property
    def key(self):
        try:
            with open(self._key_path, 'rb') as f:
                return pickle.load(f)
        except:
            try:
                shutil.copy(self._backup_key_path, self._key_path)
                with open(self._key_path, 'rb') as f:
                    return pickle.load(f)
            except:
                k = socket.gethostname()
                with open(self._key_path, 'wb' if os.path.exists(self._key_path) else 'xb') as f:
                    pickle.dump(k, f)
                with open(self._backup_key_path, 'wb' if os.path.exists(self._backup_key_path) else 'xb') as f:
                    pickle.dump(k, f)
                return k


    @key.setter
    def key(self, v):
        with open(self._backup_key_path, 'wb' if os.path.exists(self._backup_key_path) else 'xb') as f:
            pickle.dump(v, f)
        shutil.copy(self._backup_key_path, self._key_path)

    def get_auto_info(self):
        device_id = socket.gethostname()
        pack = auth_packet(device_id, None, self.key)
        return pack

    @time_limited(TIMEOUT)
    def auth_to_server(self):
        try:
            while True:
                if self._auth_info:  # not used
                    auth_info = self._auth_info
                elif self._device_sock:  # which means this is a proxy
                    auth_info = self._device_sock.recv_obj()
                else:  # which means this is the device
                    auth_info = self.get_auto_info()
                self._logger.info("Send auth packet...[ID: %s, KEY: %s]" % (auth_info.deviceID, auth_info.key))
                self._server_sock.send_obj(auth_info)
                reply_data = self._server_sock.recv_obj()
                if not isinstance(reply_data, reply_packet) or reply_data.passed == 'retry':
                    if self._device_sock:
                        self._device_sock.send_obj(reply_packet('retry'))
                else:
                    if self._device_sock:
                        self._device_sock.send_obj(reply_data)
                    else:
                        self.key = reply_data.new_key
                    return reply_data.passed
        except:
            traceback.print_exc()
            return False


class server_end:
    def __init__(self, sock, max_try_times=5, timeout=10):
        self._logger = get_logger()
        self._a_table = access_table()
        self._sock = sock
        self._timeout = timeout
        self._max_try_times = max_try_times
        global TIMEOUT
        TIMEOUT = timeout

    @time_limited(TIMEOUT)
    def authenticate(self):
        try:
            for _ in range(self._max_try_times):
                auth_info = self._sock.recv_obj()
                if isinstance(auth_info, auth_packet):
                    self._logger.info(
                        "Recive auth packet from device %s" % auth_info.deviceID)

                    m = self._a_table.get_member(auth_info.deviceID)
                    
                    if m:
                        new_key = m.auth(auth_info.key)
                        if new_key:
                            self._sock.send_obj(reply_packet(True, new_key=new_key))
                            return True, auth_info.deviceID
                    elif params.test_mode:
                        self._a_table.add_member(auth_info.deviceID)
                        self._a_table.add_relation(auth_info.deviceID, str(hash(auth_info.deviceID) % params.test_group_num))
                        self._sock.send_obj(reply_packet(True, auth_info.deviceID))
                        return True, auth_info.deviceID

                    self._sock.send_obj(reply_packet(False))
                    return False, None
                else:
                    self._sock.send_obj(reply_packet('retry'))
        except:
            return False, None
