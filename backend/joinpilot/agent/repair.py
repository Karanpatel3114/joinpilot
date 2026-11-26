"""Repair views whose checks show duplicated or lost rows.

Only structural failures are repaired: row counts, duplicate fact keys and money
totals that do not reconcile. Each join whose target is not unique is either
filtered to one row per key, when the target has a small code column that every key
fills (such as a language), or removed from the view. Orphan and null keys describe
the data, not the SQL, so they are reported but never "repaired".
"""

from __future__ import annotations

from dataclasses import replace

from joinpilot.config import JoinSettings
from joinpilot.profiling.models import ProjectProfile
from joinpilot.sqlgen.views import ApprovedJoin, ViewSpec

STRUCTURAL = frozenset({"row_count", "fan_out", "reconciliation"})


def discriminator(
    table: str, column: str, profile: ProjectProfile, settings: JoinSettings
) -> tuple[str, list[str]] | None:
    """A code column that, with `column`, keys `table` and has every value for each key."""
    target = next((t for t in profile.tables if t.name == table), None)
    if target is None:
        return None
    columns = {c.name: c for c in target.columns}
    for key in target.candidate_keys:
        if len(key) != 2 or column not in key:
            continue
        other = columns[key[1] if key[0] == column else key[0]]
        is_code = other.type == "VARCHAR" and not other.digits_only
        known = other.distinct_count <= len(other.sample_values)
        if is_code and known and 2 <= other.distinct_count <= settings.discriminator_max_distinct:
            return other.name, other.sample_values
    return None


def unique_target(join: ApprovedJoin, profile: ProjectProfile, unique_min: float) -> bool:
    """True when the join's target column is unique, or a filter already makes it so."""
    if join.filter_column:
        return True
    for key in profile.keys:
        if key.table == join.to_table and key.columns == [join.to_column]:
            return key.uniqueness >= unique_min
    return False


def connected(fact: str, joins: list[ApprovedJoin]) -> list[ApprovedJoin]:
    """Keep only joins still reachable from the fact after some were removed."""
    reached, kept, changed = {fact}, [], True
    remaining = list(joins)
    while changed:
        changed = False
        for join in list(remaining):
            anchor = join.to_table if join.is_attribute else join.from_table
            if anchor in reached:
                reached.add(join.from_table if join.is_attribute else join.to_table)
                kept.append(join)
                remaining.remove(join)
                changed = True
    return [j for j in joins if j in kept]


def repair_spec(
    spec: ViewSpec, profile: ProjectProfile, settings: JoinSettings
) -> tuple[ViewSpec, list[str]]:
    """Fix every join that multiplies rows; return the new spec and what was done."""
    joins, notes = [], []
    for join in spec.joins:
        if join.is_attribute or unique_target(join, profile, settings.unique_min):
            joins.append(join)
            continue
        found = discriminator(join.to_table, join.to_column, profile, settings)
        if found:
            column, choices = found
            preferred = [v for v in settings.preferred_filter_values if v in choices]
            value = preferred[0] if preferred else choices[0]
            joins.append(replace(join, filter_column=column, filter_value=value, filter_on="to"))
            notes.append(
                f"{spec.name}: join {join.edge_id} now keeps only {join.to_table}.{column} = "
                f"'{value}', so each row matches one {join.to_table} row."
            )
        else:
            notes.append(
                f"{spec.name}: join {join.edge_id} to {join.to_table} was removed because "
                f"{join.to_table}.{join.to_column} is not unique and duplicated rows."
            )
    return replace(spec, joins=connected(spec.fact, joins)), notes
