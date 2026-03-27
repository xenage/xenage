from __future__ import annotations

from structures.resources.rbac import Role


def role_allows(role: Role, verb: str, resource: str, namespace: str) -> bool:
    rule_index = 0
    while rule_index < len(role.rules):
        rule = role.rules[rule_index]
        namespaces = rule.namespaces if rule.namespaces else ["*"]
        if _match(rule.verbs, verb) and _match(rule.resources, resource) and _match(namespaces, namespace):
            return True
        rule_index += 1
    return False


def _match(values: list[str], expected: str) -> bool:
    index = 0
    while index < len(values):
        value = values[index]
        if value == "*" or value == expected:
            return True
        index += 1
    return False
