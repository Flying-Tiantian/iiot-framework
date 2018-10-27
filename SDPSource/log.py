import logging
from logging import config as logging_config
import os
import socket

loglevel = os.getenv('M_SDP_LOG_LEVEL')
if loglevel is None:
    loglevel = 'DEBUG'

# 其中name为getlogger指定的名字
standard_format = '[%(asctime)s][%(levelname)s][%(threadName)s:%(thread)d][%(filename)s:%(lineno)d][%(message)s]'

simple_format = '[%(asctime)s][%(levelname)s][%(filename)s:%(lineno)d]%(message)s'

logfile_dir = os.path.dirname(os.path.abspath(__file__))
logfile_dir = os.path.join(logfile_dir, 'logs')
logfile_name = socket.gethostname() + '_SDP.log'  # log文件名

if not os.path.isdir(logfile_dir):
    os.mkdir(logfile_dir)

logfile_path = os.path.join(logfile_dir, logfile_name)

LOGGING_DIC = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': standard_format
        },
        'simple': {
            'format': simple_format
        },
    },
    'filters': {},
    'handlers': {
        # 打印到终端的日志
        'console': {
            'level': loglevel,
            'class': 'logging.StreamHandler',  # 打印到屏幕
            'formatter': 'simple'
        },
        # 打印到文件的日志,收集info及以上的日志
        'default': {
            'level': loglevel,
            'class': 'logging.handlers.RotatingFileHandler',  # 保存到文件
            'formatter': 'standard',
            'filename': logfile_path,  # 日志文件
            'maxBytes': 1024*1024*1,  # 日志大小 1M
            'backupCount': 5,
            'encoding': 'utf-8',  # 日志文件的编码，再也不用担心中文log乱码了
        },
    },
    'loggers': {
        # logging.getLogger(__name__)拿到的logger配置
        '': {
            # 这里把上面定义的两个handler都加上，即log数据既写入文件又打印到屏幕
            'handlers': ['default', 'console'],
            'level': 'DEBUG',
            'propagate': True,  # 向上（更高level的logger）传递
        },
    },
}

logging_config.dictConfig(LOGGING_DIC)


def get_logger():
    return logging.getLogger(__name__)
