import json
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_create_agent_endpoint(client):
    """Test the create-agent endpoint."""
    # Test data
    test_data = {
        'name': 'Test Agent',
        'description': 'This is a test agent',
        'apiKey': 'test-api-key'
    }
    
    # Make the POST request
    response = client.post(
        '/api/create-agent',
        data=json.dumps(test_data),
        content_type='application/json'
    )
    
    # Assert response status code and data
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'Test Agent' in data['message']
    assert 'agent_id' in data