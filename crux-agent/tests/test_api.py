"""
Basic API tests for Crux Agent.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    with TestClient(app) as client:
        yield client


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "version" in data


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert "timestamp" in data


def test_basic_solve_validation(client):
    """Test basic solve endpoint validation."""
    # Missing question
    response = client.post("/api/v1/solve/basic", json={})
    assert response.status_code == 422
    
    # Empty question
    response = client.post("/api/v1/solve/basic", json={"question": ""})
    assert response.status_code == 422
    
    # Valid request (would fail without proper API keys)
    response = client.post("/api/v1/solve/basic", json={"question": "What is 2+2?"})
    # Should be 500 if no API keys configured, or 200 if they are
    assert response.status_code in [200, 500]


def test_enhanced_solve_validation(client):
    """Test enhanced solve endpoint validation."""
    # Valid request with suggested specializations
    response = client.post(
        "/api/v1/solve/enhanced",
        json={
            "question": "Test question", 
            "suggested_specializations": ["symbolic integration", "calculus"],
            "professor_max_iters": 3,
            "specialist_max_iters": 2
        }
    )
    # Should be 500 if no API keys configured, or 200 if they are
    assert response.status_code in [200, 500]
    
    # Valid request without suggested specializations (Professor decides dynamically)
    response = client.post(
        "/api/v1/solve/enhanced",
        json={"question": "Test question"}
    )
    # Should be 500 if no API keys configured, or 200 if they are
    assert response.status_code in [200, 500]


def test_job_not_found(client):
    """Test job status for non-existent job."""
    response = client.get("/api/v1/jobs/non-existent-job-id")
    # Would be 404 if Redis is running, 500 otherwise
    assert response.status_code in [404, 500] 