# Using Couchbase as a Vector Database with Solace Agent Mesh

This tutorial guides you through the process of integrating Couchbase as the vector store for your Solace agent mesh.

## Prerequisites
- Couchbase Server 7.2+ with Search Service enabled.
- Solace Agent Mesh SDK.

## Setup
1. **Initialize Bucket**: Create a bucket named `agent-vectors`.
2. **Configure SAM**: Update your `.env` file with Couchbase credentials.
3. **Index Definition**: Define a Vector Search index on the bucket.

## Implementation
```python
from solace_agent_mesh import AgentMesh
from solace_agent_mesh.vector_stores import CouchbaseStore

store = CouchbaseStore(url="couchbase://localhost", bucket="agent-vectors")
mesh = AgentMesh(vector_store=store)
```
