from locust import HttpUser, task, constant

class HealthFloodUser(HttpUser):
    """
    Very aggressive user model that only calls /health,
    with no think time between requests.
    """
    # No delay between tasks → max pressure
    wait_time = constant(0)

    @task
    def hit_health(self):
        # Single, hot endpoint: /health
        self.client.get("/health", name="GET /health")
