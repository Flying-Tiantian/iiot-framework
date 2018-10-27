import threading
import copy
import random
from log import get_logger
from params import params

SEED = '1234567890qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM'

class signal:
    def __init__(self):
        self._v_lock = threading.Lock()
        self._value = None
        self._events = {}

    def get(self, timeout=None):
        with self._v_lock:
            caller = threading.current_thread()
            if not caller in self._events:
                self._events[caller] = threading.Event()

        if self._events[caller].wait(timeout):
            self._events[caller].clear()
            with self._v_lock:
                return copy.copy(self._value)
        else:
            return None

    def set(self, value):
        with self._v_lock:
            self._value = value

        died = []
        for t, e in self._events.items():
            if t.is_alive():
                e.set()
            else:
                died.append(t)
        for t in died:
            self._events.pop(t, None)


class monitored_dict(dict):
    def __init__(self):
        dict.__init__(self)
        self.lock = threading.Lock()
        self._logger = get_logger()
        self._dirt_sig = signal()

    def get_all(self):
        if len(self) > 0:
            return set(self.values())
        else:
            return set()

    def set_dirt(self):
        self._dirt_sig.set(self.get_all())

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self.set_dirt()

    def pop(self, key, default=None):
        r = dict.pop(self, key, default)
        if r:
            self.set_dirt()
        else:
            self._logger.warning("Try to pop element which is not exist.")
        return r

    def change_signal(self):
        return self._dirt_sig

    def diff(self, d):
        if not isinstance(d, dict):
            raise ValueError("Need a dict!")
        r = monitored_dict()
        keys = set(self.keys()) - set(d.keys())
        for k in keys:
            r[k] = self[k]

        return r

    def update(self, d):
        dict.update(self, d)
        self.set_dirt()

    def remove(self, d):
        if not isinstance(d, dict):
            raise ValueError("Need a dict!")
        for k in d:
            dict.pop(self, k, None)

        self.set_dirt()

    def refresh(self, d):
        dict.clear(self)
        self.update(d)


class group:
    def __init__(self, name):
        self._name = name
        self._l = threading.Lock()
        self._member_set = set()
        self._online_dict = monitored_dict()
        self._offline_dict = {}
        self._logger = get_logger()

    def get_access_hosts(self, ID):
        """Overwrite this function to change access policy.

        Args:
            ID (str): ID of member who initiate this query.

        Returns:
            monitored_dict: Which contains all members can access by the initiator。
        """

        return self.get_online_members(), self._online_dict.change_signal()

    def get_name(self):
        return self._name

    def get_offline_members(self):
        with self._l:
            return self._offline_dict

    def get_online_members(self):
        with self._l:
            return self._online_dict.get_all()

    def add_member(self, m):
        if not isinstance(m, member):
            self._logger.warning(
                "Invalid input, must be instance of class 'member'.")
            return None

        with self._l:
            if m in self._member_set:
                return m
            self._member_set.add(m)
            m.add_group(self)
            if m.ifonline():
                self._online_dict[m.get_id()] = m
            else:
                self._offline_dict[m.get_id()] = m
            self._logger.info("Added member %s to group %s." %
                              (m.get_id(), self._name))

        return m

    def remove_member(self, m):
        if not isinstance(m, member):
            self._logger.warning(
                "Invalid input, must be instance of class 'member'.")
            return None
        with self._l:
            if not m in self._member_set:
                return m
            self._member_set.discard(m)
            m.remove_group(self)
            self._online_dict.pop(m.get_id(), None)
            self._offline_dict.pop(m.get_id(), None)
            self._logger.info("Removed member %s from group %s." %
                              (m.get_id(), self._name))

        return m

    def online(self, ID):
        with self._l:
            if ID in self._offline_dict:
                member = self._offline_dict.pop(ID, None)
                self._online_dict[ID] = member
                self._logger.info(
                    "Member %s is online in group %s." % (ID, self._name))
            elif ID in self._online_dict:
                self._logger.info(
                    "Member %s changed address in group %s." % (ID, self._name))
            else:
                self._logger.warning(
                    "Try to online member %s not owned by group %s." % (ID, self._name))

    def offline(self, ID):
        with self._l:
            if ID in self._online_dict:
                member = self._online_dict.pop(ID, None)
                self._offline_dict[ID] = member
            elif ID in self._offline_dict:
                self._logger.warning(
                    "Try to offline an offlined device %s in group %s" % (ID, self._name))
            else:
                self._logger.warning(
                    "Try to offline a member not owned by group %s.", self._name)

    def delete(self):
        for m in self._member_set:
            self.remove_member(m)

    def print(self, level=1):
        with self._l:
            online = self._online_dict.get_all()
            offline = self._offline_dict
        r = 'group %s' % self._name
        r += '--online (%d)\n' % len(online)
        if level > 1:
            for m in online:
                r += m.print() + '\n'
        r += '--offline (%d)\n' % len(offline)
        if level > 1:
            for m in offline:
                r += m.print() + '\n'

        return r


class member:
    def __init__(self, ID, key=None, address=None, online=False):
        self._ID = ID
        self._key = []
        if key is None:
            self._key.append(ID)
        else:
            self._key.append(key)
        self._address = address
        self._online = online
        self._state_lock = threading.Lock()
        self._group_lock = threading.Lock()
        self._key_lock = threading.Lock()
        self._groups = set()
        self._logger = get_logger()
        self._access_sets_lock = threading.Lock()
        # group as key and access set as value, only modified in self.monitor_func()
        self._access_sets = {}
        self._access_host_change_sig = signal()

        self._monitor_threads = {}

    def _rand_string(self, len):
        s = ''
        for _ in range(len):
            s += random.choice(SEED)

        return s

    def auth(self, key):
        if params.test_mode:
            if key == self._ID:
                return key
            else:
                return False

        with self._key_lock:
            for i in range(len(self._key)):
                if self._key[i] == key:
                    self._key = self._key[i:i+1]
                    new_key = self._rand_string(8)
                    self._key.append(new_key)

                    return new_key
            
            return False

    def merge_sets(self):
        """Merge access set of all group containing this member and set 

        Returns:
            set: The access set.
        """

        with self._access_sets_lock:
            merged = set()
            for d in self._access_sets.values():
                merged |= d
        self._access_host_change_sig.set(merged)

        return merged

    def monitor_func(self, group):
        self._logger.info("Monitor thread in member %s for group %s start." % (
            self._ID, group.get_name()))
        self._access_sets[group], change_signal = group.get_access_hosts(
            self._ID)

        self.merge_sets()

        while True:
            new_online_members = change_signal.get()
            self._logger.info("Group %s has %d online members." % (
                group.get_name(), int(len(new_online_members))))
            with self._group_lock:
                if not group in self._groups:
                    break
            with self._access_sets_lock:
                self._access_sets[group] = new_online_members
            self.merge_sets()

        with self._access_sets_lock:
            self._access_sets.pop(group, None)
        self._logger.info("Monitor thread in member %s for group %s stop." % (
            self._ID, group.get_name()))

    def get_id(self):
        return self._ID

    def get_access_hosts(self):
        return self.merge_sets(), self._access_host_change_sig

    def add_group(self, g):
        with self._group_lock:
            if g in self._groups:
                return
            self._groups.add(g)
        self._logger.info("Add group %s to member %s." %
                          (g.get_name(), self._ID))
        monitor_thread = threading.Thread(target=self.monitor_func, args=[g])
        monitor_thread.setDaemon(True)
        self._monitor_threads[g] = monitor_thread
        monitor_thread.start()

    def join_group(self, g):
        g.add_member(self)

    def remove_group(self, g):
        with self._group_lock:
            self._groups.discard(g)
        self._logger.info("Remove group %s from member %s." %
                          (g.get_name(), self._ID))

    def quit_group(self, g):
        g.remove_member(self)

    def ifonline(self):
        with self._state_lock:
            return self._online

    def get_address(self):
        return self._address

    def online(self, address):
        with self._state_lock:
            if self._online:
                self._logger.warning(
                    "Device id %s has multy instance!" % self._ID)
                return False
            self._address = address
            self._online = True
            self._logger.info("Member %s is online." % self._ID)
            with self._group_lock:
                for group in self._groups:
                    group.online(self._ID)
            return True

    def offline(self):
        with self._state_lock:
            self._address = None
            self._online = False
            self._logger.info("Member %s is offline." % self._ID)
            with self._group_lock:
                for group in self._groups:
                    group.offline(self._ID)

    def delete(self):
        with self._group_lock:
            with self._state_lock:
                self._groups.clear()
                self._access_host_change_sig.set('deleted')

    def print(self):
        r = 'ID: %s' % self._ID
        if self.ifonline():
            r += ', ADDR: %s' % self._address
        return r


class access_table:
    _instance_lock = threading.Lock()

    def __init__(self):
        if not hasattr(self, '_member_lock'):
            self._member_lock = threading.Lock()
            self._group_lock = threading.Lock()
            self._members = {}
            self._groups = {}
            self._logger = get_logger()
            # self.add_group('default')

    def __new__(cls, *args, **kwargs):
        if not hasattr(access_table, "_instance"):
            with access_table._instance_lock:
                if not hasattr(access_table, "_instance"):
                    access_table._instance = object.__new__(cls)
        return access_table._instance

    def get_access_hosts(self, ID):
        if ID in self._members:
            return self._members[ID].get_access_hosts()
        else:
            self._logger.warning("Try to query an ID which is not exist.")
            return None

    def get_member(self, ID):
        with self._member_lock:
            if ID in self._members:
                return self._members[ID]
            else:
                self._logger.warning(
                    "Try to query ID %s which is not exist." % ID)
                return None

    def add_member(self, ID=None, m=None):
        with self._member_lock:
            if ID in self._members:
                return
            if m is None:
                if ID is None:
                    return
                else:
                    m = member(ID)
            self._members[ID] = m
            self._logger.info("Add member %s" % m.get_id())

    def del_member(self, ID):
        with self._member_lock:
            m = self._members.pop(ID, None)
            m.delete()
            self._logger.info("Delete member %s" % ID)

    def get_group(self, name):
        with self._group_lock:
            return self._groups[name]

    def add_group(self, name=None, g=None):
        with self._group_lock:
            if name in self._groups:
                return
            if g is None:
                if name is None:
                    return
                else:
                    g = group(name)
            self._groups[name] = g
            self._logger.info("Add group %s" % g.get_name())

    def del_group(self, name):
        with self._group_lock:
            g = self._groups.pop(name, None)
            g.delete()
            self._logger.info("Delete group %s" % name)

    def add_relation(self, ID, name):
        if name in self._groups and ID in self._members:
            self._groups[name].add_member(self._members[ID])
            self._logger.info(
                "[access_table]Add member %s to group %s" % (ID, name))

    def remove_relation(self, ID, name):
        if name in self._groups and ID in self._members:
            self._groups[name].remove_member(self._members[ID])
            self._logger.info(
                "[access_table]Remove member %s from group %s" % (ID, name))

    def print(self, level=1):
        r = '\n==========ACCESS TABLE==========\n'
        with self._group_lock:
            for g in self._groups.values():
                r += g.print(level)

        return r + '================================\n'

