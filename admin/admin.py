# *******************************************************************************
# Copyright (c) 2025 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import argparse
import json
import os.path
from typing import Mapping, Any

import requests

REQUIRED_PERMISSIONS = {
    "VIEW_BADGES",
    "POLICY_VIOLATION_ANALYSIS",
    "VIEW_POLICY_VIOLATION",
    "VIEW_PORTFOLIO",
    "VIEW_VULNERABILITY",
    "VULNERABILITY_ANALYSIS"
}


def get_projects(args):
    page = 1
    projects = []

    while True:
        print(f"Getting page '{page}' from Eclipse API")
        response = requests.get(f"https://projects.eclipse.org/api/projects?github_only=1&pagesize=100&page={page}")
        if response.status_code == 200:
            new_projects = response.json()
            if len(new_projects) > 0:
                projects.extend(new_projects)
                page += 1
            else:
                break
        else:
            break

    print(f"Writing result to 'projects.json'")
    with open("projects.json", "wt") as file:
        json.dump(projects, fp=file)

def request(method: str, url: str, headers: Mapping[str, Any], data:str | None = None) -> requests.Response:
    response = requests.request(method, url, headers=headers, data=data)
    if response.status_code >= 500:
        print(f"received error while accessing url '{url}': ({response.status_code}, {response.text})")
    return response

def sync(args):
    if not os.path.exists("projects.json"):
        raise RuntimeError("'projects.json' does not exist, run admin projects first.")

    with open("projects.json", "r") as file:
        projects = json.load(fp=file)

    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": args.apikey
    }

    response = request("GET", "https://sbom.eclipse.org/api/v1/team", headers)
    teams = response.json()

    teams_map = {t["name"]: t for t in teams}

    response = request("GET", "https://sbom.eclipse.org/api/v1/oidc/group", headers)
    groups = response.json()

    group_map = {t["name"]: t for t in groups}

    for project in projects:
        project_id = project["project_id"]
        print(f"processing {project_id}...")
        print(f"  team...")
        if project_id in teams_map:
            team = teams_map[project_id]
            permissions = set(map(lambda x: x.get("name"), team.get("permissions", [])))
            uuid = team.get("uuid")
        else:
            permissions = set()
            data = {
                "name": project_id
            }

            response = request("PUT", "https://sbom.eclipse.org/api/v1/team", headers, json.dumps(data))
            uuid = response.json()["uuid"]

        print(f"  permissions...")
        print(f"     current permissions: {permissions}")

        for permission in (REQUIRED_PERMISSIONS - permissions):
            request("POST", f"https://sbom.eclipse.org/api/v1/permission/{permission}/team/{uuid}", headers)

        print(f"  group...")
        if project_id in group_map:
            group_uuid = group_map[project_id].get("uuid")
        else:
            data = {
                "name": project_id
            }

            response = request("PUT", "https://sbom.eclipse.org/api/v1/oidc/group", headers, json.dumps(data))
            group_uuid = response.json()["uuid"]

        data = {
            "team": uuid,
            "group": group_uuid
        }
        request("PUT", "https://sbom.eclipse.org/api/v1/oidc/mapping", headers, json.dumps(data))


def cli():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers()
    parser_projects = subparsers.add_parser('projects', help='get a list of all Eclipse projects')
    parser_projects.set_defaults(func=get_projects)
    parser_sync = subparsers.add_parser('sync', help='b help')
    parser_sync.set_defaults(func=sync)
    parser_sync.add_argument('--apikey', required=True, help='Api key to access sbom.eclipse.org')
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    cli()
