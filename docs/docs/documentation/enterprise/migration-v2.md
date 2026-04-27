---
title: Migration to Chart v2.0.0
sidebar_position: 7
---

# Migration to Chart v2.0.0

This guide covers breaking changes when upgrading from Helm chart v1.x to v2.0.0.

:::warning Breaking Changes
Chart v2.0.0 introduces several breaking changes to configuration structure, default values, and resource naming. Review this guide carefully before upgrading.
:::

## Quick Decision Guide

**Do I need to read this guide?**

| Your Situation | Action Required |
|---------------|-----------------|
| **New installation (never used v1.x)** | ✅ No action - skip this guide |
| **Upgrading from v1.2.x** | ⚠️ **CRITICAL** - Multiple required changes before upgrade (see below) |
| **Using `localCharts` or `chartBaseUrl` in values** | ❌ **SCHEMA FAILURE** - Must remove before upgrade or `helm upgrade` fails immediately |
| **Session key not explicitly set** | ⚠️ **CRITICAL** - Extract old value first or all users are logged out |
| **Using embedded PostgreSQL/SeaweedFS** | ⚠️ **CRITICAL** - Must run `kubectl annotate` before upgrade or PostgreSQL fails to restart |
| **Using external references (External Secrets, ArgoCD, etc.)** | ⚠️ Required - Update secret/configmap names |
| **Using `samDeployment.imagePullSecret`** | ⚠️ Required - Move to `global.imagePullSecrets` |
| **Using cloud workload identity (IRSA, GKE WI, Azure WI)** | ⚠️ Required - Update IAM trust policy to new SA name |
| **Using bundled persistence and upgrading from ≤v1.1.0** | ⚠️ **CRITICAL** - Must migrate StatefulSets before upgrade |
| **Relying on v1.x defaults** | ⚠️ Required - Explicitly set production values |

**Most critical issues for v1.2.x upgrades:** `localCharts`/`chartBaseUrl` removal causes schema failure, `sam.sessionSecretKey` change logs out all users, and the `ServiceAccount` annotate step is required for embedded persistence. See the full breaking changes below.

## What's New in v2.0.0

In addition to the breaking changes below, v2.0.0 introduces the following new capabilities:

| Feature | Description | Values Key |
|---------|-------------|------------|
| **GCR Pull Secret Automation** | Pass a dockerconfigjson credentials file via `--set-file` and the chart automatically creates the image pull secret and injects it into all pod specs — no manual `kubectl create secret` step required. Mutually exclusive with `global.imagePullSecrets`. See [GCR Credentials File](./quickstart-kubernetes.md#gcr-credentials-file) and [Air-Gapped: Step 3](./airgap-kubernetes.md#step-3-configuring-image-pull-secrets). | `global.imagePullKey` |
| **Custom CA Certificates** | Inject custom or self-signed CA certificates for internal infrastructure (broker, OIDC provider, LLM service) via a Kubernetes ConfigMap. See [Custom CA Certificates](./production-kubernetes.md#custom-ca-certificates). | `samDeployment.customCA` |
| **Embedded Solace Broker** | Deploy a single-node Solace PubSub+ broker in-cluster for evaluation — no external broker required. See [Kubernetes Quick Start](./quickstart-kubernetes.md). | `global.broker.embedded` |
| **SAM Doctor Pre-flight Checks** | Pre-install/pre-upgrade Helm hook that validates broker, database, object storage, TLS, and OIDC configuration before any workload pods are created — misconfigurations surface as a clear error instead of `CrashLoopBackOff`. Disabled by default (`samDoctor.enabled: false`); requires the enterprise image to include `sam_doctor`. See [SAM Doctor](./production-kubernetes.md#sam-doctor-pre-flight-validation). | `samDoctor.enabled` |
| **JSON Schema Validation** | `values.schema.json` is now shipped with the chart — Helm rejects invalid configuration at `helm lint`, `helm install`, `helm upgrade`, and `helm template` with clear error messages. Also enforces conditional rules (e.g., external datastore credentials required when `global.persistence.enabled: false`). | Built-in |
| **Cluster Resource Checks** | At `helm install`/`upgrade` time, validates that referenced Secrets, ConfigMaps, StorageClass, and IngressClass actually exist in the cluster — reports all missing resources in one aggregated error instead of letting pods fail with `ImagePullBackOff` or PVCs get stuck `Pending`. No-op during `helm template`/`--dry-run=client`. | `validations.clusterResourceChecks` |

## Migration Timeline

### From v1.1.0 and Earlier

If upgrading from v1.1.0 or earlier with bundled persistence, also address:
- [Bundled Persistence VCT Labels](#9-bundled-persistence-vct-labels)

### From v1.2.x to v2.0.0

All users upgrading from v1.2.x must address:
- [localCharts and chartBaseUrl Keys Removed](#1-localcharts-and-chartbaseurl-keys-removed)
- [Image Configuration Restructured](#2-image-configuration-restructured)
- [Session Key Secret Location Changed](#3-session-key-secret-location-changed)
- [Service Account Naming Changed](#4-service-account-naming-changed) (+ `kubectl annotate` if using embedded persistence)
- [Default Values Changed](#7-default-values-changed)
- [Image Pull Policy Changed](#10-image-pull-policy-change)

## Breaking Changes Detail

### 1. localCharts and chartBaseUrl Keys Removed

In v2.0.0, the agent chart is always bundled inside the main chart. These keys no longer exist in the schema.

**Old values (v1.2.x) — remove these:**
```yaml
samDeployment:
  agentDeployer:
    chartBaseUrl: "https://..."
    localCharts:
      enabled: true
      mountPath: "/opt/helm-charts"
```

Also update the version fields:
```yaml
samDeployment:
  agentDeployer:
    version: "k8s-2.0.0"   # was k8s-1.2.x
    chartVersion: "2.0.0"   # was 1.2.x
```

### 2. Image Configuration Restructured

:::warning Critical - Pods Will Fail Without This Change
All users upgrading from v1.2.x must update their values file before running `helm upgrade`. The default `repository` value in v1.2.x included the registry hostname (`gcr.io/gcp-maas-prod/solace-agent-mesh-enterprise`). In v2.0.0, the chart prepends `global.imageRegistry` to `repository` automatically — upgrading without updating your values will produce a double-prefixed image reference that Kubernetes cannot pull, and pods will go into `ImagePullBackOff` immediately.
:::

Starting with v2.0.0, the registry is separated from the repository. The chart constructs the full image reference as `registry/repository:tag`, where `registry` defaults to `global.imageRegistry` (`gcr.io/gcp-maas-prod`).

**What breaks without migration:**
```
# Kubernetes will try to pull this broken image reference:
gcr.io/gcp-maas-prod/gcr.io/gcp-maas-prod/solace-agent-mesh-enterprise:1.97.2
```

**Old Format (v1.2.x):**
```yaml
samDeployment:
  image:
    repository: gcr.io/gcp-maas-prod/solace-agent-mesh-enterprise
    tag: "1.83.1"
    pullPolicy: Always
  agentDeployer:
    image:
      repository: gcr.io/gcp-maas-prod/sam-agent-deployer
      tag: "1.6.3"
      pullPolicy: Always
```

**New Format (v2.0.0):**
```yaml
# global.imageRegistry defaults to gcr.io/gcp-maas-prod — no change needed for GCR users
samDeployment:
  image:
    repository: solace-agent-mesh-enterprise  # registry prefix removed
    tag: "1.97.2"
  agentDeployer:
    image:
      repository: sam-agent-deployer          # registry prefix removed
      tag: "1.7.0"
```

**For air-gap or internal registry users**, set `global.imageRegistry` to redirect all images with a single value:
```yaml
global:
  imageRegistry: my-registry.internal  # all images redirect here

samDeployment:
  image:
    repository: solace-agent-mesh-enterprise  # registry prefix removed
    tag: "1.97.2"
  agentDeployer:
    image:
      repository: sam-agent-deployer          # registry prefix removed
      tag: "1.7.0"
```

**Migration Steps:**

**Step 1:** Remove the registry hostname from `samDeployment.image.repository` and `samDeployment.agentDeployer.image.repository` in your values file. If you use an internal registry, set `global.imageRegistry` to that registry hostname.

**Step 2:** Validate your updated values file before upgrading — check that all image references resolve correctly:
```bash
helm template <release-name> solace/solace-agent-mesh \
  -f updated-values.yaml \
  | grep "image:" | sort -u
```
Every image should show the correct registry prefix exactly once (e.g., `gcr.io/gcp-maas-prod/solace-agent-mesh-enterprise:1.97.2`).

**Step 3:** Proceed with the upgrade (see [Upgrade Command](#upgrade-command) section).

### 3. Session Key Secret Location Changed

:::danger All Users Logged Out Without This Step
In v1.2.x the session key was stored in `<release>-environment`. In v2.0.0 it moves to a new secret with a different name. On first upgrade, the chart cannot find the old value and generates a new random key — instantly logging out all active users.
:::

**If `sam.sessionSecretKey` was already set explicitly in your v1.2.x values:** carry it forward unchanged. No action needed.

**If it was not set explicitly**, extract the value before upgrading:

```bash
kubectl get secret <release>-environment -n <namespace> \
  -o go-template='{{index .data "SESSION_SECRET_KEY" | base64decode}}{{"\n"}}'
```

Then set it explicitly in your v2.0.0 values:

```yaml
sam:
  sessionSecretKey: "<value from above>"
```

### 4. Service Account Naming Changed

Default service account names are now auto-generated as `{release}-solace-agent-mesh-{component}-sa` instead of the previous hardcoded `solace-agent-mesh-sa`.

**Old Behavior (v1.x):**
- Single shared SA: `solace-agent-mesh-sa` (used by core, agent-deployer, PostgreSQL, SeaweedFS, and agent pods)

**New Behavior (v2.0.0):**
- Core SA: `{release}-solace-agent-mesh-core-sa` (auto-generated)
- The old `solace-agent-mesh-sa` is deleted by Helm during upgrade

#### Pre-Upgrade: Protect the Shared ServiceAccount (Embedded Persistence Only)

:::warning Required for Embedded PostgreSQL/SeaweedFS Users
If you use embedded persistence (`global.persistence.enabled: true`), run this command **before** `helm upgrade`. If skipped, Helm deletes `solace-agent-mesh-sa` during the upgrade — PostgreSQL and SeaweedFS cannot restart and running agent pods lose their SA reference.
:::

```bash
kubectl annotate serviceaccount solace-agent-mesh-sa \
  -n <namespace> \
  "helm.sh/resource-policy=keep"
```

After annotating, keep these values explicitly in your v2.0.0 values file so PostgreSQL and SeaweedFS continue using the preserved SA:

```yaml
persistence-layer:
  postgresql:
    serviceAccountName: solace-agent-mesh-sa
  seaweedfs:
    serviceAccountName: solace-agent-mesh-sa
```

The SA is no longer tracked by Helm after the upgrade but existing pods continue using it.

#### Workload Identity Users (IRSA / GKE WI / Azure WI)

If you have an IAM trust policy attached to `solace-agent-mesh-sa` for cloud storage access, update it to the new core SA name **before upgrading**. Find the new name with:

```bash
helm template <release> <chart> -f values-2.0.0.yaml \
  | grep "kind: ServiceAccount" -A5 | grep " name:"
```

#### External Reference Update
- Update any external IAM/RBAC bindings if they reference `solace-agent-mesh-sa` for the core pod (not needed if you are preserving it for embedded persistence)

### 5. Pull Secret Migration

In v1.2.x, pull secrets were attached to the shared `solace-agent-mesh-sa` ServiceAccount. In v2.0.0, core and agent-deployer pods use new auto-generated ServiceAccounts with no pull secret attached.

**Old values (v1.2.x):**
```yaml
samDeployment:
  imagePullSecret: "my-reg-secret"
```

**New values (v2.0.0):**
```yaml
global:
  imagePullSecrets:
    - "my-reg-secret"

samDeployment:
  imagePullSecret: ""  # clear the old field
```

Alternatively, use `global.imagePullKey` with `--set-file` to let the chart create the secret automatically. See [GCR Credentials File](./quickstart-kubernetes.md#gcr-credentials-file).

### 6. Secrets and ConfigMaps Restructured

The monolithic secret and configmap have been split into multiple focused resources for better security and organization.

**Old Resources (v1.x):**
- `solace-agent-mesh-secret` (single monolithic secret)
- `solace-agent-mesh-config` (single monolithic configmap)

**New Resources (v2.0.0):**

All resources follow the naming pattern `{release}-solace-agent-mesh-{component}`. To see the exact names in your deployment:

```bash
kubectl get secrets -n <namespace> -l app.kubernetes.io/instance=<release>
kubectl get configmaps -n <namespace> -l app.kubernetes.io/instance=<release>
```

**Migration Action:**
- Pods will automatically pick up the new secret and configmap names
- **Update external references** if you have:
  - External Secrets Operator syncing to SAM secrets
  - ArgoCD or other GitOps patches referencing old names
  - Custom scripts or operators reading SAM secrets/configmaps
  - Backup/restore automation referencing old names

### 7. Default Values Changed

Chart v2.0.0 changes several default values to optimize for quickstart evaluation.

| Setting | v1.x Default | v2.0.0 Default | Impact |
|---------|--------------|----------------|--------|
| `global.broker.embedded` | N/A (new field) | `true` | Deploys embedded Solace broker |
| `global.persistence.enabled` | `false` | `true` | Deploys PostgreSQL and SeaweedFS |
| `sam.authorization.enabled` | `true` | `false` | Disables RBAC/OIDC authentication |
| `service.type` | `LoadBalancer` | `ClusterIP` | Requires port-forward for access |
| `service.tls.enabled` | `true` | `false` | Disables TLS |
| `samDeployment.image.pullPolicy` | `Always` | `IfNotPresent` | Reduces registry load |

### 8. Sample Values Files Removed

Sample values files in `samples/values/` have been removed and consolidated into comprehensive inline documentation within the main `values.yaml`.

**Removed Files:**
- `samples/values/quickstart.yaml`
- `samples/values/production.yaml`
- `samples/values/sam-tls-oidc-bundled-persistence.yaml`
- `samples/values/sam-tls-bundled-persistence-no-auth.yaml`
- And other sample files

**New Approach:**
- Use the main `values.yaml` as reference documentation
- Create custom override files (e.g., `production-overrides.yaml`)

**Migration Action:**
- If you were using `-f samples/values/*.yaml`, migrate to custom override files
- Reference the inline documentation in `values.yaml` for all configuration options
- See [Production Kubernetes Installation](./production-kubernetes.md) for examples

### 9. Bundled Persistence VCT Labels

:::warning Only for Bundled Persistence Users Upgrading from ≤v1.1.0
This section only applies if you are using **bundled persistence** (`global.persistence.enabled: true`) and upgrading from chart version ≤1.1.0. External persistence users and new installations are **not affected**.
:::

Starting with chart versions after 1.1.0, the bundled persistence layer uses minimal VolumeClaimTemplate (VCT) labels for StatefulSets. This prevents upgrade failures when labels change over time, but requires a one-time migration for existing deployments.

**Why this matters:** Kubernetes StatefulSet VCT labels are immutable. Without migration, upgrades will fail with:
```
StatefulSet.apps "xxx-postgresql" is invalid: spec: Forbidden: updates to statefulset spec
for fields other than 'replicas', 'ordinals', 'template', 'updateStrategy'... are forbidden
```

**Step 1:** Delete StatefulSets while preserving data (`--cascade=orphan` retains PVCs):

```bash
kubectl delete sts <release>-postgresql <release>-seaweedfs --cascade=orphan -n <namespace>
```

**Step 2:** Upgrade the Helm release:

```bash
helm upgrade <release> solace/solace-agent-mesh \
  -f your-values.yaml \
  -n <namespace>
```

**Step 3:** Verify the upgrade succeeded and data is intact:

```bash
kubectl get pods -l app.kubernetes.io/instance=<release> -n <namespace>
kubectl get pvc -l app.kubernetes.io/instance=<release> -n <namespace>
```

The new StatefulSets automatically reattach to the existing PVCs, preserving all data.

### 10. Image Pull Policy Change

The default `pullPolicy` for all images has changed from `Always` to `IfNotPresent`.

**Old Behavior (v1.x):**
```yaml
samDeployment:
  image:
    pullPolicy: Always
  agentDeployer:
    image:
      pullPolicy: Always
```

**New Behavior (v2.0.0):**
```yaml
samDeployment:
  image:
    pullPolicy: IfNotPresent  # New default
  agentDeployer:
    image:
      pullPolicy: IfNotPresent  # New default
```

**Impact:**
- Deployments with pinned tags (e.g., `1.97.2`) are unaffected
- If you use mutable tags (e.g., `latest`) or republish images under the same tag, restore the previous behavior explicitly:

```yaml
samDeployment:
  image:
    pullPolicy: Always
  agentDeployer:
    image:
      pullPolicy: Always
```

**Migration Action:**
- Review your image tagging strategy
- If using immutable tags (recommended), no action needed
- If using mutable tags, explicitly set `pullPolicy: Always`

## Migration Checklist

### Phase 1: Update Values File

- [ ] [Remove localCharts and chartBaseUrl](#1-localcharts-and-chartbaseurl-keys-removed)
- [ ] [Restructure image configuration](#2-image-configuration-restructured)
- [ ] [Preserve session key](#3-session-key-secret-location-changed)
- [ ] [Migrate pull secret](#5-pull-secret-migration)
- [ ] [Apply default value overrides](#7-default-values-changed) (broker, persistence, authorization)
- [ ] [Migrate from sample values files](#8-sample-values-files-removed) (if applicable)
- [ ] [Review image pull policy](#10-image-pull-policy-change)
- [ ] [Validate values file](#upgrade-command) (catches schema errors before touching the cluster)

### Phase 2: Prepare the Cluster

- [ ] **Backup current deployment**
  - Export values: `helm get values <release> -n <namespace> > current-values.yaml`
  - If using bundled persistence, verify PVC backup strategy

- [ ] [Migrate StatefulSet VCT labels](#9-bundled-persistence-vct-labels) (bundled persistence + upgrading from ≤v1.1.0 only)
- [ ] [Annotate shared ServiceAccount](#pre-upgrade-protect-the-shared-serviceaccount-embedded-persistence-only) (embedded persistence users only)
- [ ] [Update workload identity trust policy](#workload-identity-users-irsa--gke-wi--azure-wi) (IRSA/GKE WI/Azure WI users only)
- [ ] [Update external references](#6-secrets-and-configmaps-restructured) (External Secrets Operator, ArgoCD/Flux, backup scripts)

### Phase 3: Upgrade and Verify

- [ ] Run `helm upgrade` (see [Upgrade Command](#upgrade-command))
- [ ] Confirm running agents (`sam-agent-*`) were unaffected — they continue on the old agent chart throughout
- [ ] Verify pods start successfully (check for `ImagePullBackOff`)
- [ ] Test RBAC/OIDC authentication

## Upgrade Command

After completing the migration checklist:

**Step 1: Validate the values file (catches schema errors before touching the cluster)**

```bash
helm template <release> <chart> -n <namespace> -f values-2.0.0.yaml > /dev/null
```

Also verify image references have no double-prefix:

```bash
helm template <release> <chart> -f values-2.0.0.yaml \
  | grep "image:" | sort -u
```

- ✅ Correct: `gcr.io/gcp-maas-prod/solace-agent-mesh-enterprise:1.97.2`
- ❌ Wrong: `gcr.io/gcp-maas-prod/gcr.io/gcp-maas-prod/solace-agent-mesh-enterprise:1.97.2`

**Step 2: Review what will change (if using helm-diff plugin)**

```bash
helm diff upgrade <release> <chart> \
  --namespace <namespace> \
  -f values-2.0.0.yaml
```

**Step 3: Run the upgrade**

```bash
helm upgrade <release> <chart> \
  --namespace <namespace> \
  -f values-2.0.0.yaml
```

:::info Running Agents Are Unaffected
`helm upgrade` on the main chart does not touch `sam-agent-*` pods. They continue running on the old agent chart throughout the upgrade with no intervention required. After the upgrade, new agents use the 2.0.0 agent chart. Existing agents can be redeployed from the SAM UI to pick up the new version.
:::

**Step 4: Verify the upgrade**

```bash
# Check rollout status
kubectl rollout status deployment/<release>-solace-agent-mesh-core -n <namespace>

# Verify pods are running
kubectl get pods -l app.kubernetes.io/instance=<release> -n <namespace>

# Check for ImagePullBackOff errors
kubectl get pods -l app.kubernetes.io/instance=<release> -n <namespace> | grep -i "ImagePullBackOff\|ErrImagePull"

# Confirm new secrets were created
kubectl get secrets -n <namespace> | grep -E "core-secrets|database|storage"
```

## Troubleshooting Migration Issues

### ImagePullBackOff After Upgrade

**Symptom:** Pods fail to start with `ImagePullBackOff` or `ErrImagePull` errors.

**Cause:** Double-prefixed image reference due to incomplete image configuration migration.

**Solution:**
```bash
# Check actual image reference being used
kubectl describe pod <pod-name> -n <namespace> | grep "Image:"

# If you see double-prefix (e.g., gcr.io/gcp-maas-prod/gcr.io/gcp-maas-prod/...):
# 1. Update your values file to remove registry from repository
# 2. Rollback and re-upgrade with corrected values
helm rollback <release> -n <namespace>
helm upgrade <release> solace/solace-agent-mesh -n <namespace> -f corrected-values.yaml
```

### StatefulSet Update Failures (Bundled Persistence)

**Symptom:** Upgrade fails with "StatefulSet.apps is invalid: spec: Forbidden" error.

**Cause:** VCT labels are immutable in StatefulSets.

**Solution:** See [Bundled Persistence VCT Labels](#9-bundled-persistence-vct-labels) section above.

### Service Account Not Found

**Symptom:** Pods fail with "service account not found" errors.

**Cause:** Service account name changed from hardcoded to auto-generated.

**Solution:**
```yaml
# In your values file, explicitly set the old service account name
samDeployment:
  serviceAccount:
    name: solace-agent-mesh-sa  # Your old SA name
```

### External References Broken

**Symptom:** External Secrets Operator, ArgoCD patches, or monitoring fail.

**Cause:** Secret/ConfigMap names changed from monolithic to focused resources.

**Solution:** Update external references to use new resource names:
- Old: `<release>-secret`, `<release>-config`
- New: `<release>-secret-auth`, `<release>-secret-core`, `<release>-core-env`, etc.

## Rollback

If you encounter issues, rollback to the previous chart version:

```bash
helm rollback <release> -n <namespace>
```

**After rollback:**
- Verify pods are running
- Check that old secrets/configmaps still exist

## Getting Help

If you encounter migration issues:

1. Check the inline documentation in the chart's `values.yaml`
2. Contact Solace support with your migration questions

## Related Documentation

- [Kubernetes Quick Start](./quickstart-kubernetes.md) - Updated for v2.0.0
- [Production Kubernetes Installation](./production-kubernetes.md) - Production configuration examples
- [Air-Gapped Kubernetes Installation](./airgap-kubernetes.md) - Air-gapped deployment guidance
