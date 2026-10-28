#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Create the Secret the Civo provider reads its API key from. The key comes
# from the environment so it never lands in a file in this folder.
set -euo pipefail
: "${CIVO_TOKEN:?export CIVO_TOKEN=<your Civo API key> first}"
kubectl create secret generic civo-credentials \
  --namespace crossplane-system \
  --from-literal=creds="{\"token\": \"${CIVO_TOKEN}\"}" \
  --dry-run=client -o yaml | kubectl apply -f -
