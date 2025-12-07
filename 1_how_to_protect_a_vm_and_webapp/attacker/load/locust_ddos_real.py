import os
import random
from locust import HttpUser, task, between, constant

DEMO_USER = os.getenv("DEMO_USERNAME", "demo")
DEMO_PASS = os.getenv("DEMO_PASSWORD", "changeme")


class NormalUser(HttpUser):
    """
    Normal user that:
      - logs in (80% of the time) and uses session cookies
      - otherwise uses HTTP Basic Auth
      - hits all business endpoints: /add (GET+POST), /io, /compute, /health
    """
    wait_time = between(0.5, 2.0)   # human-like think time
    weight = 1                      # relative proportion vs AttackerUser

    def on_start(self):
        # Decide if this user uses session or basic auth
        self.use_session = random.random() < 0.8
        if self.use_session:
            with self.client.post(
                "/login",
                json={"username": DEMO_USER, "password": DEMO_PASS},
                name="POST /login",
                catch_response=True,
            ) as resp:
                if resp.status_code != 200:
                    resp.failure(f"Login failed: {resp.status_code} {resp.text}")

    def on_stop(self):
        if self.use_session:
            self.client.post("/logout", name="POST /logout")

    def _auth(self):
        """
        Helper: return auth tuple for Basic Auth when not using session.
        """
        if self.use_session:
            return None
        return (DEMO_USER, DEMO_PASS)

    # ---- Core behavior tasks ----

    @task(3)
    def read_sum(self):
        """
        Read current sum with GET /add
        """
        with self.client.get(
            "/add",
            name="GET /add",
            auth=self._auth(),
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"GET /add failed: {resp.status_code} {resp.text}")
            else:
                # basic sanity check
                if "sum" not in resp.json():
                    resp.failure("Missing 'sum' in GET /add response")

    @task(1)
    def add_random(self):
        """
        Update sum with POST /add (small random int, including negatives).
        """
        value = random.randint(-3, 12)
        with self.client.post(
            "/add",
            json={"value": value},
            name="POST /add",
            auth=self._auth(),
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"POST /add failed: {resp.status_code} {resp.text}")
            else:
                if "sum" not in resp.json():
                    resp.failure("Missing 'sum' in POST /add response")

    @task(2)
    def simulate_io_task(self):
        """
        Hit I/O-bound endpoint /io (requires auth).
        """
        with self.client.get(
            "/io",
            name="GET /io",
            auth=self._auth(),
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"/io failed: {resp.status_code} {resp.text}")

    @task(2)
    def simulate_compute_task(self):
        """
        Hit CPU-bound endpoint /compute (requires auth).
        """
        with self.client.get(
            "/compute",
            name="GET /compute",
            auth=self._auth(),
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"/compute failed: {resp.status_code} {resp.text}")

    @task(1)
    def health_check(self):
        """
        Normal users occasionally hit /health (e.g., frontends or internal checks).
        No auth required.
        """
        self.client.get("/health", name="GET /health (normal)")


class AttackerUser(HttpUser):
    """
    Attacker model:
      - zero or near-zero think time
      - floods /health (cheap endpoint)
      - and /login (to stress auth / DB / rate limiting)
    """
    wait_time = constant(0)   # relentless flood
    weight = 1000             # fewer attacker users than normal ones (but each is very aggressive)

    @task(4)
    def flood_health(self):
        """
        DDoS-style hammering of /health.
        """
        self.client.get("/health", name="GET /health (attacker)")

    @task(1)
    def flood_login(self):
        """
        Aggressive /login calls.
        Here: mix of correct and incorrect creds to simulate brute-force / abuse.
        """
        # 30%: valid creds, 70%: bad password
        if random.random() < 0.3:
            username = DEMO_USER
            password = DEMO_PASS
        else:
            username = DEMO_USER
            password = "wrong-" + str(random.randint(0, 999999))

        self.client.post(
            "/login",
            json={"username": username, "password": password},
            name="POST /login (attacker)",
        )
