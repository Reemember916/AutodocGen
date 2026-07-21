"""问题单台账：人工填写序号/问题/问题单编号，挂到更改单问题条目。"""

from tickets.match import apply_matched_tickets, match_report, match_tickets_to_changes
from tickets.strategy import MatchContext, get_match_strategy, run_match_strategy
from tickets.tickets import (
    Ticket,
    apply_tickets_to_changes,
    load_tickets,
    write_ticket_template,
)

__all__ = [
    "Ticket",
    "MatchContext",
    "apply_tickets_to_changes",
    "apply_matched_tickets",
    "get_match_strategy",
    "load_tickets",
    "match_report",
    "match_tickets_to_changes",
    "run_match_strategy",
    "write_ticket_template",
]
