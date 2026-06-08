"""Locust load test for CodeGuardian API."""

from locust import HttpUser, task, between


class CodeGuardianUser(HttpUser):
    wait_time = between(3, 10)

    @task(3)
    def trigger_review(self):
        self.client.post(
            "/v1/reviews",
            json={
                "repo_url": "https://github.com/psf/requests.git",
                "branch": "main",
                "scope": "full",
            },
            headers={"Authorization": "Bearer cg_test_key"},
        )

    @task(1)
    def health_check(self):
        self.client.get("/v1/health")

    @task(1)
    def get_results(self):
        self.client.get(
            "/v1/reviews/some-id",
            headers={"Authorization": "Bearer cg_test_key"},
        )
