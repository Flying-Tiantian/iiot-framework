from threading import Lock

class access_list:
    def __init__(self, name, users=None):
        self._name = name
        self._users = set()
        if users:
            self._users.update(users)
        self._lock = Lock()
        self._children = dict()
        self._children_lock = Lock()

    def get_name(self):
        return self._name

    def add_users(self, users, recursive=True):
        with self._lock:
            if recursive:
                for child in self._children.values():
                    child.add_users(users)
            self._users.update(set(users))

    def del_users(self, users, recursive=True):
        with self._lock:
            if recursive:
                for child in self._children.values():
                    child.del_users(users)
            self._users.discard(set(users))

    def change_users(self, users, recursive=True):
        with self._lock:
            if recursive:
                for child in self._children.values():
                    child.change_users(users)
            self._users = set(users)

    def check_authority(self, user, mode=None):
        with self._lock:
            if user in self._users:
                return True
            else:
                return False

    def add_child(self, child_name, inherit=True):
        if isinstance(child_name, str):
            child_name = child_name.split('/')
        assert isinstance(child_name, list)

        with self._lock:
            child = self._children.get(child_name[0])
            if not child:
                child = access_list(child_name[0], users=self._users if inherit else None)
                self._children[child_name[0]] = child
            if len(child_name) == 1:
                return child
            else:
                return child.add_child(child_name[1:], inherit=inherit)

    def del_children(self, child_name):
        if isinstance(child_name, str):
            child_name = child_name.split('/')
        assert isinstance(child_name, list)

        if len(child_name) == 0 or child_name[0] == '#':
            return True

        with self._lock:
            if child_name[0] == '+':
                to_delete = []
                for name, child in self._children.items():
                    if child.del_children(child_name[1:]):
                        to_delete.append(name)
                for name in to_delete:
                    self._children.pop(name, None)
            else:
                child = self._children.get(child_name[0])
                if child:
                    if child.del_children(child_name[1:]):
                        self._children.pop(child_name[0], None)

        return False


    def get_children(self, child_name):
        if isinstance(child_name, str):
            child_name = child_name.split('/')
        assert isinstance(child_name, list)

        if len(child_name) == 0:
            return set([self])

        with self._lock:
            children = set()
            if child_name[0] == '+':
                for child in self._children.values():
                    children.update(child.get_children(child_name[1:]))
            elif child_name[0] == '#':
                children.add(self)
                for child in self._children.values():
                    children.update(child.get_children('#'))
            else:
                child = self._children.get(child_name[0])
                if child:
                    children.update(child.get_children(child_name[1:]))

        return children

    def __str__(self, level=0):
        with self._lock:
            prefix = '│  ' * level  + '├─'
            r = prefix + self._name + ': ' + str(list(self._users)) + '\n'
            for child in self._children.values():
                r += child.__str__(level=level + 1)

        return r


class authority_chain:
    _instance_lock = Lock()

    def __init__(self):
        if not hasattr(self, '_root'):
            self._root = access_list('root')
            self._lock = Lock()

    def __new__(cls, *args, **kwargs):
        if not hasattr(authority_chain, "_instance"):
            with authority_chain._instance_lock:
                if not hasattr(authority_chain, "_instance"):
                    authority_chain._instance = object.__new__(cls)
        return authority_chain._instance

    def add_topic(self, topic, inherit=True):
        with self._lock:
            if ('+' not in topic) and ('#' not in topic):
                self._root.add_child(topic, inherit=inherit)

    def del_topic(self, topic):
        with self._lock:
            self._root.del_children(topic)

    def _get_topic(self, topic, create=False):
        members = self._root.get_children(topic)

        return members

    def check_authority(self, topic, user):
        members = self._root.get_children(topic)

        if len(members) == 0:
            return False

        for member in members:
            if not member.check_authority(user):
                return False
        return True

    def add_authority(self, topic, users, recursive=True):
        with self._lock:
            members = self._get_topic(topic, create=True)
            for member in members:
                member.add_users(users, recursive=recursive)

    def del_authority(self, topic, users, recursive=True):
        with self._lock:
            members = self._get_topic(topic)
            for member in members:
                member.del_users(users, recursive=recursive)

    def __str__(self):
        return str(self._root)


if __name__ == '__main__':
    chain = authority_chain()
    chain2 = authority_chain()
    assert chain is chain2
    for i in range(4):
        name = str(i)
        for j in range(3):
            child_name = name + '/' + str(j)
            chain.add_topic(child_name)
            chain.add_authority(child_name, (name+str(j),))

    print(str(chain))

