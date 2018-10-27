class list_update_packet:
    def __init__(self, accept_hosts=None, available_hosts=None):
        """
        
        Args:
            accept_hosts (dict): May have three keys: 'add' 'remove' 'refresh', value should be a dict of {ID: address}.
            available_hosts (dict): Same as above.
        """

        self.accept_hosts = accept_hosts
        self.available_hosts = available_hosts

    def __str__(self):
        s = '\n=====LIST UPDATE PACKET=====\n'
        s += 'ACCEPT HOSTS:\n'
        for k, c in self.accept_hosts.items():
            s += '--' + str(k) + ':\n'
            for k, v in c.items():
                s += '----' + str(k) + ': ' + str(v) + '\n'
        s += 'AVAILIABLE HOSTS:\n'
        for k, c in self.available_hosts.items():
            s += '--' + str(k) + ':\n'
            for k, v in c.items():
                s += '----' + str(k) + ': ' + str(v) + '\n'
        s += '============================\n'

        return s

class data_packet:
    def __init__(self, data):
        self.data = data

    def __str__(self):
        s = '\n============DATA============\n'
        s += str(self.data) + '\n'
        s += '============================\n'

        return s

class key_update_packet:
    def __init__(self, old, new):
        self.old_key = old
        self.new_key = new

    def __str__(self):
        s = '\n=========KEY-UPDATE=========\n'
        s += 'old key: ' + self.old_key + '\n'
        s += 'new key: ' + self.new_key + '\n'
        s += '============================\n'

        return s

class mqtt_info_packet:
    def __init__(self, deviceID, username, password):
        self.deviceID = deviceID
        self.username = username
        self.password = password

    def __str__(self):
        s = '\n=========MQTT-INFO=========\n'
        s += 'deviceID: ' + self.deviceID + '\n'
        s += 'username: ' + self.username + '\n'
        s += 'password: ' + self.password + '\n'
        s += '===========================\n'

        return s
