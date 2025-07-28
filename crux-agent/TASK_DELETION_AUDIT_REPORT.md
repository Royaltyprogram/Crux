# Backend Task Deletion Code Paths Audit Report

## Executive Summary

This audit identifies all code paths that can result in task/job deletion in the Crux backend system. The system uses Redis as the primary storage mechanism for job data, with no traditional database persistence.

## System Architecture Overview

- **Primary Storage**: Redis (key-value store)
- **Job Lifecycle**: Managed through Redis hash keys with pattern `job:{job_id}`
- **Task Processing**: Celery workers with async job execution
- **TTL Management**: Jobs have automatic expiration (1 hour TTL)

## Discovered Deletion Paths

### 1. REST API Endpoints

#### 1.1 Job Cancellation Endpoint
- **Path**: `DELETE /api/v1/jobs/{job_id}`
- **Handler**: `app/api/routers/jobs.py:cancel_job()` (lines 101-166)
- **Action**: Sets job status to `cancelled`, updates completion timestamp
- **Cascade**: Attempts to revoke Celery task via `celery_app.control.revoke()`
- **Storage Impact**: Updates Redis hash, does not delete the key
- **Code Location**: 
  ```python
  # Line 136-142
  await redis_client.hset(
      f"job:{job_id}",
      mapping={
          "status": JobStatus.CANCELLED.value,
          "completed_at": datetime.now(timezone.utc).isoformat(),
      },
  )
  ```

### 2. Administrative Scripts

#### 2.1 Manual Job Purge Script
- **Path**: `scripts/purge_jobs.py`
- **Execution**: Manual command-line tool
- **Action**: Direct Redis key deletion using `r.delete(key)`
- **Code Location**:
  ```python
  # Line 6
  if r.delete(key):
      print(f"Deleted {key}")
  ```
- **Cascade**: No cascade logic - only deletes the specific job key

#### 2.2 Verification Script
- **Path**: `scripts/verify_purge.py`
- **Purpose**: Post-deletion verification (doesn't delete, only verifies)
- **Checks**: 
  - Redis key existence (`r.exists(key)`)
  - API 404 response verification

### 3. Automatic Expiration Mechanisms

#### 3.1 Redis TTL (Time-To-Live)
- **Location**: `app/api/routers/solve.py`
- **Implementation**: 
  ```python
  # Lines 69 & 157
  await redis_client.expire(f"job:{job_id}", 3600)  # 1 hour TTL
  ```
- **Trigger**: Automatic Redis expiration after 1 hour
- **Scope**: Applies to all async jobs (both basic and enhanced modes)

### 4. Cascade Deletion Analysis

#### 4.1 Job-to-Task Cascade
- **Mechanism**: When job is cancelled via REST API, attempts Celery task termination
- **Implementation**: `celery_app.control.revoke(job_id, terminate=True, signal="SIGKILL")`
- **Reliability**: Best-effort - logs warning if revocation fails

#### 4.2 No Database Cascades
- **Finding**: No traditional database cascade rules exist
- **Reason**: System uses Redis as primary storage with simple key-value structure

### 5. Data Dependencies and Relationships

#### 5.1 Job Data Structure
```
Redis Key: job:{job_id}
Hash Fields:
├── job_id: string
├── status: enum (pending|running|completed|failed|cancelled)
├── created_at: ISO timestamp
├── started_at: ISO timestamp (optional)
├── completed_at: ISO timestamp (optional)
├── progress: float (0.0-1.0)
├── current_phase: string (optional)
├── result: JSON string (if completed)
├── error: string (if failed)
├── partial_results: JSON string (optional)
├── request: JSON string (original request data)
└── mode: string (basic|enhanced)
```

#### 5.2 No Child Dependencies
- **Finding**: Jobs are atomic units with no child records
- **Implication**: Deletion of a job doesn't require cleanup of dependent records

## Deletion Flow Diagram

```
┌─────────────────────────┐
│ Task Deletion Triggers  │
└─────────┬───────────────┘
          │
    ┌─────▼─────┐    ┌─────────────────┐    ┌──────────────────┐
    │   Redis   │    │   REST API      │    │  Manual Script   │
    │    TTL    │    │  DELETE /jobs   │    │  purge_jobs.py   │
    │ (1 hour)  │    │     /{id}       │    │                  │
    └─────┬─────┘    └─────┬───────────┘    └─────┬────────────┘
          │                │                      │
          │                ▼                      │
          │      ┌─────────────────────┐          │
          │      │ Update Job Status   │          │
          │      │ status=cancelled    │          │
          │      │ completed_at=now    │          │
          │      └─────────┬───────────┘          │
          │                │                      │
          │                ▼                      │
          │      ┌─────────────────────┐          │
          │      │ Revoke Celery Task  │          │
          │      │ terminate=True      │          │
          │      │ signal=SIGKILL      │          │
          │      └─────────────────────┘          │
          │                                       │
          ▼                                       ▼
  ┌──────────────────┐                   ┌──────────────────┐
  │ Automatic Redis  │                   │ Direct Redis     │
  │ Key Expiration   │                   │ Key Deletion     │
  │                  │                   │ r.delete(key)    │
  └──────────────────┘                   └──────────────────┘
```

## Security and Access Control

### Deletion Authorization
- **REST API**: No explicit authorization checks in current code
- **Manual Scripts**: Command-line access required
- **Redis TTL**: Automatic, no authorization needed

### Audit Trail
- **Logging**: Deletion events logged in application logs
- **Persistence**: No permanent audit trail for deleted jobs
- **Recovery**: No recovery mechanism once job deleted from Redis

## Risk Assessment

### High Risk Areas
1. **No Authorization**: REST DELETE endpoint lacks access control
2. **No Confirmation**: Direct deletion without confirmation prompts
3. **No Backup**: Deleted jobs are permanently lost
4. **TTL Surprise**: Jobs auto-expire after 1 hour regardless of completion status

### Medium Risk Areas
1. **Script Access**: Manual purge script requires server access
2. **Failed Revocation**: Celery task might continue running if revocation fails

## Recommendations

1. **Add Authorization**: Implement access control for job deletion endpoints
2. **Add Confirmation**: Require explicit confirmation for bulk deletions
3. **Extend TTL**: Consider longer TTL for completed jobs
4. **Add Backup**: Implement job archiving before deletion
5. **Improve Logging**: Add structured audit logs for all deletion events

## Code Coverage Summary

| Component | Lines Audited | Deletion Paths | Risk Level |
|-----------|---------------|----------------|------------|
| jobs.py | 166 | 1 (cancel) | Medium |
| solve.py | 207 | 1 (TTL setup) | Low |
| purge_jobs.py | 10 | 1 (direct delete) | High |
| worker.py | 301 | 0 | N/A |

## Appendix: Search Keywords Used

- `delete` - Found in multiple contexts
- `purge` - Found in cleanup scripts
- `cleanup` - Found in documentation
- `task.expire` - Not found (Redis TTL used instead)
- `task.remove` - Not found (direct Redis delete used)

---
*Report generated on: 2025-01-27*
*Audit scope: Backend task deletion mechanisms*
*Tools used: grep, file analysis, code tracing*
