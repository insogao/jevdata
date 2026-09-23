# FORMAT_SPEC

## Canonical sample format
One YAML file per 1-to-1 conversation.

The YAML header is hidden metadata. The final `conversation: |-` field is the only model-visible text.

## Export rule

```python
sample = yaml.safe_load(...)
input_text = sample["conversation"]
target = sample["labels"]["risk"]
```

Never place `labels`, `hidden_case`, `source`, `generation_signature`, or lineage metadata into the model prompt.

## Long-conversation requirements
- 1-to-1 A/B dialogue.
- May span multiple days.
- Normal side topics must be interleaved, not appended as a single padding block.
- Risk evidence may be distributed across early/middle/late positions.
- System events such as transfers appear inline in human-readable form.
- A single case must not repeat an identical side-topic template.
- Hard negatives must contain superficially suspicious features while retaining decisive benign context.

## ID rules
Every case has stable `case_id`, `family_id`, `lineage_id`, and `archetype_id`.
