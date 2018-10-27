#!/bin/sh

SHELL_FOLDER=$(dirname $0)

$SHELL_FOLDER/openssl/gen.sh
# cp $SHELL_FOLDER/sdp_proxy_service /etc/init.d/
# rc-update add sdp_proxy_service
# rc-service sdp_proxy_service start

$SHELL_FOLDER/device_monitor.py &
# iptables -L
$SHELL_FOLDER/sdp_proxy.py