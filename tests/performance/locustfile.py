import random

from locust import HttpUser, between, task


class CostOptimizerUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Set up test data."""
        self.prompts = [
            "What is Python?",
            "Explain quantum computing",
            "Write a function to calculate fibonacci",
            "Design a microservices architecture",
        ]

    @task(3)
    def complete_simple_prompt(self):
        """Test simple prompt completion (60% of load)."""
        self.client.post(
            "/v1/complete", json={"prompt": random.choice(self.prompts[:2]), "max_tokens": 200}
        )

    @task(2)
    def complete_medium_complexity_prompt(self):
        """Test medium complexity prompts (30% of load).

        Note: Prompt "Write a function..." contains keyword "function"
        which auto-classifies as complex by the router's complexity analyzer.
        """
        self.client.post("/v1/complete", json={"prompt": self.prompts[2], "max_tokens": 500})

    @task(1)
    def complete_complex_prompt(self):
        """Test complex prompts (10% of load)."""
        self.client.post("/v1/complete", json={"prompt": self.prompts[3], "max_tokens": 1000})

    @task(1)
    def get_providers(self):
        """Test listing providers."""
        self.client.get("/v1/providers")

    @task(1)
    def get_usage_stats(self):
        """Test usage statistics."""
        self.client.get("/v1/usage")
