# Feedback Examples for Labs

## Binary Qualitative Metric (Soft Skills)

### False Negative — Metric scored FALSE but should be TRUE

```json
{
  "metric_id": 120069,
  "vote": "disagree",
  "feedback": "Metric failed at 02:15 because the agent asked 'Can I get your postcode and first line of address?' which the metric flagged as two questions. However, these are related data points for address verification — a data cluster, not question stacking. The spirit of the one-question rule is to prevent cognitive overload, and asking for two parts of an address in one turn is natural and efficient. Should be TRUE."
}
```

### False Positive — Metric scored TRUE but should be FALSE

```json
{
  "metric_id": 120069,
  "vote": "disagree",
  "feedback": "Metric passed this call but at 03:42 the agent said 'I'm running an internal process to check your account'. This exposes system internals in a way that should be flagged by the hard guardrails. 'Internal process' is functionally equivalent to the banned terms like 'system action'. Should be FALSE."
}
```

## Workflow Adherence Metric (Flow Compliance)

### Over-strict Evaluation

```json
{
  "metric_id": 120072,
  "vote": "disagree",
  "feedback": "The metric failed because the agent didn't explicitly say 'Let me confirm your booking' before creating the appointment. However, at 04:15 the agent said 'So that's Tuesday at 2pm for a boiler service at 123 High St — shall I go ahead and book that in?' which is functionally a confirmation, just phrased differently. The spirit of the confirmation step is to ensure the caller agrees before booking, which the agent achieved. Should be TRUE."
}
```

### Missed Violation

```json
{
  "metric_id": 120072,
  "vote": "disagree",
  "feedback": "Metric passed but the agent skipped the pricing step entirely. At no point between 02:00-05:30 did the agent quote a price or use the pricing tool. The booking was created without the caller knowing the cost. This is a clear workflow violation — the booking instructions require pricing before confirmation. Should be FALSE."
}
```

## Enum Classification Metric

### Wrong Classification

```json
{
  "metric_id": 120070,
  "vote": "disagree",
  "feedback": "Metric classified as 'new_customer' but the caller said 'I called last week about the same issue' at 00:45 and 'you should have my details on file' at 01:10. These are clear signals of an existing customer. The agent didn't ask the classification question but should have picked up on these signals. Correct classification: 'existing_customer'."
}
```

## Pattern Recognition Across Feedback

After leaving multiple feedback instances, look for patterns:

- **Consistently too strict on X**: The metric is taking a rule too literally
  → Labs should add safeguarding examples for this rule

- **Missing context about Y**: The metric doesn't consider a relevant factor
  → Labs should add evaluation criteria for this factor

- **Inconsistent on Z**: The metric sometimes catches it, sometimes doesn't
  → Labs should add clearer criteria with examples for this scenario

- **Wrong threshold on W**: The metric's bar is too high/low
  → Labs should adjust the severity calibration
