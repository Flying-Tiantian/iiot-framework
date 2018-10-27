import iptc
import socket
import threading
import traceback
from log import get_logger


FAKE_TEST = False
FILTER_PORT = False


LOGGER = get_logger()

L = threading.Lock()

FILTER_TABLE = iptc.Table(iptc.Table.FILTER)
FILTER_TABLE.autocommit = True
FILTER_INPUT_CHAIN = iptc.Chain(FILTER_TABLE, 'INPUT')
FILTER_FORWARD_CHAIN = iptc.Chain(FILTER_TABLE, 'FORWARD')


def rule2str(rule):
    r = 'src: %s, dst: %s' % (rule.src, rule.dst)

    return r


def chain2str(chain=FILTER_INPUT_CHAIN):
    r = '==========Chain %s==========\n' % chain.name
    for rule in chain.rules:
        r += rule2str(rule) + '\n'
    r += '===============================\n'

    return r


def exception_catcher(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except BaseException as e:
            LOGGER.warning("Iptables error: %s." % str(e))
            traceback.print_exc()
    return wrapper


def _accept_loop():
    LOGGER.info("Accept loop packet.")
    rule = iptc.Rule()
    rule.in_interface = 'lo'
    rule.create_target(iptc.Policy.ACCEPT)
    with L:
        FILTER_INPUT_CHAIN.insert_rule(rule, position=0)

    if not FILTER_TABLE.autocommit:
        FILTER_TABLE.commit()


def _accept_positive():
    LOGGER.info("Accept out connection.")
    rule = iptc.Rule()
    rule.in_interface = 'eth0'
    m = rule.create_match('state')
    m.state = "ESTABLISHED,RELATED"
    rule.create_target(iptc.Policy.ACCEPT)
    with L:
        FILTER_INPUT_CHAIN.insert_rule(rule, position=1)

    if not FILTER_TABLE.autocommit:
        FILTER_TABLE.commit()


def _get_rule(src_addr, dst_addr, filter_port=False, protocol='tcp'):
    rule = iptc.Rule()
    rule.in_interface = 'eth0'
    rule.protocol = protocol
    if src_addr:
        rule.src = src_addr.split(':')[0]
    if dst_addr:
        rule.dst = dst_addr.split(':')[0]
    if filter_port:
        m = rule.create_match('tcp')
        if src_addr:
            src_port = src_addr.split(':')[1]
            m.sport = src_port
        if dst_addr:
            dst_port = dst_addr.split(':')[1]
            m.dport = dst_port
    rule.create_target(iptc.Policy.ACCEPT)

    return rule


def _insert_rule(src_addr, dst_addr, filter_port=False, position=0):
    rule = _get_rule(src_addr, dst_addr, filter_port=filter_port)
    with L:
        LOGGER.info('[firewall] Insert rule %s to position %d \n%s' % (rule2str(rule), position, chain2str()))
        FILTER_INPUT_CHAIN.insert_rule(rule, position=position)

    if not FILTER_TABLE.autocommit:
        FILTER_TABLE.commit()


def _add_rule(src_addr, dst_addr, filter_port=False, protocol='tcp'):
    rule = _get_rule(src_addr, dst_addr, filter_port=filter_port, protocol=protocol)
    with L:
        LOGGER.info('[firewall] Append rule %s\n%s' % (rule2str(rule), chain2str()))
        FILTER_INPUT_CHAIN.append_rule(rule)

    if not FILTER_TABLE.autocommit:
        FILTER_TABLE.commit()


def _remove_rule(src_addr, dst_addr, filter_port=False, protocol='tcp'):
    rule = _get_rule(src_addr, dst_addr, filter_port=filter_port, protocol=protocol)
    with L:
        LOGGER.info('[firewall] Delete rule %s\n%s' % (rule2str(rule), chain2str()))
        FILTER_INPUT_CHAIN.delete_rule(rule)

    if not FILTER_TABLE.autocommit:
        FILTER_TABLE.commit()


def _replace_rule(src_addr, dst_addr, filter_port=False, position=-1):
    rule = _get_rule(src_addr, dst_addr, filter_port=filter_port)
    with L:
        LOGGER.info('[firewall] Replace rule %s to position %d\n%s' % (rule2str(rule), position, chain2str()))
        FILTER_INPUT_CHAIN.replace_rule(rule, position=position)

    if not FILTER_TABLE.autocommit:
        FILTER_TABLE.commit()


def _add_controller(controller_addr):
    return
    _insert_rule(controller_addr, None, filter_port=True, position=1)


def _add_listening(listening_addr):
    _insert_rule(None, listening_addr, filter_port=True, position=2)


@exception_catcher
def add_device(device_addr, listening_addr):
    _replace_rule(device_addr, listening_addr, filter_port=True, position=2)


@exception_catcher
def remove_device(listening_addr):
    _replace_rule(None, listening_addr, filter_port=True, position=2)


@exception_catcher
def add_hosts(host_addr):
    if isinstance(host_addr, list):
        for host in host_addr:
            _add_rule(host, None)
    else:
        _add_rule(host_addr, None)


@exception_catcher
def remove_hosts(host_addr):
    if isinstance(host_addr, list):
        for host in host_addr:
            _remove_rule(host, None)
    else:
        _remove_rule(host_addr, None)


@exception_catcher
def flush_hosts():
    with L:
        while len(FILTER_INPUT_CHAIN.rules) > 3:
            to_delete = FILTER_INPUT_CHAIN.rules[-1]
            LOGGER.info('[firewall] Delete rule %s' % rule2str(to_delete))
            FILTER_INPUT_CHAIN.delete_rule(to_delete)
            LOGGER.info('[firewall]\n%s' % chain2str())

        if not FILTER_TABLE.autocommit:
            FILTER_TABLE.commit()


@exception_catcher
def firewall_init(listening_addr):
    with L:
        LOGGER.info("Closing all ports...")
        FILTER_INPUT_CHAIN.flush()
        FILTER_INPUT_CHAIN.set_policy(iptc.Policy.DROP)
        FILTER_FORWARD_CHAIN.flush()
        FILTER_FORWARD_CHAIN.set_policy(iptc.Policy.DROP)
        filter_output_chain = iptc.Chain(FILTER_TABLE, 'OUTPUT')
        filter_output_chain.flush()
        filter_output_chain.set_policy(iptc.Policy.ACCEPT)

    _accept_loop()
    _accept_positive()
    if listening_addr:
        _add_listening(listening_addr)

    if not FILTER_TABLE.autocommit:
        FILTER_TABLE.commit()


@exception_catcher
def firewall_open_all():
    with L:
        FILTER_INPUT_CHAIN.flush()
        FILTER_INPUT_CHAIN.set_policy(iptc.Policy.ACCEPT)
        FILTER_FORWARD_CHAIN.flush()
        FILTER_FORWARD_CHAIN.set_policy(iptc.Policy.ACCEPT)
        filter_output_chain = iptc.Chain(FILTER_TABLE, 'OUTPUT')
        filter_output_chain.flush()
        filter_output_chain.set_policy(iptc.Policy.ACCEPT)

    if not FILTER_TABLE.autocommit:
        FILTER_TABLE.commit()

if __name__ == '__main__':
    firewall_init('127.0.0.1:2222')
    add_hosts(['192.168.1.1:1', '192.168.1.2:2'])
    flush_hosts()
    firewall_open_all()
