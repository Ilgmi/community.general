#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2024, Michael Ilg
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = '''
module: consul_agent_check
short_description: Add, modify and delete checks within a consul cluster
description:
 - Allows the addition, modification and deletion of checks in a consul
   cluster via the agent. For more details on using and configuring Checks,
   see U(https://developer.hashicorp.com/consul/api-docs/agent/check).
author: "Michael Ilg (@Ilgmi)"
extends_documentation_fragment:
  - community.general.consul
  - community.general.consul.actiongroup_consul
  - community.general.consul.token
  - community.general.attributes
attributes:
  check_mode:
    support: full
    version_added: 8.3.0
  diff_mode:
    support: partial
    version_added: 8.3.0
    details:
      - In check mode the diff will miss operational attributes.
options:
  state:
    description:
      - Whether the check should be present or absent.
    choices: ['present', 'absent']
    default: present
    type: str
  name:
    description:
    - Required name for the service check.
    type: str
  id:
    description:
      - An unique ID for the service check.
    type: str
  interval:
    description:
      - The interval at which the service check will be run.
        This is a number with a V(s) or V(m) suffix to signify the units of seconds or minutes, for example V(15s) or V(1m).
        If no suffix is supplied V(s) will be used by default, for example V(10) will be V(10s).
      - Required if one of the parameters O(args), O(http), or O(tcp) is specified.
    type: str
  notes:
    description:
      - Notes to attach to check when registering it.
    type: str
  args:
    description:
      - Specifies command arguments to run to update the status of the check.
      - Requires O(interval) to be provided.
      - Mutually exclusive with O(ttl), O(tcp) and O(http).
      - "There is an issue with args. It throws an 'Invalid check: TTL must be > 0 for TTL checks'"
      - See U(https://github.com/hashicorp/consul/issues/6923#issuecomment-564476529) for more details
    type: list
    elements: str
  ttl:
    description:
      - Checks can be registered with a TTL instead of a O(args) and O(interval)
        this means that the service will check in with the agent before the
        TTL expires. If it doesn't the check will be considered failed.
        Required if registering a check and the script an interval are missing
        Similar to the interval this is a number with a V(s) or V(m) suffix to
        signify the units of seconds or minutes, for example V(15s) or V(1m).
        If no suffix is supplied V(s) will be used by default, for example V(10) will be V(10s).
      - Mutually exclusive with O(args), O(tcp) and O(http).
    type: str
  tcp:
    description:
      - Checks can be registered with a TCP port. This means that consul
        will check if the connection attempt to that port is successful (that is, the port is currently accepting connections).
        The format is V(host:port), for example V(localhost:80).
      - Requires O(interval) to be provided.
      - Mutually exclusive with O(args), O(ttl) and O(http).
    type: str
    version_added: '1.3.0'
  http:
    description:
      - Checks can be registered with an HTTP endpoint. This means that consul
        will check that the http endpoint returns a successful HTTP status.
      - Requires O(interval) to be provided.
      - Mutually exclusive with O(args), O(ttl) and O(tcp).
    type: str
  timeout:
    description:
      - A custom HTTP check timeout. The consul default is 10 seconds.
        Similar to the interval this is a number with a V(s) or V(m) suffix to
        signify the units of seconds or minutes, for example V(15s) or V(1m).
        If no suffix is supplied V(s) will be used by default, for example V(10) will be V(10s).
    type: str
  service_id:
    description:
      - The ID for the service, must be unique per node. If O(state=absent),
        defaults to the service name if supplied.
    type: str
'''

EXAMPLES = '''
- name: register tcp check for service 'nginx'
  community.general.consul_agent_check:
    name: nginx_tcp_check
    service_id: nginx
    interval: 60s
    tcp: localhost:80
    notes: "Nginx Check"

- name: register http check for service 'nginx'
  community.general.consul_agent_check:
    name: nginx_http_check
    service_id: nginx
    interval: 60s
    http: http://localhost:80/status
    notes: "Nginx Check"

- name: Remove check for service 'nginx'
  community.general.consul_agent_check:
    state: absent
    id: nginx_http_check
    service_id: "{{ nginx_service.ID }}"
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.general.plugins.module_utils.consul import (
    AUTH_ARGUMENTS_SPEC,
    OPERATION_CREATE,
    OPERATION_UPDATE,
    OPERATION_DELETE,
    OPERATION_READ,
    _ConsulModule,
    validate_check,
)

_ARGUMENT_SPEC = {
    "state": dict(default="present", choices=["present", "absent"]),
    "name": dict(type='str'),
    "id": dict(type='str'),
    "interval": dict(type='str'),
    "notes": dict(type='str'),
    "args": dict(type='list', elements='str'),
    "http": dict(type='str'),
    "tcp": dict(type='str'),
    "ttl": dict(type='str'),
    "timeout": dict(type='str'),
    "service_id": dict(type='str'),
}

_MUTUALLY_EXCLUSIVE = [
    ('args', 'ttl', 'tcp', 'http'),
]

_REQUIRED_IF = [
    ('state', 'present', ['name']),
    ('state', 'absent', ('id', 'name'), True),
]

_REQUIRED_BY = {
    'args': 'interval',
    'http': 'interval',
    'tcp': 'interval',
}

_ARGUMENT_SPEC.update(AUTH_ARGUMENTS_SPEC)


class ConsulAgentCheckModule(_ConsulModule):
    api_endpoint = "agent/check"
    result_key = "check"
    unique_identifier = "id"

    def endpoint_url(self, operation, identifier=None):
        if operation == OPERATION_READ:
            return 'agent/checks'
        if operation in [OPERATION_CREATE, OPERATION_UPDATE]:
            return "/".join([self.api_endpoint, "register"])
        if operation == OPERATION_DELETE:
            return "/".join([self.api_endpoint, "deregister", identifier])

        return super(ConsulAgentCheckModule, self).endpoint_url(operation, identifier)

    def read_object(self):
        url = self.endpoint_url(OPERATION_READ)
        checks = self.get(url)
        unique_identifiers = [self.unique_identifier, "name"]
        for identifier in unique_identifiers:
            if self.params.get(identifier) in checks:
                return checks[self.params.get(self.unique_identifier)]
            else:
                return None

    def prepare_object(self, existing, obj):
        existing = super(ConsulAgentCheckModule, self).prepare_object(existing, obj)

        operational_attributes = {"Node", "CheckID", "Output", "ServiceName", "ServiceTags",
                                  "Status", "Type", "ExposedPort", "Definition"}
        existing = {
            k: v for k, v in existing.items() if k not in operational_attributes
        }

        validate_check(existing)

        if 'Args' in existing and existing['Args']:
            existing['Args'] = ["sh", "-c", existing['Args']]

        return existing

    def create_object(self, obj):
        super(ConsulAgentCheckModule, self).create_object(obj)
        if self._module.check_mode:
            return obj
        else:
            return self.read_object()

    def update_object(self, existing, obj):
        super(ConsulAgentCheckModule, self).update_object(existing, obj)
        if self._module.check_mode:
            return obj
        else:
            return self.read_object()

    def delete_object(self, obj):
        if not self._module.check_mode:
            url = self.endpoint_url(
                OPERATION_DELETE, obj.get("CheckID")
            )
            self.put(url)
        return {}


def main():
    module = AnsibleModule(
        _ARGUMENT_SPEC,
        mutually_exclusive=_MUTUALLY_EXCLUSIVE,
        required_if=_REQUIRED_IF,
        required_by=_REQUIRED_BY,
        supports_check_mode=True,
    )

    consul_module = ConsulAgentCheckModule(module)
    consul_module.execute()


if __name__ == "__main__":
    main()
