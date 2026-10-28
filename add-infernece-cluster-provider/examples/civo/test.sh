#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Wait for each layer, then send one chat completion through the gateway.
set -euo pipefail
CLUSTER=civo-nyc1
kubectl wait --for=condition=Ready "ic/${CLUSTER}" --timeout=30m
kubectl wait --for=condition=Ready ig/public --timeout=10m
kubectl wait --for=condition=Ready md/qwen-demo -n ml-team --timeout=20m
kubectl get modelreplica -n ml-team
ADDRESS=$(kubectl get ig public -o jsonpath='{.status.endpoints.openAI}')
kubectl run -i --rm curl-test --image=curlimages/curl --restart=Never \
  --env="ADDRESS=${ADDRESS}" -- sh -c 'curl -sS --fail "$ADDRESS/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"ml-team/qwen\",\"messages\":[{\"role\":\"user\",\"content\":\"What is Kubernetes in one sentence?\"}],\"max_tokens\":64}"'
