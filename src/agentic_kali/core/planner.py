from __future__ import annotations

from agentic_kali.policy.models import Action, Scope


SAFE_RECON_ACTIONS = ("ping_check", "nmap_top_ports", "whatweb", "httpx_probe", "nuclei_safe")
INTRUSIVE_ACTIONS = ("sqlmap_safe",)
ALL_ACTIONS = (*SAFE_RECON_ACTIONS, *INTRUSIVE_ACTIONS)


def build_plan(scope: Scope) -> list[Action]:
    actions: list[Action] = []
    requested = [name for name in scope.allowed_actions if name in ALL_ACTIONS]

    for target in scope.targets:
        for name in requested:
            actions.append(Action(name=name, target=target, intrusive=name in INTRUSIVE_ACTIONS))

    return actions
