# Lightroom MCP Agent Configuration

This folder contains configuration files and settings for AI agents working with the Lightroom MCP server.

## Files

### `settings.json`
Main configuration file for agent behavior, Lightroom connection settings, workflow preferences, and safety settings.

**Key sections:**
- `agent.defaultBehavior`: Default agent behaviors (verify connection, check selection, etc.)
- `lightroom.connection`: Connection settings for the Lightroom plugin
- `lightroom.operations`: Default operation parameters
- `workflows`: Enable/disable and configure specific workflows
- `safety`: Safety settings for operations (confirmations, limits, dry-run mode)
- `logging`: Logging configuration

### `workflows.json`
Predefined workflow templates that agents can use for common tasks:
- **Photo Culling**: Automated photo culling and rating
- **Metadata Enhancement**: Batch caption and metadata updates
- **Catalog Management**: Catalog operations and organization

## Usage

Agents should read these configuration files to:
1. Understand default behaviors and preferences
2. Configure connection settings
3. Follow predefined workflows
4. Respect safety settings and confirmations

## Customization

Edit `settings.json` to customize:
- Connection timeouts and retry behavior
- Default operation parameters
- Workflow preferences
- Safety confirmation requirements
- Logging levels

## Example Agent Behavior

Based on these settings, an agent should:
1. Always verify connection with `get_studio_info()` if `verifyConnection` is true
2. Check selection with `get_selection()` before modifications if `checkSelectionBeforeModify` is true
3. Confirm batch operations if `confirmBatchOperations` is true
4. Provide feedback after operations if `provideFeedback` is true
5. Respect safety settings and require confirmations as configured
