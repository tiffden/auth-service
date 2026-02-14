# data-model-notes-week 4

Below is a concrete, interview-grade target model for a learning platform that needs to scale, stay auditable, and evolve without breaking clients. I’m going to give you:

 1. a canonical ER model (entities + keys + relationships)
 2. a set of sequence diagrams for the critical API flows
 3. schema evolution / versioning rules that keep you out of migration hell

⸻

## Data model: the “spine” (what everything hangs off)

Design principles (the abstractions you want in your head)
 • Separate “content definitions” from “attempts/results.”
Courses/assessments are mostly authored data; progress is user-generated data at high volume.
 • Treat progress as an event stream + a projection.
Events are the source of truth (auditability); projections make reads fast.
 • Credentials are claims.
They reference the evidence (attempts, rubric decisions, completions) and can be revoked/versioned.

⸻

## ER diagram (logical)

Use this as your Week 4 deliverable “ER.” It’s intentionally normalized where it matters (authorship, attempts, credentials) and denormalized where it’s safe (projections).

Entities (core)

User profiles
 • users
 • id (PK)
 • email (unique)
 • created_at, status
 • user_profile
 • user_id (PK/FK -> users.id)
 • display_name, locale, timezone, metadata_json
 • user_role
 • user_id (FK)
 • role (enum: learner|instructor|admin)
 • PK(user_id, role)

Courses / pathways
 • course
 • id (PK)
 • slug (unique), title, status (draft|published|retired)
 • version (int) (content version)
 • created_by, published_at
 • course_module
 • id (PK)
 • course_id (FK)
 • position (int), title
 • module_item
 • id (PK)
 • module_id (FK)
 • type (enum: lesson|assessment|external)
 • ref_id (nullable) (e.g., assessment_id if type=assessment)
 • position (int)
 • learning_pathway
 • id (PK)
 • slug (unique), title, status, version
 • pathway_course
 • pathway_id (FK)
 • course_id (FK)
 • position (int)
 • PK(pathway_id, course_id)

Assessments (definition vs execution)
 • assessment
 • id (PK)
 • course_id (FK) (nullable if reusable across courses)
 • type (quiz|project|exam)
 • version (int) (definition version)
 • scoring_model (auto|rubric|manual)
 • assessment_item
 • id (PK)
 • assessment_id (FK)
 • kind (mcq|short|code|file|peer)
 • prompt
 • max_score
 • position

Attempts / results (high volume)
 • assessment_attempt
 • id (PK)
 • assessment_id (FK)
 • assessment_version (int) (frozen at attempt time)
 • user_id (FK)
 • status (in_progress|submitted|graded|void)
 • started_at, submitted_at, graded_at
 • attempt_no (int) (per user+assessment)
 • attempt_response
 • attempt_id (FK)
 • assessment_item_id (FK)
 • response_json
 • score (nullable)
 • PK(attempt_id, assessment_item_id)

Progress (events + projection)
 • progress_event (append-only)
 • id (PK)
 • user_id (FK)
 • course_id (FK)
 • occurred_at
 • type (enrolled|module_started|item_completed|assessment_submitted|assessment_passed|course_completed|...)
 • entity_type, entity_id (e.g., module_item)
 • payload_json (scores, time_spent, etc.)
 • idempotency_key (unique per user) (optional but highly recommended)
 • course_progress (projection / read model)
 • user_id (FK)
 • course_id (FK)
 • status (not_started|in_progress|completed)
 • percent_complete (0..100)
 • last_activity_at
 • completed_at (nullable)
 • PK(user_id, course_id)

Credentials
 • credential
 • id (PK)
 • type (certificate|badge|microcredential)
 • name, issuer
 • version (int) (credential schema version)
 • user_credential (issued instances)
 • id (PK)
 • user_id (FK)
 • credential_id (FK)
 • issued_at
 • status (issued|revoked|expired)
 • evidence_json (attempt ids, course version, rubric decision ids)
 • unique(user_id, credential_id, issued_at) (or an external claim id)

Relationship sketch (Mermaid ERD)

You can paste this into markdown if you use Mermaid:

erDiagram
  users ||--|| user_profile : has
  users ||--o{ user_role : has

  course ||--o{ course_module : contains
  course_module ||--o{ module_item : contains

  learning_pathway ||--o{ pathway_course : includes
  course ||--o{ pathway_course : included_in

  course ||--o{ assessment : may_have
  assessment ||--o{ assessment_item : defines

  users ||--o{ assessment_attempt : makes
  assessment ||--o{ assessment_attempt : attempted_as
  assessment_attempt ||--o{ attempt_response : has

  users ||--o{ progress_event : emits
  course ||--o{ progress_event : referenced_by
  users ||--o{ course_progress : has
  course ||--o{ course_progress : tracked_for

  credential ||--o{ user_credential : issued_as
  users ||--o{ user_credential : earns

⸻

## Sequence diagrams (API flows)

These are the “platform API” narratives interviewers love because they show you understand write paths, consistency, and evolution.

### Enroll in a course

sequenceDiagram
  participant C as Client
  participant API as Platform API
  participant DB as DB
  participant EVT as Event Log (progress_event)

  C->>API: POST /v1/courses/{courseId}/enroll
  API->>DB: Upsert course_progress(user, course) = in_progress
  API->>EVT: Append progress_event(type=enrolled, idempotency_key)
  API-->>C: 201 Enrolled (course_progress snapshot)

### Complete a module item (lesson, video, etc.)

sequenceDiagram
  participant C as Client
  participant API as Platform API
  participant EVT as Event Log
  participant PROJ as Progress Projector
  participant DB as Read Model DB

  C->>API: POST /v1/progress/events (item_completed)
  API->>EVT: Append progress_event (idempotent)
  EVT-->>PROJ: Stream/notify new event
  PROJ->>DB: Recompute course_progress percent/last_activity
  API-->>C: 202 Accepted (or 200 if synchronous projection)

### Assessment attempt: start → submit → grade

sequenceDiagram
  participant C as Client
  participant API as Platform API
  participant DB as DB
  participant EVT as Event Log
  participant GR as Grader

  C->>API: POST /v1/assessments/{id}/attempts (start)
  API->>DB: Create assessment_attempt(status=in_progress, version=frozen)
  API-->>C: 201 attempt_id

  C->>API: POST /v1/attempts/{attemptId}/submit
  API->>DB: Update attempt status=submitted, submitted_at
  API->>EVT: Append progress_event(type=assessment_submitted)
  API-->>C: 202 Accepted

  API->>GR: Queue grading job (auto/rubric/manual)
  GR->>DB: Write scores (attempt_response), set status=graded
  GR->>EVT: Append progress_event(type=assessment_passed/failed, payload=score)

D) Issue credential after course completion

sequenceDiagram
  participant PROJ as Progress Projector
  participant DB as DB
  participant CRED as Credential Service
  participant EVT as Event Log

  PROJ->>DB: Detect course_progress.completed_at set
  PROJ->>CRED: Evaluate eligibility (ruleset)
  CRED->>DB: Create user_credential(evidence_json)
  CRED->>EVT: Append progress_event(type=credential_issued)

⸻

## Learning pathways as structured data (what “good” looks like)

The key is: a pathway is not just a list of courses; it often has rules.

If you want the abstraction to scale, represent pathways like this:
 • Structure: ordered nodes (courses, modules, “milestones”)
 • Constraints: prerequisites, branching, optionality, completion requirements (N-of-M)

Minimal extension if you want it now:
 • Add pathway_node(id, pathway_id, kind, ref_id, position)
 • Add pathway_edge(from_node_id, to_node_id, condition_json)
(condition_json can start simple: “requires completion of X”)

This gives you room for:
 • multiple tracks (beginner → advanced)
 • electives
 • gating (must pass exam before proceeding)

⸻

## API versioning + schema evolution (rules that prevent breakage)

API versioning
 • URI major version: /v1/..., /v2/... for breaking changes.
 • Additive changes are non-breaking: adding optional fields, new enum values (careful), new endpoints.
 • Use explicit resource versions for authored content:
 • course.version, assessment.version
Attempts always store the version they were taken against.

Schema evolution patterns you’ll actually use
 • Expand/Contract for breaking changes:

 1. add new columns/tables (expand)
 2. dual-write
 3. backfill
 4. cut reads over
 5. remove old fields (contract)
 • Events are immutable:
 • never change past events; instead add a compensating event (e.g., credential_revoked)
 • Idempotency keys on write endpoints:
 • especially for progress events and issuance flows

“Enum drift” safety

If you use enums in DB, treat new values as a compatibility risk. Alternatives:
 • DB: store as text with app-level validation
 • API: document new values as “clients must ignore unknown enum values”

⸻

## Enterprise tenancy (the missing spine)

The JD says "enterprise ready." Every table above implicitly belongs to an
organization. Without tenant isolation, you can't do enterprise SSO, per-org
billing, or data residency.

Entities

 • organization
   • id (PK)
   • name, slug (unique)
   • plan (free|team|enterprise)
   • created_at, status (active|suspended)
 • org_membership
   • org_id (FK -> organization.id)
   • user_id (FK -> users.id)
   • org_role (owner|admin|instructor|learner)
   • PK(org_id, user_id)

Tenant scoping rules
 • Every query that returns user data, progress, or credentials must be
   scoped to org_id. This is the single most common security bug in
   multi-tenant SaaS.
 • Courses can be org-scoped (private) or platform-scoped (shared catalog).
   Use an org_id (nullable) FK on course: null = platform-wide.
 • SSO binds at the org level: organization stores saml_metadata_url,
   sso_provider, sso_enforced (bool).

Impact on Principal
 • The auth-service Principal grows to carry org context:
   Principal(user_id, roles, org_id, org_role)
 • API guards become: "is this user an admin *in this org*?" not just
   "is this user an admin globally?"

Mermaid addition

  organization ||--o{ org_membership : has
  users ||--o{ org_membership : belongs_to
  organization ||--o{ course : may_own

⸻

## AI interaction logs (the data AI-native education generates)

If AI is the delivery mechanism (not just the subject), the platform produces
a new category of high-volume data: the AI-learner conversation itself. This
is both audit trail and the raw material for improving the platform.

Entities

 • ai_session
   • id (PK)
   • user_id (FK)
   • module_item_id (FK, nullable)
   • session_type (tutoring|assessment_review|content_generation)
   • started_at, ended_at
 • ai_interaction (high volume, append-only)
   • id (PK)
   • session_id (FK -> ai_session.id)
   • role (user|assistant|system)
   • content_hash (text) (store content in object storage, hash here)
   • model_id (text) (e.g. "claude-sonnet-4-5-20250929")
   • input_tokens, output_tokens
   • latency_ms
   • created_at
 • ai_feedback (optional, links human signal back to interactions)
   • interaction_id (FK)
   • user_id (FK)
   • rating (thumbs_up|thumbs_down|flag)
   • comment (nullable)
   • PK(interaction_id, user_id)

Why this matters for the role
 • Cost attribution: token counts per session, per org, per course
 • Quality monitoring: feedback ratings correlated with model_id and
   session_type (→ Week 13: AI observability)
 • Safety audit: content_hash lets you reconstruct any conversation
   without storing raw PII in the hot path
 • Adaptive improvement: which tutoring sessions led to assessment_passed
   events? (join ai_session → progress_event)

Mermaid addition

  users ||--o{ ai_session : initiates
  module_item ||--o{ ai_session : context_for
  ai_session ||--o{ ai_interaction : contains
  ai_interaction ||--o{ ai_feedback : rated_by

⸻

## Credential model → Open Badges v3 mapping

The JD lists "badging standards (Open Badges)" as a strong-candidate signal.
The credential/user_credential tables map naturally to the Open Badges v3
spec (W3C Verifiable Credentials based):

 • credential → Achievement (the badge definition)
   • credential.name → achievement.name
   • credential.type → achievement.type (Badge, Certificate, etc.)
   • credential.issuer → issuer profile (organization in our model)
   • credential.version → achievement.version
 • user_credential → AchievementCredential (the issued assertion)
   • user_credential.id → credential.id (the VC identifier)
   • user_credential.user_id → credentialSubject.id
   • user_credential.issued_at → issuanceDate
   • user_credential.evidence_json → evidence[] array
   • user_credential.status → credentialStatus

To be fully OBv3 compliant, you'd add:
 • A JSON-LD @context field on user_credential (or generate it at export)
 • A verification endpoint: GET /v1/credentials/{id}/verify
 • Revocation list support (credentialStatus → RevocationList2020)

This doesn't change the relational schema — it's a serialization concern.
Store the canonical data in the relational model, export OBv3 JSON-LD on
demand via an API endpoint.

⸻

## Data store strategy (what lives where)

Not everything belongs in PostgreSQL. The model above is the relational
core, but production systems layer multiple stores. Each store is introduced
in the week where it's naturally motivated:

 • Relational DB (PostgreSQL) — Week 4 (this week)
   All entities above. The source of truth for authored content,
   user records, credentials, and the progress event log.
   Why Postgres: ACID transactions, foreign keys, JSON columns for
   semi-structured fields (payload_json, evidence_json), mature
   ecosystem.

 • Cache layer (Redis) — Week 6 (Scalable Backend Patterns)
   Session state, rate-limit counters, course_progress projections
   for hot-path reads, token blacklists.
   Why here: Week 6 covers horizontal scaling and rate limiting —
   Redis is the natural tool for both.

 • Document / object store (S3 + optional document DB) — Week 9 (LLM Integration)
   AI interaction content (full conversation text referenced by
   content_hash), prompt templates, generated content artifacts.
   Why here: Week 9 introduces the LLM pipeline — that's when you
   need to store large, variable-shaped AI outputs outside the
   relational model.

 • Vector store (pgvector or dedicated) — Week 12 (Adaptive Experience Logic)
   Embeddings of course content, learner question history, and
   assessment items for semantic similarity search (e.g., "find
   related lessons" or "match learner question to relevant module").
   Why here: Week 12 covers adaptive/personalized delivery — vector
   search is what makes "find content relevant to this learner's
   struggle" possible.

⸻

## What to actually deliver for Week 4

ER (1 page)
 • The Mermaid ERD above (including organization + ai_session additions)
 • A short legend:
   • which tables are "authored content"
   • which are "user-generated high volume"
   • which are "audit log" vs "projection"
   • which are "tenant boundary" tables

Sequence diagrams (4)
 • enroll (now org-scoped)
 • item completion event ingestion + projection
 • assessment start/submit/grade
 • credential issuance (note OBv3 export path)

Data store map (1 page)
 • Which entities live in which store
 • When each store gets introduced (Week 6, 9, 12)
 • Why not all-in-one (latency, shape of data, query patterns)

Short "evolution notes" section
 • how you version courses/assessments
 • expand/contract example
 • idempotency + event immutability
 • tenant migration strategy (adding org_id to existing tables)
