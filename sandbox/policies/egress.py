#!/usr/bin/env python3
"""
egress.py --- default-deny network egress policy with an explicit allowlist

Contains:
    EgressPolicy: network egress allowlist for sandboxes
    EgressPolicy.load(): loads the allowlist from YAML
    EgressPolicy.allows(): decides whether a host is permitted
    EgressPolicy.render_nft_rules(): renders the nftables ruleset
    EgressPolicy.validate(): checks for authoring mistakes
    EgressPolicy.describe(): one-line policy summary
"""

import yaml
from dataclasses import dataclass
from pathlib import Path

EGRESS_NETWORK = "shipwright-egress"

@dataclass(frozen=True)
class EgressPolicy:
    """Network egress allowlist enforced on sandbox containers.

    Attributes:
        allowed_hosts: Domains the sandbox may connect to.
    """

    allowed_hosts: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> "EgressPolicy":
        """Loads the allowlist from a YAML policy file.

        Args:
            path: YAML file with an "allowed" list of domains.

        Returns:
            policy: Parsed egress policy.
        """
        data = yaml.safe_load(path.read_text())
        return cls(allowed_hosts=tuple(data.get("allowed", [])))

    def allows(self, host: str) -> bool:
        """Decides whether outbound traffic to a host is permitted.

        Args:
            host: Domain the sandbox wants to reach.

        Returns:
            allowed: True only for allowlisted domains.
        """
        if host in self.allowed_hosts:
            return True
        return any(host.endswith(f".{allowed}") for allowed in self.allowed_hosts)

    def network_name(self) -> str:
        """Names the docker network sandboxes attach to.

        Returns:
            network: Dedicated egress-controlled docker network.
        """
        return EGRESS_NETWORK

    def render_nft_rules(self) -> str:
        """Renders an nftables ruleset implementing the allowlist.

        Returns:
            ruleset: Default-drop ruleset with per-host accept rules.
        """
        lines = ["table inet shipwright {", "  chain egress {", "    policy drop;"]
        for host in self.allowed_hosts:
            lines.append(f"    ip daddr {host} tcp dport 443 accept;")
        lines.append("  }")
        lines.append("}")
        return "\n".join(lines)

    def validate(self) -> list[str]:
        """Checks the policy for common authoring mistakes.

        Returns:
            problems: One entry per issue found; empty means valid.
        """
        problems = []
        if not self.allowed_hosts:
            problems.append("allowlist is empty; sandbox will have no network access")
        seen: set[str] = set()
        for host in self.allowed_hosts:
            if host in seen:
                problems.append(f"duplicate entry: {host}")
            if " " in host:
                problems.append(f"invalid host with whitespace: {host!r}")
            seen.add(host)
        return problems

    def describe(self) -> str:
        """Renders the policy as a one-line summary for audit records.

        Returns:
            summary: Host count and network name in one line.
        """
        return f"{len(self.allowed_hosts)} hosts allowed via {EGRESS_NETWORK}"
