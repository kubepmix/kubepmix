#!/bin/bash

## 
# Create tag from timestamp
TAG=$(date +%Y%m%d%H%M%S)

docker build . -t ghcr.io/jjlakis/pmix:$TAG --push

# Update server deployment in place using kubectl, replace image in the container[0] of the deployment kube-pmix in ns kue-pmix with the new image tag:
kubectl -n kube-pmix set image deployment/kube-pmix kube-pmix=ghcr.io/jjlakis/pmix:$TAG
