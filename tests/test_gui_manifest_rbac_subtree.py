from structures.resources.manifest.generator import build_release_manifest


def test_manifest_navigation_contains_rbac_subtree_items() -> None:
    manifest = build_release_manifest()
    children = manifest["navigation"]["children"]
    kinds = {item["kind"] for item in children}
    table_kinds = {item["kind"] for item in manifest["tables"]}
    resource_kinds = {item["kind"] for item in manifest["resources"]}

    assert "User" in kinds
    assert "Role" in kinds
    assert "RoleBinding" in kinds
    assert "User" in table_kinds
    assert "Role" in table_kinds
    assert "RoleBinding" in table_kinds
    assert "User" in resource_kinds
