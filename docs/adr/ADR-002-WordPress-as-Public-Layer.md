# ADR-002: WordPress as Public Layer

Status: Proposed

Context
- Need a simple public CMS and publishing interface for marketing and release notes.

Decision
- Use WordPress as the public presentation and publishing layer. All automated posts default to draft for editorial review.

Consequences
- All public content pipelines must push to WordPress; QUAD OS remains private.

Alternatives Considered
- Static site generator — considered, but WordPress provides easier editorial workflow.

Future Evolution
- Consider headless CMS or static export for performance when needed.

---

**See also:** [QUAD_OS_MASTER_ARCHITECTURE.md](../QUAD_OS_MASTER_ARCHITECTURE.md) §2 (Public vs. private boundaries) | [WORDPRESS_PUBLIC_LAYER.md](../WORDPRESS_PUBLIC_LAYER.md)
