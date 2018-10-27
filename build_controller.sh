#!/bin/sh

kubectl delete -f controller-rc.yaml
docker image rm -f sdp-controller
docker build --no-cache -t sdp-controller -f Dockerfile_controller .
kubectl create -f controller-rc.yaml