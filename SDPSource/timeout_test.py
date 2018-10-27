import socket
import socketserver
import threading
import time

def time_limited(time_limit):

    '''
    一个规定函数执行时间的装饰器
    '''
    def wrapper(func):
        def _wrapper(*args, **kwargs):
            start_time = time.time()
            #通过设置守护线程强制规定函数的运行时间
            t = threading.Thread(target=func, args=args, kwargs=kwargs)
            t.setDaemon(True)
            t.start()
            time.sleep(time_limit)
            if t.is_alive():
                #若在规定的运行时间未结束守护进程，则主动抛出异常
                raise TimeoutError
        return _wrapper
    return wrapper

class void_handler(socketserver.StreamRequestHandler):
    def handle(self):
        sock = self.request

        while(True):
            time.sleep(5)

server = socketserver.TCPServer(('localhost', 2222), void_handler)

t = threading.Thread(target=server.serve_forever)
t.setDaemon(True)
t.start()

class test:
    def __init__(self):
        self.s = socket.socket()

    def timeout_f(self):
        self.s.close()  # Work on windows, but not on Linux!
        print("Socket closed.")

    @time_limited(5)  # Work on both windows and Linux!
    def run(self):
        self.s.connect(('localhost', 2222))

        timer = threading.Timer(5, self.timeout_f)
        # timer.start()

        # self.s.close()
        
        self.s.recv(10)

        timer.cancel()

o = test()
o.run()



 




