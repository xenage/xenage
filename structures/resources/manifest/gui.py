from ..base import ResourceDocument
from ..cluster import Node
from ..membership import ClusterNodeTableRow, EventLogEntry, GroupConfig, GroupConfigKeyTableRow
from ..observability import Event

RESOURCE_TYPES: tuple[type[ResourceDocument], ...] = (
    Node,
    GroupConfig,
    Event,
)

NAVIGATION = {
    "label": "Cluster",
    "children": [
        {"label": "Nodes", "kind": "Node"},
        {"label": "Group Config", "kind": "GroupConfig"},
        {"label": "Events", "kind": "Event"},
    ],
}

GUI_TABLES: tuple[dict[str, object], ...] = (
    {
        "kind": "Node",
        "title": "Nodes",
        "source": "snapshot.nodes",
        "row_type": ClusterNodeTableRow,
        "row_key": "node_id",
        "default_sort": {"field": "node_id", "direction": "asc"},
    },
    {
        "kind": "GroupConfig",
        "title": "Group Config",
        "source": "snapshot.group_config",
        "row_type": GroupConfigKeyTableRow,
        "row_key": "key",
        "default_sort": {"field": "key", "direction": "asc"},
    },
    {
        "kind": "Event",
        "title": "Events",
        "source": "events.items",
        "row_type": EventLogEntry,
        "row_key": "sequence",
        "default_sort": {"field": "sequence", "direction": "desc"},
        "page_size": 200,
    },
)
