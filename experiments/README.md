## Experiments

### CePO (Cerebras Planning & Optimization)

Run advanced reasoning with test-time compute using Cerebras Inference and OptiLLM.

Prerequisites:

- `pip install --upgrade cerebras_cloud_sdk optillm`
- Set `CEREBRAS_API_KEY` in your environment (or `.env` in repo root)

Example:

```bash
export CEREBRAS_API_KEY=sk-... # or place in .env
python experiments/cepo_experiment.py --question "If 2x+3=11, what is x?" --verbose
```

Notes:

- Uses `--approach cepo` under the hood via OptiLLM.
- Default model is `llama3.3-70b`, which supports CePO per Cerebras docs.

References:

- CePO capability: https://inference-docs.cerebras.ai/capabilities/cepo
- OpenAI compatibility: https://inference-docs.cerebras.ai/resources/openai
