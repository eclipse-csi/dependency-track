# dependency-track
Configuration files and guides for deployment and usage of Dependency Track at the Eclipse Foundation

## Overview

Dependency-Track is deployed with the upstream
[Helm chart](https://github.com/DependencyTrack/helm-charts).

| Environment | Host                       | Namespace                                   | Release            | Values file                         |
|-------------|----------------------------|---------------------------------------------|--------------------|-------------------------------------|
| staging     | `sbom-staging.eclipse.org` | `foundation-internal-security-sbom-staging` | `dependency-track` | `deployment/values-staging.yaml`    |
| production  | `sbom.eclipse.org`         | `foundation-sbom`                           | `dependency-track` | `deployment/values-production.yaml` |

## Deploying

Add the chart repository (one-time setup) and refresh it:

```sh
helm repo add dependency-track https://dependencytrack.github.io/helm-charts  # once
helm repo update dependency-track
```

Deploy from the repository root. **Make sure the Secrets exist first (see
[Secrets](#secrets)).**

**Staging**
```sh
helm upgrade --install dependency-track dependency-track/dependency-track --version 1.6.0 \
  -n foundation-internal-security-sbom-staging -f deployment/values-staging.yaml
```

**Production**
```sh
helm upgrade --install dependency-track dependency-track/dependency-track --version 1.6.0 \
  -n foundation-sbom -f deployment/values-production.yaml
```


## Secrets

These Secrets are managed outside of Helm and must exist before deploying.

- **Secret key**: Secret `dependency-track-secret-key` (key `secret.key`) in
  both namespaces. Dependency-Track encrypts credentials it stores (e.g. the
  NVD API key, GitHub token, notification credentials) with this key. If it
  changes, they can no longer be decrypted and must be re-entered in the UI.
- **Database password**:
  - Staging: Secret `sbom-user` (key `password`). It belongs to the
    CloudNativePG cluster `sbom-postgres`, which also sets the password of the
    `dependency-track` database role from it. Both are managed outside this
    repository.
  - Production: Secret `dependencytrack-secrets` (key `db-password`), the
    password for `pgsql-write.eclipse.org/dependency-track`.

Create the secret key with a random 32-byte key (only for a new environment;
a new key invalidates the stored credentials):

```sh
openssl rand 32 > secret.key
oc create secret generic dependency-track-secret-key -n <namespace> --from-file=secret.key=secret.key
rm secret.key
```

Create or update `dependencytrack-secrets` (the password is read from the
prompt, so it doesn't end up in the shell history):

```sh
read -rs DB_PASSWD
oc create secret generic dependencytrack-secrets -n <namespace> \
  --from-literal=db-password="${DB_PASSWD}" --dry-run=client -o yaml | oc apply -f -
unset DB_PASSWD
```

Restart the API server after changing a Secret:

```
oc rollout restart statefulset -n <namespace>
```

## Upgrading

Upgrade staging first, verify it, then repeat steps 4 to 6 for production.

### 1. Check what is running

```sh
curl -s https://sbom-staging.eclipse.org/api/version | jq .version
curl -s https://sbom.eclipse.org/api/version | jq .version
```

`curl` asks the running application and is always accurate. `helm list -n
<namespace>` shows the chart version and the chart's app version, which match
what is running as long as the image tags in the values files equal the chart's
app version (see step 4) and nobody changed the workloads by hand.

### 2. Check what is available

```sh
helm repo update dependency-track
helm search repo dependency-track/dependency-track --versions | head
```

Chart `2.x` deploys Dependency-Track v5. That is not an in-place upgrade: it
needs a new PostgreSQL database and the chart's migration job. Stay on `1.x`
(Dependency-Track 4) unless that migration is planned.

### 3. Review chart changes

Compare the deployed and the new chart, and adapt the values files where needed:

```sh
helm pull dependency-track/dependency-track --version <old> --untar --untardir /tmp/chart-old
helm pull dependency-track/dependency-track --version <new> --untar --untardir /tmp/chart-new
diff -ru /tmp/chart-old/dependency-track /tmp/chart-new/dependency-track
```

- Read the chart's `MIGRATION.md` and the Dependency-Track release notes.
- Dependency-Track migrates the database schema on startup, and there is no
  downgrade path: a failed upgrade can only be undone by restoring the
  database. Production (`pgsql-write.eclipse.org`) is backed up by the
  infrastructure team; ask them for a restore. Staging has no backups and does
  not need any: if its database is lost, start from an empty one.
- Watch out for new defaults that clash with OpenShift. For example, the chart
  sets `podSecurityContext.fsGroup: 1000`, which OpenShift rejects; it is set to
  `null` in our values files.
- Render the result and review it:
  `helm template dependency-track dependency-track/dependency-track --version <new> -f deployment/values-staging.yaml`

### 4. Bump the versions

- Set `apiServer.image.tag` and `frontend.image.tag` in both values files to
  the app version of the new chart (shown by `helm search` in step 2).
- Set `--version` in the deploy commands above to the new chart version.

Never use floating tags such as `snapshot` or `latest` with
`pullPolicy: Always`. Every pod restart can then silently change the running
version, including schema migrations of the database.

### 5. Deploy

Run the deploy command for the environment (see [Deploying](#deploying)), first
with `--dry-run=server` appended to check the result against the cluster.

### 6. Verify

- `curl -s https://<host>/api/version | jq .version` shows the new version, and
  `helm list -n <namespace>` the new chart and app version.
- `oc get pods -n <namespace>`: pods are ready and not restarting; the API
  server log shows no errors from the schema migration.
- Log in via OIDC, check that projects and findings are there, and upload an
  SBOM to see it processed.
