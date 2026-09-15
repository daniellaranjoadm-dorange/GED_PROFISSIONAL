# Document 360 — Phase 1C.4A

## Baseline and scope

Official checkout: `C:/Users/daniel.laranjo/GED_PROFISSIONAL`, branch `main`,
HEAD `fc195c14bdf68e3a503dc5b0354fb3dc3fc04368`. Initial working tree clean.
No other checkout is used for this phase. No schema, migrations, production data,
importers, workflows, templates, frontend, CORS or existing endpoint contracts change.

## Endpoint

`GET /api/v1/document-center/<int:document_id>/`

Session authentication and `automacoes.visualizar`, through the existing
`document_center_read_only` decorator. Anonymous GET: JSON 401; unauthorized
GET: JSON 403. Missing/inactive/deleted document: JSON 404. No query parameters:
unknown/repeated parameters produce JSON 400. Non-GET methods reaching the view
produce JSON 405 and `Allow: GET`. Existing CSRF middleware can first reject unsafe
requests with its standard 403; it is not bypassed. All view responses carry
`Cache-Control: private, no-store`. Errors use the existing `{error: {code, message}}`.

## Read architecture

`document_360_views` -> `consultar_documento_360` -> existing
`consulta_central_documentos` plus single-document prefetches -> explicit serializer.
The central query remains authoritative for `ativo=True, deletado_em IS NULL`.
Existing page-loading/filter/metric functions are useful for collection endpoints,
but are not invoked for a detail request. No existing service was modified.

Confirmed relationships:

- Documento has nullable `projeto`, `mestre`, `etapa` FKs.
- DocumentoMestre has `revisoes` (Documento rows) and nullable `revisao_atual`.
- Files, file versions, external references, workflow history, approvals and audit
  logs use the existing reverse relations on Documento.
- `workflow_status` is an optional reverse one-to-one; its stage may be null.
- LD, PCF and transmittal records have nullable `documento_ged` FKs.
- Pending actions have a document FK, nullable LD FK and nullable responsible user.
- DocumentoKM links indirectly via a nullable LD FK; no inferred KM join is added.
- VinculoDoxManual exists in this checkout, but is identifier-based, without a
  Documento FK. It is not matched or reconciled by this endpoint.

Lifecycle, link engine, timeline PCF, transmittal and KM synchronization services
were inspected; they write records and/or process external workbooks/files. They
are not dependencies of the new read service and are never called by this endpoint.

## Contract

Top-level objects/arrays:

| Key | Source / semantics |
|---|---|
| document | Existing core serializer: revision-level Documento.pk |
| ld_records | All LD rows linked by FK, using the existing LD allowlist |
| revisions | All Documento rows with the same master, including inactive/deleted history |
| pcf_timeline | Only PCFTimeline rows already linked to this document |
| transmittals | Only TransmittalKM rows already linked to this document |
| external_references | IDs, system, external identifier/status, divergent flag and timestamps |
| workflow | Separate persisted document_stage, legacy_stage, current status row and history |
| approvals | ID, stage, user, stored status and date |
| files | ID, basename of original name, type and uploaded_at |
| versions | ID, basename, stored file revision/status, created_at and creator |
| pending_actions | All linked statuses including resolved; type, title, severity, status, responsible, LD ID and dates |
| audit_trail | Real LogAuditoria IDs, actors, actions and dates |

`document` keeps its existing keys: id, master_id, document_number, title,
revision, current_revision_id, current_revision, is_current_revision, project,
discipline, document_type and status. No project inference or LD overwrite occurs.

Nulls and blank values are retained. Missing many-valued relationships are `[]`.
Missing workflow status is `null`. Missing stage/user references are `null`.
Typed dates/timestamps use ISO 8601; source date strings in LD/PCF/transmittals
are left unchanged, not parsed or interpreted.

Revisions are not DocumentoVersao records. Historical revision metadata includes
id, document_number, revision, status, project_id, active, deleted_at, created_at,
issued_at and is_current_revision. Its current flag compares the stored master
pointer, including historical/hidden revisions. The existing core serializer in
`document` still hides an inactive/deleted/inconsistent current pointer. No pointer
is recalculated or repaired. With no master, revisions is empty.

Workflow exposes the document stage and the workflow-status stage separately so
persisted discrepancies remain visible. Deadlines are persisted values; no SLA or
lifecycle calculation occurs. Audit entries have no cryptographic immutability claim.

## Ordering and performance

Every array is scoped to the requested document, except revisions scoped to its
master. LD, revisions, PCF, transmittals, references, files, versions and pending
records use ascending PK. Workflow history, approvals and audit use `(date, id)`
ascending. PK order is stable, not a claim about chronology of string dates.
No arbitrary LD winner, truncation or implicit deduplication is applied.

A fully related document costs 12 data queries (authentication/RBAC queries are
additional); serialization costs zero. Empty tables need no scans beyond FK-scoped
queries. A missing master skips its revision prefetch. No filesystem or storage
operations are performed. Arrays are intentionally complete; the inspected sample
has 158 pending records. This is not a transactional snapshot across concurrent
operational updates.

## Security choices

Explicit allowlists omit LD paths, PCF caminho/pcf_link, transmittal pasta/arquivo_pdf,
parse notes, FileField paths/URLs, external URLs, arbitrary JSON metadata/divergences,
financial fields, deletion actors/reasons, pending internal keys and free-form notes.
Workflow observations, approval comments, file-version observations, pending
 descriptions/recommended-action text and audit descriptions are omitted because
these arbitrary narratives can contain internal paths or sensitive data. This is
an explicit metadata-only contract, not a claim that their source values are empty.
The stored external divergent boolean is retained.

File names are basenames only, handling both Windows and POSIX separators. Missing
original attachment names remain null/empty; file-version names use the stored
FileField name without opening storage or resolving a URL. Users expose only id
and username, not email, permissions or account flags. There is no download route.
These exclusions apply to this new endpoint; the existing Central contract is unchanged.

## SELECT-only profiling — 2026-09-15

Configured database: SQLite at `C:/GED_DATA/db.sqlite3`. Direct connection used
`mode=ro&immutable=1` with a SELECT-only authorizer; no Django setup or write service.
WAL/SHM were absent before and after, and database size/mtime did not change during
profiling. Counts are observations at profiling time, not migration assumptions.

| Model | Total | Linked to Documento | Distinct documents | Distinct visible documents | Unlinked |
|---|---:|---:|---:|---:|---:|
| ArquivoDocumento | 12 | 12 | 6 | 2 | 0 |
| DocumentoVersao | 10 | 10 | 4 | 1 | 0 |
| DocumentoReferenciaExterna | 359 | 359 | 358 | 358 | 0 |
| DocumentoWorkflowStatus | 2438 | 2438 | 2438 | 1236 | 0 |
| DocumentoWorkflowHistorico | 3354 | 3354 | 2438 | 1236 | 0 |
| DocumentoAprovacao | 0 | 0 | 0 | 0 | 0 |
| LogAuditoria | 2624 | 1856 | 1839 | 598 | 768 |
| DocumentoLD | 1199 | 1199 | 1197 | 1197 | 0 |
| PCFTimeline | 430 | 407 | 142 | 142 | 23 |
| TransmittalKM | 349 | 130 | 127 | 127 | 219 |
| PendenciaDocumental | 79210 | 79210 | 1827 | 931 | 0 |

Documento: 2477 total, 1236 visible, all 2477 with master.
DocumentoMestre: 1064 total/active, all with current pointer.
Pending statuses: 952 ABERTA; 78258 RESOLVIDA.

JSON inspection: all 359 reference metadata objects contain string keys
origem_ld/status_ld/guia_emissao; divergence arrays are empty in 253 and contain
one item in 106. Pending metadata is empty in 71598 rows and has integer `open`
in 7612. The inspected values had no detected path/secret pattern, but arbitrary
JSON remains excluded because its schema permits future unsafe content.

Manual candidates with seven populated relation categories each:

- 599, I-ET-4880.00-9311-000-CZ1-001: project 27, 3 files, 1 LD, 1 PCF,
  1 workflow status, 2 workflow history entries, 2 audit entries, 158 pending records.
- 1316, I-DE-4880.00-0100-100-CZ1-008: null project, 1 LD, 1 PCF, 1 transmittal,
  1 workflow status, 1 history, 1 audit entry, 158 pending records.
- 1321, I-DE-4880.00-3100-200-CZ1-004: same populated relation categories as 1316.

No single candidate covers every relation; approvals are empty in production.
Isolated test fixtures cover all contract sections, including approvals and versions.

## Validation

Use the official checkout's venv. For validation only, set process-local
`DATABASE_URL=sqlite:///:memory:` and `PYTHONDONTWRITEBYTECODE=1` so production
connections are not used. Do not change `.env`.

- `python manage.py check`: no issues.
- `python manage.py test apps.api -v 2`: 61 tests passed, 22 new Document 360 tests.
- Relevant existing Central/RBAC tests: 13 passed.
- Expected CSRF rejection logs occur in negative tests; CSRF stays enabled.

Tests include allowlisted schema, all relationships, historical revision semantics,
nulls, hidden-document 404s, exact permission, methods, deterministic ordering,
query count, unchanged record snapshots, SELECT-only SQL, blocked sync helpers and
blocked storage access. Existing migrations are applied only by Django's isolated
test runner to its in-memory database; no migrations are created.

Manual validation, authenticated with automacoes.visualizar:
`http://127.0.0.1:8000/api/v1/document-center/599/`
Also inspect `/api/v1/document-center/1316/` for a null project and a transmittal.
