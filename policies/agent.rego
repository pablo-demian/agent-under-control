package agent.authz

import rego.v1

# Unknown or incomplete inputs are denied.
default allow := false

# Only this principal may operate on the
# designated simulated resource.
trusted_context if {
    input.principal == "sre-agent"
    input.resource == "payments-api"
    input.environment == "staging"
}

# Read-only metrics capability.
allow if {
    trusted_context
    input.capability == "metrics.read"
}

# Service restart capability.
allow if {
    trusted_context
    input.capability == "service.restart"
}

# Logging configuration is permitted only
# when audit logging is explicitly preserved.
allow if {
    trusted_context
    input.capability == "logging.configure"
    input.predicted_effects.audit_logging_enabled == true
}