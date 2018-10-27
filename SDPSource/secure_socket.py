import ssl
import socket
import pickle
import time
from params import params
from log import get_logger


CERT_FILE = '/home/SDPSource/openssl/cert.crt'
KEY_FILE = '/home/SDPSource//openssl/rsa_private.key'


LATENCY = 0

class DisconnectException(Exception):
    pass


def valid_ip(address):
    try:
        socket.inet_aton(address)
    except:
        return False
    else:
        return True


class secure_socket():
    def __init__(self, sock=None, secure=True, server_side=False, do_handshake_on_connect=True):
        self._logger = get_logger()
        self._secure = secure
        if sock is None:
            sock = socket.socket()

        if not server_side:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if secure:
            if isinstance(sock, ssl.SSLSocket):
                self._sock = sock
            else:
                context = ssl.SSLContext()
                if server_side:
                    context.load_cert_chain(CERT_FILE, KEY_FILE)
                self._sock = context.wrap_socket(
                    sock, server_side=server_side, do_handshake_on_connect=do_handshake_on_connect)
        else:
            self._sock = sock

    def connect(self, *args, timeout=None):
        self.settimeout(timeout)
        self._sock.connect(*args)
        self.settimeout(None)


    def _send_obj(self, obj):
        try:
            data = pickle.dumps(obj)
            length = len(data)
            length_code = pickle.dumps(length)
            # print(length_code + data)
            self.sendall(length_code + data)
        except:
            raise DisconnectException

    def send_obj(self, obj):
        self._send_obj(obj)

        if params.test_mode:
            send_time = time.time()
            r = self._recv_obj()
            ack_time = time.time()
            if r == 'ACK':
                if params.test_mode:
                    global LATENCY
                    l = (ack_time-send_time) * 500
                    LATENCY = (LATENCY * 0.8) + (l * 0.2)
                    self._logger.critical('[latency]%fms' % (LATENCY))


    def _recv_length(self, length):
        buffer = b''
        while True:
            try:
                data = self.recv(length-len(buffer))
            except:
                data=None
            if not data:
                raise DisconnectException
            buffer += data
            if len(buffer) >= length:
                return buffer

    def _recv_a_pickle(self, buffersize=1):
        data = b''
        while True:
            try:
                new_data = self.recv(buffersize)
            except:
                new_data = None
            if not new_data:
                raise DisconnectException
            data += new_data
            # print(data)
            try:
                obj = pickle.loads(data)
            except:
                pass  # Need more data to decode into an object.
            else:
                return obj

    def _recv_obj(self):
        length = self._recv_a_pickle(1)
        if not isinstance(length, int):
            length = self._recv_a_pickle(1)
            if not isinstance(length, int):
                return None
        try:
            r = pickle.loads(self._recv_length(length))
        except:
            return None
        else:
            return r

    def recv_obj(self):
        r = self._recv_obj()
        if params.test_mode:
            self._send_obj('ACK')

        return r


    def close(self):
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
            self._sock.close()
        except:
            pass

    def __getattr__(self, attr):
        return getattr(self._sock, attr)


if __name__ == '__main__':
    s = secure_socket()
    pass
