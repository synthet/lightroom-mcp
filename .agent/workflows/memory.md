---
description: Manage knowledge graph (add/query entities)
---

# Knowledge Graph Management

This workflow helps you interact with the Memory MCP knowledge graph.

## Add Knowledge

To add new information to the graph:

1.  **Identify Entities**: Determine the key entities (e.g., "Project X", "Person Y") and their types.
2.  **Create Entities**: Use `create_entities` to add them.
    - Example: `create_entities(entities=[{"name": "Project X", "entityType": "Project", "observations": ["Important"]}])`
3.  **Link Entities**: Use `create_relations` to define relationships.
    - Example: `create_relations(relations=[{"from": "Person Y", "to": "Project X", "relationType": "leads"}])`

## Query Knowledge

To retrieve information:

1.  **Search**: Use `search_nodes(query="...")` to find relevant entities.
2.  **Explore**: Use `open_nodes(names=["..."])` to get detailed connections.
3.  **Read All**: Use `read_graph()` to see the entire graph structure (use with caution for large graphs).
