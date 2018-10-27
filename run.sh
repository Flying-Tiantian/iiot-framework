#!/bin/sh

SHELL_FOLDER=$(dirname $0)

echo PWD=$SHELL_FOLDER

kubectl delete -f controller-svc.yaml
kubectl delete -f broker-svc.yaml
kubectl delete -f monitor-svc.yaml

kubectl create -f controller-svc.yaml
kubectl create -f broker-svc.yaml
kubectl create -f monitor-svc.yaml

docker load -i $SHELL_FOLDER/images/sdp-platform.tar
$SHELL_FOLDER/build_controller.sh
$SHELL_FOLDER/build_monitor.sh
$SHELL_FOLDER/build_device.sh