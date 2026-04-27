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
| **Upgrading from v1.2.x** | ⚠️ **CRITICAL** - Must update image configuration before upgrade |
| **Upgrading from v1.1.0 or earlier with bundled persistence** | ⚠️ **CRITICAL** - Must migrate StatefulSets |
| **Using external references (External Secrets, ArgoCD, etc.)** | ⚠️ Required - Update secret/configmap names |
| **Using sample values files** | ⚠️ Required - Migrate to custom override files |
| **Relying on v1.x defaults** | ⚠️ Required - Explicitly set production values |

**Most critical issue:** Upgrading from v1.2.x without updating image configuration will cause immediate pod failures with `ImagePullBackOff`. See [Image Configuration Restructured](#1-image-configuration-restructured) before upgrading.

## Overview of Changes

Chart v2.0.0 restructures the Helm chart for a quickstart-first experience with the following major changes:

1. **Image Configuration Restructured** - Image registry and repository are now separate fields (⚠️ **CRITICAL**)
2. **Service Account Naming Changed** - Auto-generated names instead of hardcoded defaults
3. **Secrets and ConfigMaps Restructured** - Monolithic resources split into focused components
4. **Default Values Changed** - Optimized for quickstart evaluation with embedded components
5. **Sample Values Files Removed** - Consolidated into comprehensive inline documentation
6. **Bundled Persistence VCT Labels** - One-time StatefulSet migration required (if using bundled persistence from ≤v1.1.0)
7. **Image Pull Policy Changed** - Default changed from `Always` to `IfNotPresent`

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

If upgrading from v1.1.0 or earlier, you may also need to address:
- [Bundled Persistence VCT Labels](#6-bundled-persistence-vct-labels-migration) (if using bundled persistence)

### From v1.2.x to v2.0.0

All users upgrading from v1.2.x must address:
- [Image Configuration Restructured](#1-image-configuration-restructured)
- [Default Values Changed](#4-default-values-changed)
- [Image Pull Policy Changed](#7-image-pull-policy-change)

## Breaking Changes Detail

### 1. Image Configuration Restructured

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

### 2. Service Account Naming Changed

Default service account names are now auto-generated as `{release}-solace-agent-mesh-{component}-sa` instead of the previous hardcoded `solace-agent-mesh-sa`.

**Old Behavior (v1.x):**
- Service account: `solace-agent-mesh-sa` (hardcoded)

**New Behavior (v2.0.0):**
- Service account: `{release}-solace-agent-mesh-core-sa` (auto-generated from release name)
- Example: If release name is `sam`, SA name is `sam-solace-agent-mesh-core-sa`

**Migration Action:**
- If you need to preserve the old service account name, explicitly set it:
  ```yaml
  samDeployment:
    serviceAccount:
      name: solace-agent-mesh-sa
  ```
- Update any external references to the service account (e.g., IAM role bindings, workload identity)

### 3. Secrets and ConfigMaps Restructured

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

### 4. Default Values Changed

Chart v2.0.0 changes several default values to optimize for quickstart evaluation.

| Setting | v1.x Default | v2.0.0 Default | Impact |
|---------|--------------|----------------|--------|
| `global.broker.embedded` | N/A (new field) | `true` | Deploys embedded Solace broker |
| `global.persistence.enabled` | `false` | `true` | Deploys PostgreSQL and SeaweedFS |
| `sam.authorization.enabled` | `true` | `false` | Disables RBAC/OIDC authentication |
| `service.type` | `LoadBalancer` | `ClusterIP` | Requires port-forward for access |
| `service.tls.enabled` | `true` | `false` | Disables TLS |
| `samDeployment.image.pullPolicy` | `Always` | `IfNotPresent` | Reduces registry load |

**Migration Action:**

:::danger Resource Impact
The new defaults deploy embedded PostgreSQL, SeaweedFS, and Solace broker, consuming additional cluster resources. Existing deployments with explicit values are NOT affected.
:::

If you were relying on the v1.x defaults, you must now **explicitly set** production values:

```yaml
global:
  broker:
    embedded: false
  persistence:
    enabled: false

sam:
  authorization:
    enabled: true

service:
  type: LoadBalancer
  tls:
    enabled: true
```

### 5. Sample Values Files Removed

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

### 6. Bundled Persistence VCT Labels Migration

:::warning Only for Bundled Persistence Users
This section only applies if you are using **bundled persistence** (`global.persistence.enabled: true`) and upgrading from chart version ≤1.1.0. External persistence users and new installations are **not affected**.
:::

Starting with chart versions after 1.1.0, the bundled persistence layer uses minimal VolumeClaimTemplate (VCT) labels for StatefulSets. This change prevents upgrade failures when labels change over time, but requires a one-time migration for existing deployments.

**Why this matters:** Kubernetes StatefulSet VCT labels are immutable. Without migration, upgrades will fail with:
```
StatefulSet.apps "xxx-postgresql" is invalid: spec: Forbidden: updates to statefulset spec
for fields other than 'replicas', 'ordinals', 'template', 'updateStrategy'... are forbidden
```

**Migration Procedure:**

**Step 1:** Delete StatefulSets while preserving data (PVCs are retained):

```bash
kubectl delete sts <release>-postgresql <release>-seaweedfs --cascade=orphan -n <namespace>
```

The `--cascade=orphan` flag ensures pods and PVCs remain intact.

**Step 2:** Upgrade the Helm release:

```bash
helm upgrade <release> solace/solace-agent-mesh \
  -f your-values.yaml \
  -n <namespace>
```

**Step 3:** Verify the upgrade succeeded and data is intact:

```bash
# Check pods are running
kubectl get pods -l app.kubernetes.io/instance=<release> -n <namespace>

# Verify PVCs are still bound
kubectl get pvc -l app.kubernetes.io/instance=<release> -n <namespace>
```

The new StatefulSets are created with minimal VCT labels and automatically reattach to the existing PVCs, preserving all your data.

### 7. Image Pull Policy Change

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

Before upgrading to chart v2.0.0:

- [ ] **Backup your current deployment**
  - Export current values: `helm get values <release> -n <namespace> > current-values.yaml`
  - Backup secrets and configmaps
  - Document current service account names
  - If using bundled persistence, verify PVC backup strategy

- [ ] **Update image configuration** (CRITICAL)
  - Split `image.repository` into `global.imageRegistry` + `image.repository`
  - Remove registry hostname from repository fields
  - Validate with `helm template` to check for double-prefix issue
  - Review all image references in your values file

- [ ] **Review image pull policy**
  - If using mutable tags (e.g., `latest`), explicitly set `pullPolicy: Always`
  - If using immutable tags, no action needed

- [ ] **Bundled persistence migration** (if applicable)
  - Only if using `global.persistence.enabled: true` and upgrading from ≤v1.1.0
  - Plan StatefulSet deletion and recreation window
  - Verify PVCs will not be deleted (use `--cascade=orphan`)

- [ ] **Review service account naming**
  - Decide: keep old name (explicit) or migrate to new auto-generated name
  - Update external IAM/RBAC bindings if needed

- [ ] **Update external references**
  - Check External Secrets Operator configurations
  - Check ArgoCD/Flux patches
  - Check backup/restore scripts
  - Check monitoring/alerting rules

- [ ] **Review default value changes**
  - Explicitly set production values if you were relying on v1.x defaults
  - Confirm embedded components won't strain cluster resources

- [ ] **Migrate from sample values files**
  - Create custom override files based on `values.yaml` inline docs
  - Remove references to `samples/values/*.yaml`

- [ ] **Test in non-production first**
  - Perform upgrade in dev/staging environment
  - Validate all integrations work with new resource names
  - Test RBAC/OIDC authentication if enabled
  - Verify pods start successfully (check for ImagePullBackOff)

## Upgrade Command

After completing the migration checklist:

**Step 1: Validate configuration (CRITICAL)**

```bash
# Validate that image references are correct (no double-prefix)
helm template <release> solace/solace-agent-mesh \
  -f your-values.yaml \
  | grep "image:" | sort -u
```

Verify output shows each image with registry prefix exactly once:
- ✅ Correct: `gcr.io/gcp-maas-prod/solace-agent-mesh-enterprise:1.97.2`
- ❌ Wrong: `gcr.io/gcp-maas-prod/gcr.io/gcp-maas-prod/solace-agent-mesh-enterprise:1.97.2`

**Step 2: Review what will change (if using helm-diff plugin)**

```bash
helm diff upgrade <release> solace/solace-agent-mesh \
  --namespace <namespace> \
  -f your-values.yaml
```

**Step 3: Perform the upgrade**

```bash
helm upgrade <release> solace/solace-agent-mesh \
  --namespace <namespace> \
  -f your-values.yaml
```

**Step 4: Verify the upgrade**

```bash
# Check rollout status
kubectl rollout status deployment/<release>-solace-agent-mesh-core -n <namespace>

# Verify pods are running
kubectl get pods -l app.kubernetes.io/instance=<release> -n <namespace>

# Check for ImagePullBackOff errors
kubectl get pods -l app.kubernetes.io/instance=<release> -n <namespace> | grep -i "ImagePullBackOff\|ErrImagePull"
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

**Solution:** See [Bundled Persistence VCT Labels Migration](#6-bundled-persistence-vct-labels-migration) section above.

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
- If you deleted StatefulSets during migration, you may need to restore from backup

## Getting Help

If you encounter migration issues:

1. Review the [Kubernetes Quick Start](./quickstart-kubernetes.md) for v2.0.0 examples
2. Check the inline documentation in the chart's `values.yaml`
3. Contact Solace support with your migration questions

## Related Documentation

- [Kubernetes Quick Start](./quickstart-kubernetes.md) - Updated for v2.0.0
- [Production Kubernetes Installation](./production-kubernetes.md) - Production configuration examples
- [Air-Gapped Kubernetes Installation](./airgap-kubernetes.md) - Air-gapped deployment guidance
