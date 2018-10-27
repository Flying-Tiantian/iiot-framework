#!/bin/sh

kubectl delete -f monitor-rc.yaml
docker image rm -f sdp-monitor
docker build --no-cache -t sdp-monitor -f Dockerfile_monitor .
kubectl create -f monitor-rc.yaml