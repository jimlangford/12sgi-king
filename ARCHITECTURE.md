# ARCHITECTURE.md — govOS v2 additions

## govOS v2 Module Registry (placeholders)

The following modules are planned for govOS v2. This registry is a living document — each module should declare its API surface, health checks, and deployment footprint.

- govOS (core app)
- Tenant Assistant
- Civic Signal
- Element LOTUS
- Transparency Engine
- AI Services
- Public API
- Authentication
- Document Generator

Module guidance
- Each module must register a health check with services/health and expose a /ready endpoint where applicable.
- Do not hard-code internal hostnames; read from environment.
