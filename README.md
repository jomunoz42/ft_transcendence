

# ft_transcendence

## Description

TODO: Add the final project name, concept, goal, and key features.

ft_transcendence must be a web application with a frontend, backend, database, secure user management, multi-user support, Privacy Policy and Terms of Service pages, and at least 14 validated module points.

## Project Management

TODO: Describe how the team organizes work, distributes tasks, reviews code, communicates, and tracks blockers.

## Technical Stack

| Area | Choice | Justification |
| --- | --- | --- |
| Frontend | React + Vite + TypeScript | Component-based frontend with fast local development. |
| Backend | Python + FastAPI | Lightweight API framework with WebSocket support. |
| Database | PostgreSQL | Relational database for users, profiles, social data, and application state. |
| Styling solution | TODO | TODO |
| Deployment | Docker Compose | Runs the application services through a single development stack. |

## Database Schema

TODO: Add a visual representation or clear text description of the database schema, including tables/collections, key fields, data types, and relations.

## Features List

| Feature | Description | Contributor(s) |
| --- | --- | --- |
| TODO | TODO | TODO |

## Modules

Major modules count as 2 points. Minor modules count as 1 point. The project must reach at least 14 validated module points.

| Module | Type | Points | Justification | Implementation | Contributor(s) |
| --- | --- | ---: | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | TODO |

Total planned points: TODO

## Individual Contributions

| Member | Contributions | Challenges and Solutions |
| --- | --- | --- |
| jomunoz | TODO | TODO |

## Instructions

### Prerequisites

- Docker with Docker Compose
- Make

### Environment

Create the local environment file from the committed template:

```bash
cp .env.example .env
```

Fill in the local values in `.env`. This file contains local configuration and secrets and must remain ignored by Git.

### Run

Build and start the complete application:

```bash
make up
```

The development services are exposed at:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`

To stop the application:

```bash
make down
```

Useful development commands:

```bash
make logs
make status
make test
make migrate
```

## Resources

TODO: Add documentation, articles, tutorials, and references used by the team.

### AI Usage

TODO: Explain which AI tools were used, for which tasks, and which parts of the project were AI-assisted.

## Notes

The subject and correction sheet PDFs are kept in the repository root for reference.

