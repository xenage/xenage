from __future__ import annotations

from argparse import Namespace

from structures.resources.membership import GuiClusterSnapshot, GuiEventPage, GroupState

from .context import CommandContext
from .manifest import ManifestParser
from .output import Table, first_endpoint, render_json, render_table, render_yaml


class CliCommand:
    def run(self, args: Namespace, context: CommandContext) -> int:
        raise NotImplementedError


class GetCommand(CliCommand):
    def run(self, args: Namespace, context: CommandContext) -> int:
        resource = str(args.resource)
        output = str(args.output)
        if resource == "nodes":
            snapshot = context.client.fetch_cluster_snapshot()
            self._print_snapshot(snapshot, output)
            return 0
        if resource == "events":
            page = context.client.fetch_cluster_events(limit=int(args.limit))
            self._print_events(page, output)
            return 0
        if resource == "state":
            state = context.client.fetch_current_state()
            self._print_state(state, output)
            return 0
        if resource == "group-config":
            state = context.client.fetch_current_state()
            self._print_group_config(state, output)
            return 0
        if resource in {"serviceaccounts", "roles", "rolebindings"}:
            values = context.client.fetch_resources(resource, namespace=str(args.namespace))
            self._print_resources(values, output)
            return 0
        raise RuntimeError(f"unsupported resource: {resource}")

    def _print_snapshot(self, snapshot: GuiClusterSnapshot, output: str) -> None:
        if output == "json":
            print(render_json(snapshot))
            return
        if output == "yaml":
            print(render_yaml(snapshot), end="")
            return
        rows: list[list[str]] = []
        index = 0
        while index < len(snapshot.nodes):
            node = snapshot.nodes[index]
            status = node.status
            if node.leader:
                status = f"{status} (leader)"
            rows.append([node.node_id, node.role, status, first_endpoint(node.endpoints)])
            index += 1
        print(render_table(Table(headers=["NODE", "ROLE", "STATUS", "ENDPOINT"], rows=rows)), end="")

    def _print_events(self, page: GuiEventPage, output: str) -> None:
        if output == "json":
            print(render_json(page))
            return
        if output == "yaml":
            print(render_yaml(page), end="")
            return
        rows: list[list[str]] = []
        index = 0
        while index < len(page.items):
            item = page.items[index]
            rows.append([str(item.sequence), item.happened_at, item.action, item.actor_id])
            index += 1
        print(render_table(Table(headers=["SEQ", "TIMESTAMP", "ACTION", "ACTOR"], rows=rows)), end="")

    def _print_state(self, state: GroupState, output: str) -> None:
        if output == "yaml":
            print(render_yaml(state), end="")
            return
        print(render_json(state))

    def _print_group_config(self, state: GroupState, output: str) -> None:
        if output == "json":
            print(render_json(state))
            return
        print(render_yaml(state), end="")

    def _print_resources(self, resources: list[dict[str, object]], output: str) -> None:
        if output == "json":
            print(render_json(resources))
            return
        if output == "yaml":
            print(render_yaml(resources), end="")
            return
        rows: list[list[str]] = []
        index = 0
        while index < len(resources):
            item = resources[index]
            metadata = item.get("metadata")
            name = ""
            namespace = ""
            if isinstance(metadata, dict):
                raw_name = metadata.get("name", "")
                raw_namespace = metadata.get("namespace", "default")
                name = str(raw_name)
                namespace = str(raw_namespace)
            rows.append([str(item.get("kind", "")), namespace, name])
            index += 1
        print(render_table(Table(headers=["KIND", "NAMESPACE", "NAME"], rows=rows)), end="")


class ApplyCommand(CliCommand):
    def __init__(self) -> None:
        self.parser = ManifestParser()

    def run(self, args: Namespace, context: CommandContext) -> int:
        docs = self.parser.parse_file(str(args.filename))
        results: list[dict[str, object]] = []
        index = 0
        while index < len(docs):
            results.append(context.client.apply_manifest(docs[index]))
            index += 1

        output = str(args.output)
        if output == "json":
            print(render_json(results))
            return 0
        if output == "yaml":
            print(render_yaml(results), end="")
            return 0

        rows: list[list[str]] = []
        row_index = 0
        while row_index < len(results):
            item = results[row_index]
            rows.append([
                str(item.get("kind", "")),
                str(item.get("namespace", "default")),
                str(item.get("name", "")),
                str(item.get("status", "applied")),
            ])
            row_index += 1
        print(render_table(Table(headers=["KIND", "NAMESPACE", "NAME", "STATUS"], rows=rows)), end="")
        return 0


class CanICommand(CliCommand):
    def run(self, args: Namespace, context: CommandContext) -> int:
        result = context.client.can_i(
            verb=str(args.verb),
            resource=str(args.resource),
            namespace=str(args.namespace),
        )
        allowed = bool(result.get("allowed", False))
        print("yes" if allowed else "no")
        return 0
