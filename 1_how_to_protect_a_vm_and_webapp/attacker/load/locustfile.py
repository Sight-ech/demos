import os
import random
from locust import HttpUser, task, between, events

DEMO_USER = os.getenv("DEMO_USERNAME", "demo")
DEMO_PASS = os.getenv("DEMO_PASSWORD", "changeme")

class WebAppUser(HttpUser):
    """
    Simulates a user who:
      - logs in (session cookie)
      - alternates between reading the sum and adding a random int
      - logs out when the user stops
    """
    # Think time between requests (seconds)
    wait_time = between(0.5, 2.0)

    def on_start(self):
        # 70% session login, 30% use Basic Auth only (no login)
        self.use_session = random.random() < 0.7
        if self.use_session:
            with self.client.post(
                "/login",
                json={"username": DEMO_USER, "password": DEMO_PASS},
                name="POST /login",
                catch_response=True,
            ) as resp:
                if resp.status_code != 200:
                    resp.failure(f"Login failed: {resp.text}")

    def on_stop(self):
        if self.use_session:
            self.client.post("/logout", name="POST /logout")

    @task(3)  # weight 3 → higher frequency (priority)
    def read_sum(self):
        """
        Read the current sum (GET /add).
        If not logged in via session, send Basic Auth.
        """
        headers = {}
        auth = None
        if not self.use_session:
            auth = (DEMO_USER, DEMO_PASS)

        with self.client.get("/add", name="GET /add", auth=auth, headers=headers, catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"GET /add unauthorized or error: {resp.status_code} {resp.text}")
                return
            if "sum" not in resp.json():
                resp.failure("Response missing 'sum' key")

    @task(1)  # weight 1 → lower frequency than read_sum
    def add_random(self):
        """
        Add a random integer in [-3, 12] (POST /add).
        """
        value = random.randint(-3, 12)
        payload = {"value": value}
        auth = None
        if not self.use_session:
            auth = (DEMO_USER, DEMO_PASS)

        with self.client.post("/add", json=payload, name="POST /add", auth=auth, catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"POST /add failed: {resp.status_code} {resp.text}")
                return
            data = resp.json()
            if "sum" not in data:
                resp.failure("Response missing 'sum' after POST /add")

    @task(2)  # moderate frequency
    def simulate_io_task(self):
        """
        Hit /io endpoint — I/O-bound sleep (0.5–2 seconds).
        Good for simulating external service waits or DB latency.
        """
        auth = None
        if not self.use_session:
            auth = (DEMO_USER, DEMO_PASS)

        with self.client.get("/io", name="GET /io", auth=auth, catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"I/O simulation failed: {resp.status_code} {resp.text}")

    @task(1)  # low frequency because CPU-heavy
    def simulate_compute_task(self):
        """
        Hit /compute endpoint — CPU-bound loop.
        Good for CPU pressure testing on the backend.
        """
        auth = None
        if not self.use_session:
            auth = (DEMO_USER, DEMO_PASS)

        with self.client.get("/compute", name="GET /compute", auth=auth, catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Compute simulation failed: {resp.status_code} {resp.text}")
