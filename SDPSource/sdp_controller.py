#!/usr/bin/python3

import sys
import time
import threading
import traceback
import socket
from params import params
from secure_socket import secure_socket, DisconnectException
from protocol import list_update_packet
from socketserver import ThreadingTCPServer, StreamRequestHandler
from authentication import auth_packet, reply_packet, server_end
from access_policy import access_table
from log import get_logger

LOGGER = get_logger()

HEART_BEAT_INTERVAL = 10
AUTH_TIMEOUT = 30

class UnknowndeviceException(Exception):pass

class request_handler(StreamRequestHandler):
    def extract_info(self, excep, members_set):
        info = {}
        for m in members_set:
            if m != excep:
                info[m.get_id()] = m.get_address()

        return info

    def handle(self):
        try:
            ID = None
            m = None

            # this is already a sslsocket
            sock = secure_socket(sock=self.request)
            # get client addr
            ip, port = sock.getpeername()
            addr = ip + ':' + str(port)

            ip, port = sock.getsockname()
            server_addr = ip + ':' + str(port)

            LOGGER.info("Request from %s." % addr)

            # authentication
            auth_obj = server_end(sock, timeout=AUTH_TIMEOUT)
            passed, ID = auth_obj.authenticate()

            if not passed:
                LOGGER.warning("Auth failed!")
                raise UnknowndeviceException

            LOGGER.info("Auth passed %s, %s." % (ID, addr))

            a_table = access_table()
            m = a_table.get_member(ID)
            if not m.online(addr):
                LOGGER.warning("Mimicry attack of device %s on %s." % (ID, addr))
                m = None
                return

            # athorization done, update list
            access_members, sig = m.get_access_hosts()

            accept_hosts = {}
            to_add = self.extract_info(m, access_members)
            if to_add:
                accept_hosts['add'] = to_add

                
            pack = list_update_packet(accept_hosts, accept_hosts)
            
            LOGGER.info("List init packet to %s:\n%s" % (ID, str(pack)))
            
            sock.send_obj(pack)

            while True:
                new_members = sig.get(HEART_BEAT_INTERVAL)
                if new_members is None:
                    # send test packet to manually test connection
                    LOGGER.info("Heartbeat packet to %s." % ID)
                    sock.send_obj(None)
                elif new_members == 'deleted':
                    break
                else:
                    to_add = new_members - access_members
                    to_remove = access_members - new_members
                    access_members = new_members

                    to_add = self.extract_info(m, to_add)
                    to_remove = self.extract_info(m, to_remove)

                    accept_hosts = {}
                    if to_add:
                        accept_hosts['add'] = to_add
                    if to_remove:
                        accept_hosts['remove'] = to_remove

                    pack.accept_hosts = accept_hosts
                    pack.available_hosts = accept_hosts

                    LOGGER.info("List update packet to %s:\n%s" % (ID, str(pack)))

                    sock.send_obj(pack)

        except UnknowndeviceException:
            LOGGER.warning("Unknown device on %s." % addr)
        except DisconnectException:
            if ID is None:
                ID = 'unknown'
            LOGGER.info("Member %s connection interrupted." % ID)
        except BaseException:
            LOGGER.error("Catch unhandled exception.")
            traceback.print_exc()
        finally:
            if m:
                LOGGER.info("Member %s is offline." % ID)
                m.offline()
            try:
                sock.close()
            except:
                pass


def main(address=None):
    try:
        LOGGER.info("Server up.")
        if address is None:
            ip = socket.gethostbyname(socket.gethostname())
            port = params.controller_port

            address = ip + ':' + str(port)

        LOGGER.info("Server listening address %s." % address)

        ip = address.split(':')[0]
        port = int(address.split(':')[1])

        server = ThreadingTCPServer((ip, port), request_handler)
        server.socket = secure_socket(sock=server.socket, server_side=True)
        server.daemon_threads = True

        LOGGER.info("Creating work thread...")
        serv_thread = threading.Thread(target=server.serve_forever)
        serv_thread.setDaemon(True)
        serv_thread.start()
        LOGGER.info("server is running at %s." % address)

        a_table = access_table()
        while True:
            time.sleep(5)
            # LOGGER.critical(a_table.print())
    except KeyboardInterrupt:
        LOGGER.info("Receive keyboard interrupt, shut down...")
    except BaseException:
        LOGGER.error("Catch unhandled exception.")
        traceback.print_exc()
    finally:
        try:
            LOGGER.info("Exit handle loop...")
            server.shutdown()
            LOGGER.info("Close socket...")
            server.server_close()
        except:
            pass
        try:
            LOGGER.info("Wait all request handler threads...")
            serv_thread.join()
        except:
            pass
        LOGGER.info("Server down.")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        addr = sys.argv[1]
    else:
        addr = None

    if params.test_mode:
        a_table = access_table()
        for i in range(params.test_group_num):
            a_table.add_group(name=str(i))
    
    main(addr)
