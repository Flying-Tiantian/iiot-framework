#!/bin/sh

SHELL_FOLDER=$(dirname $0)

# $SHELL_FOLDER/openssl/gen.sh

$SHELL_FOLDER/mqtt_broker.py &
$SHELL_FOLDER/sdp_controller.py