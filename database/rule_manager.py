import logging

logger = logging.getLogger(__name__)


class RuleManager:
    """Dynamic safety-rule loader backed by the RULE_MASTER table.

    Rule thresholds are read from the database at runtime so the system
    never depends on hardcoded values. Unknown rules degrade gracefully.
    """

    def __init__(self, db):
        self.db = db

    def get_rules(self, status="Active"):
        return self.db.get_rules(status)

    def get_rule_by_name(self, rule_name, status="Active"):
        return self.db.get_rule_by_name(rule_name, status)

    def get_rule(self, rule_id):
        return self.db.get_rule(rule_id)

    def get_threshold(self, rule_name, status="Active"):
        rule = self.get_rule_by_name(rule_name, status)
        if not rule:
            return None
        return rule.get("threshold")

    def resolve_rule(self, violation_type):
        """Return the active rule matching a violation type, or None."""
        rule = self.get_rule_by_name(violation_type)
        if rule:
            return rule
        for candidate in self.get_rules():
            if candidate["rule_name"].lower() == violation_type.lower():
                return candidate
        return None

    def apply_config_overrides(self, config, threshold_map):
        """Override config attributes from active numeric rules in RULE_MASTER.

        `threshold_map` maps a rule name (lowercase) to a config attribute
        name. Only numeric thresholds are applied so non-numeric values
        (e.g. "Immediate") leave the existing defaults untouched.
        """
        applied = []
        for rule in self.get_rules():
            attr = threshold_map.get(rule["rule_name"].lower())
            if not attr or not hasattr(config, attr):
                continue
            raw = rule.get("threshold")
            if raw is None or not str(raw).strip().isdigit():
                continue
            setattr(config, attr, int(raw))
            applied.append((attr, raw))
        for attr, raw in applied:
            logger.info(f"RULE_MASTER override: {attr} = {raw}")
        return applied
