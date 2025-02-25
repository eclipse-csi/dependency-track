#! /usr/bin/env bash
#*******************************************************************************
# Copyright (c) 2020 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the Eclipse Public License 2.0
# which is available at http://www.eclipse.org/legal/epl-v20.html
# SPDX-License-Identifier: EPL-2.0
#*******************************************************************************

# Bash strict-mode
set -o nounset
set -o pipefail

IFS=$'\n\t'

RELEASE_NAME="dependency-track"
NAMESPACE="foundation-sbom"

LOCAL_CONFIG="${HOME}/.cbi/config"

if [[ ! -f "${LOCAL_CONFIG}" ]] && [[ -z "${PASSWORD_STORE_DIR:-}" ]]; then
  echo "ERROR: File '$(readlink -f "${LOCAL_CONFIG}")' does not exists"
  echo "Create one to configure the location of the password store. Example:"
  echo '{"password-store": {"it-dir": "~/.password-store"}}' | jq '.'
fi
PASSWORD_STORE_DIR="$(jq -r '.["password-store"]["it-dir"]' "${LOCAL_CONFIG}")"
PASSWORD_STORE_DIR="$(readlink -f "${PASSWORD_STORE_DIR/#~\//${HOME}/}")"
export PASSWORD_STORE_DIR

DB_PASSWD=$(pass "IT/CSI/sbom/database-password")

# ensure the helm chart for dependency track is available
helm repo add dependency-track https://dependencytrack.github.io/helm-charts

if helm status ${RELEASE_NAME} --namespace ${NAMESPACE}; then
   echo "Upgrading existing installation at ${NAMESPACE}/${RELEASE_NAME}"
   sed -e "s/{{ DB_PASSWD }}/${DB_PASSWD}/" values.yaml | helm upgrade ${RELEASE_NAME} dependency-track/dependency-track --namespace ${NAMESPACE} -f -
   exit
else
   echo "Installing Dependency Track in ${NAMESPACE}/${RELEASE_NAME}"
   sed -e "s/{{ DB_PASSWD }}/${DB_PASSWD}/" values.yaml | helm install ${RELEASE_NAME} dependency-track/dependency-track --namespace ${NAMESPACE} -f -
fi

echo "Done."