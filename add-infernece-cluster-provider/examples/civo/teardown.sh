#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Delete in dependency order with foreground cascading deletion, so the
# serving stack uninstalls while the cluster is still reachable and no
# cloud resource is orphaned.
set -euo pipefail
cd "$(dirname "$0")"
kubectl delete -f 05-model.yaml --cascade=foreground --ignore-not-found
kubectl delete -f 04-inference-gateway.yaml --cascade=foreground --ignore-not-found
kubectl delete -f 03-inference-cluster.yaml --cascade=foreground --ignore-not-found
kubectl wait --for=delete ic/civo-nyc1 --timeout=30m || true
echo "Cluster gone. Check the Civo console for leftovers before deleting the class and provider config."
kubectl delete -f 02-inference-class.yaml --ignore-not-found
