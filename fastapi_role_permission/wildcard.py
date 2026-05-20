from __future__ import annotations


class WildcardPermission:
    """
    Supports wildcard permission patterns like:
      posts.*        matches posts.read, posts.write, posts.delete
      *.read         matches posts.read, articles.read
      *              matches everything
      posts.read     exact match
    """

    WILDCARD = "*"
    PART_DELIMITER = "."

    @staticmethod
    def build_index(permission_names: list[str]) -> dict:
        """Build a nested-dict index from a list of permission name strings."""
        index: dict = {}
        for name in permission_names:
            parts = name.split(WildcardPermission.PART_DELIMITER)
            node = index
            for part in parts:
                if part not in node:
                    node[part] = {}
                node = node[part]
            node[""] = {}  # terminal marker
        return index

    @staticmethod
    def implies(permission: str, index: dict) -> bool:
        """Check if the index of granted permissions implies the given permission."""
        parts = permission.split(WildcardPermission.PART_DELIMITER)
        return WildcardPermission._matches(parts, 0, index)

    @staticmethod
    def _matches(parts: list[str], depth: int, node: dict) -> bool:
        if not node:
            return False

        # Wildcard at this level matches everything below
        if WildcardPermission.WILDCARD in node:
            sub = node[WildcardPermission.WILDCARD]
            # * at a node means all remaining parts are implicitly granted
            if not sub or "" in sub:
                return True
            if depth + 1 < len(parts):
                return WildcardPermission._matches(parts, depth + 1, sub)
            return "" in sub

        if depth >= len(parts):
            return "" in node

        part = parts[depth]
        matched = False

        # Exact match at this level
        if part in node:
            sub = node[part]
            if depth + 1 == len(parts):
                matched = "" in sub
            else:
                matched = WildcardPermission._matches(parts, depth + 1, sub)

        # Wildcard match at this level
        if not matched and WildcardPermission.WILDCARD in node:
            sub = node[WildcardPermission.WILDCARD]
            if not sub or "" in sub:
                matched = True
            elif depth + 1 < len(parts):
                matched = WildcardPermission._matches(parts, depth + 1, sub)

        return matched

    @staticmethod
    def check(permission: str, granted_permissions: list[str]) -> bool:
        """Check if a permission is granted by the list of granted permissions (with wildcard support)."""
        index = WildcardPermission.build_index(granted_permissions)
        return WildcardPermission.implies(permission, index)
