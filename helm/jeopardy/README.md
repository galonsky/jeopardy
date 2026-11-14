# Jeopardy Study Helm chart

The chart runs the API, Taskiq worker and scheduler, a migration job, PostgreSQL, and Valkey. PostgreSQL and Valkey use persistent volume claims. KEDA autoscaling is optional and disabled by default; set `keda.enabled: true` when the `keda.sh/v1alpha1` CRD is installed. Without KEDA, the worker runs one replica.

## Native Kubernetes secret

Create the namespace and secret before installing. The database password must use URL-safe characters because the chart builds the app's PostgreSQL connection URL from it. Hexadecimal is a suitable format.

```sh
kubectl create namespace jeopardy
kubectl create secret generic jeopardy-secrets \
  --namespace jeopardy \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)" \
  --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 24)" \
  --from-literal=TSIDP_CLIENT_SECRET='replace-with-tsidp-client-secret'
```

Set `tsidpClientId`, `tsidpIssuer`, `allowedIdentity`, and `host` in the ignored `helm/jeopardy/values-local.yaml`. Register `https://<host>/oidc/callback/` with your OIDC provider. If classification is not configured, leave `classificationModel` empty; no OpenAI key is required for normal study.

For a private test release before TSIDP is configured, set `djangoSettingsModule: config.settings.local`. Do not use local settings for the long-lived release.

## Install

The chart defaults to `jeopardy-study:local` with `image.pullPolicy: IfNotPresent`, a `ClusterIP` Service on port 8000, and placeholder host and identity-provider values. Set a Service type and port appropriate for your cluster in the local values file. Build the image and import it into every K3s node that may schedule an app pod before installing:

```sh
docker build -f backend/Dockerfile -t jeopardy-study:local .
docker save jeopardy-study:local | sudo k3s ctr images import -
helm upgrade --install jeopardy helm/jeopardy \
  --namespace jeopardy \
  --values helm/jeopardy/values-local.yaml \
  --wait --timeout 5m
```

`values-local.yaml` is an operator-created file for cluster-specific identity, host, and storage settings; it is gitignored. The native Kubernetes Secret is managed separately from Helm and remains in the namespace across chart upgrades. Configure private ingress or a reverse proxy separately; the chart does not include network-specific hostnames or access rules.

The chart uses the cluster's default StorageClass for 5 GiB PostgreSQL and 1 GiB Valkey claims. Set `postgres.persistence.storageClassName` or `valkey.persistence.storageClassName` to select a different class. If using a tailnet proxy, configure its service name, hostname, upstream address, TLS endpoint, and access policy for your environment.

## Image delivery and GitOps

K3s uses containerd rather than Docker's image store. For local testing, import the built image on each eligible node before installing an `IfNotPresent` local tag. CircleCI publishes checked `main` commits to the configured Docker Hub repository with an immutable `sha-<commit>-<build-number>` tag. Configure Kargo to watch that image repository and this Git repository; CI does not deploy directly to Argo CD. Argo CD can sync the Git changes promoted by Kargo.

## Data and backup

PostgreSQL and Valkey are stateful workloads. Back up their PVCs before deleting the namespace or uninstalling storage. PostgreSQL contains clue imports, classifications, sessions, attempts, and study progress. Valkey contains cache and queued task data; it can be rebuilt, but pending background jobs may be lost.
