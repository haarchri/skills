# Civo: apply-able example

A Civo InferenceCluster with one L40S node, a gateway, and a 0.5B model,
end to end. This is the shape the skill produces in `examples/<cloud>/` for
a new provider; Civo is the worked example.

## Prerequisites

- A Modelplane control plane with Civo support installed, `kubectl` pointing
  at it. Crossplane activates the Civo provider's resources on first use.
- A Civo account with GPU node access in NYC1 (or change `region` and `size`).
- `export CIVO_TOKEN=<your Civo API key>`

## Apply

```bash
./00-credentials.sh
kubectl apply -f .
./test.sh
```

`kubectl apply -f .` applies the numbered files in order; anything applied
before its dependency is ready reconciles once it is. `test.sh` waits for the
cluster (about 15 minutes, the GPU Operator installs the driver on first
boot), the gateway and the deployment, then sends one chat completion.

What each file is:

| File | What it creates |
|---|---|
| `00-credentials.sh` | `civo-credentials` Secret in `crossplane-system`, from `CIVO_TOKEN` |
| `01-clusterproviderconfig.yaml` | the provider's `default` ClusterProviderConfig |
| `02-inference-class.yaml` | the L40S hardware class |
| `03-inference-cluster.yaml` | the cluster: network, firewall, system pool, one GPU node |
| `04-inference-gateway.yaml` | an unauthenticated gateway on that cluster |
| `05-model.yaml` | `ml-team` namespace, a ModelDeployment, a ModelService |

## Clean up

```bash
./teardown.sh
```

It deletes model, gateway, then cluster with foreground cascading deletion,
so the serving stack uninstalls while the cluster is still reachable. Check
the Civo console afterwards; a deletion that hangs leaves billable resources.

## Expected differences from other clouds

No ModelCache (Civo storage is ReadWriteOnce only), no fabric, and the pool is
fixed-size. Set `minNodeCount`/`maxNodeCount` on the pool to have Modelplane
install the cluster autoscaler.
