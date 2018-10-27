#!/bin/sh

kubectl delete -f device-rc.yaml
docker image rm -f sdp-device
docker build --no-cache -t sdp-device -f Dockerfile_device .
kubectl create -f device-rc.yaml