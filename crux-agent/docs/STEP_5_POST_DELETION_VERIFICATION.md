# Step 5: Post-deletion Verification and UI Cleanup

This document describes the implementation of Step 5 in the job purging process: verifying deletion and handling UI cleanup after jobs have been purged from the system.

## Overview

After running the purge script (`purge_jobs.py`), Step 5 ensures that:

1. Jobs are actually deleted from Redis (`EXISTS job:<id>` returns 0)
2. The API correctly returns 404 for purged jobs
3. The React dashboard handles purged jobs gracefully
4. Users are notified about permanently removed reports

## Implementation Components

### 1. Verification Script (`scripts/verify_purge.py`)

**Purpose**: Comprehensive verification that jobs have been properly purged from all system components.

**Features**:
- **Redis Verification**: Uses `EXISTS job:<id>` command to confirm deletion
- **API Testing**: Tests that the job endpoints return 404 for purged jobs
- **User Notification**: Provides formatted notification templates
- **Detailed Reporting**: Shows success/failure status for each verification step

**Usage**:
```bash
# Verify specific job IDs after purging
pypy scripts/verify_purge.py abc123 def456 ghi789

# The script will:
# 1. Check Redis with EXISTS command
# 2. Test API endpoints for 404 responses  
# 3. Show user notification templates
# 4. Provide verification summary
```

**Example Output**:
```
🔍 Post-Deletion Verification for 3 job(s)
============================================================

=== Step 1: Verifying Redis Deletion ===
✅ job:abc123 successfully deleted from Redis
✅ job:def456 successfully deleted from Redis
✅ job:ghi789 successfully deleted from Redis

=== Step 2: Testing API 404 Handling ===
✅ GET http://localhost:8000/api/v1/jobs/abc123 correctly returns 404 (Job not found)
✅ GET http://localhost:8000/api/v1/jobs/def456 correctly returns 404 (Job not found)
✅ GET http://localhost:8000/api/v1/jobs/ghi789 correctly returns 404 (Job not found)

=== Step 3: UI Cleanup Information ===
The React dashboard handles purged jobs as follows:

📱 Frontend Behavior:
   • use-tasks.ts hook already maps 404 errors to 'failed - job not found' state
   • Tasks showing 'Job not found' status will appear with:
     - Status badge: 'Failed' (red)
     - Error message: 'Job not found'
     - Disabled action button

[... detailed UI behavior information ...]

=== User Notification Template ===
The following notification should be shown to users:

┌─────────────────────────────────────────────────────────────┐
│ 🗑️  Research Reports Permanently Removed                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ✅ Successfully purged:                                     │
│    • Report abc123...                                       │
│    • Report def456...                                       │
│    • Report ghi789...                                       │
│                                                             │
│ These research reports and all associated data have been   │
│ permanently removed from the system and cannot be          │
│ recovered. Tasks may appear as 'Failed - Job not found'    │
│ on your dashboard.                                          │
└─────────────────────────────────────────────────────────────┘

🎉 All 3 job(s) successfully verified as purged!
```

### 2. Frontend UI Enhancements

#### Enhanced `use-tasks.ts` Hook

**New Features**:
- **404 Error Handling**: Automatically maps API 404 responses to "failed - job not found" state
- **Purged Task Removal**: New `removePurgedTasks()` function to clean up local storage
- **Persistent State**: Updates local storage when tasks become purged

**Implementation**:
```typescript
// Automatic 404 handling in polling and task loading
if (err instanceof Error && err.message.includes('404')) {
  setTasks((prevTasks) => {
    const updatedTasks = prevTasks.map((t) =>
      t.id === taskId ? { ...t, status: "failed" as const, error: "Job not found" } : t
    );
    localStorage.setItem("crux-tasks", JSON.stringify(updatedTasks));
    return updatedTasks;
  });
}

// Function to remove purged tasks from UI
const removePurgedTasks = useCallback(() => {
  setTasks((prevTasks) => {
    const activeTasks = prevTasks.filter(
      (task) => !(task.status === "failed" && task.error === "Job not found")
    );
    localStorage.setItem("crux-tasks", JSON.stringify(activeTasks));
    return activeTasks;
  });
}, []);
```

#### Enhanced Dashboard (`app/dashboard/page.tsx`)

**New Features**:
- **Purged Tasks Notification**: Orange alert box when purged tasks are detected
- **Cleanup Button**: One-click removal of purged tasks from local storage
- **User-Friendly Messaging**: Clear explanation of what happened to purged reports

**UI Components**:
```tsx
{/* Purged Tasks Notification */}
{purgedTasks.length > 0 && (
  <div className="mb-8">
    <div className="border border-orange-300 p-6 bg-orange-50">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <h3 className="font-mono text-lg text-black mb-2">
            🗑️ Reports Permanently Removed
          </h3>
          <p className="font-mono text-sm text-gray-700 mb-3 leading-relaxed">
            {purgedTasks.length} research report{purgedTasks.length > 1 ? 's have' : ' has'} been 
            permanently removed from the system and cannot be recovered. 
            These tasks now show as "Failed - Job not found".
          </p>
          <div className="font-mono text-xs text-gray-600">
            You can safely remove these entries from your dashboard.
          </div>
        </div>
        <div className="ml-6">
          <Button 
            onClick={removePurgedTasks}
            variant="outline"
            className="font-mono border-orange-600 text-orange-700 hover:bg-orange-600 hover:text-white px-4 py-2 text-sm"
          >
            Clean Up ({purgedTasks.length})
          </Button>
        </div>
      </div>
    </div>
  </div>
)}
```

#### Enhanced Task Details Page (`app/task/[id]/page.tsx`)

**New Features**:
- **Purged Task Detection**: Identifies when a task has been purged (failed + "Job not found")
- **Specialized UI**: Different messaging and styling for purged vs. failed tasks
- **User Education**: Explains why reports get purged

**Enhanced Error Handling**:
```tsx
if (task.status !== "completed") {
  const isPurged = task.status === "failed" && task.error === "Job not found";
  
  return (
    <div className="min-h-screen bg-white">
      {/* ... header ... */}
      <main className="max-w-4xl mx-auto px-5 py-12 text-center">
        <h1 className="font-mono text-2xl text-black mb-4">
          {isPurged 
            ? "🗑️ Report Permanently Removed" 
            : task.status === "failed" 
              ? "Task Failed" 
              : "Task Still Processing"
          }
        </h1>
        <p className="font-mono text-sm text-gray-600 mb-6">
          {isPurged
            ? "This research report has been permanently removed from the system and cannot be recovered."
            : /* ... other messages ... */
          }
        </p>
        {isPurged && (
          <div className="mb-6 p-4 bg-orange-50 border border-orange-200 rounded-lg max-w-md mx-auto">
            <p className="font-mono text-xs text-orange-700">
              This happens when reports are purged from the system for maintenance or storage management.
              Any associated data has been permanently deleted.
            </p>
          </div>
        )}
        {/* ... rest of component ... */}
      </main>
    </div>
  );
}
```

### 3. Demo and Testing

#### Demo Script (`scripts/demo_verify_purge.py`)

**Purpose**: Safe testing of the verification process without affecting real data.

**Features**:
- Creates temporary Redis entries for testing
- Simulates both existing and purged jobs
- Runs full verification process
- Cleans up test data automatically

**Usage**:
```bash
# Run demo to test verification process
pypy scripts/demo_verify_purge.py --demo

# This will:
# 1. Create temporary test jobs in Redis
# 2. Run the full verification process  
# 3. Show example output and notifications
# 4. Clean up test data
```

## User Experience Flow

### 1. Before Purging
- User sees normal task list with completed/failed/running tasks
- Tasks have normal status badges and action buttons

### 2. During Purging
- Admin runs `pypy scripts/purge_jobs.py job_id1 job_id2`
- Jobs are deleted from Redis
- Users may still see tasks in browser (cached in localStorage)

### 3. After Purging - Automatic Detection
- Dashboard polling detects 404 responses
- Tasks automatically update to "failed - Job not found" status
- Orange notification bar appears explaining what happened

### 4. User Cleanup
- User sees "Reports Permanently Removed" notification
- User clicks "Clean Up" button to remove entries from local storage
- Tasks disappear from dashboard
- User understands reports were permanently deleted

### 5. Verification (Admin)
- Admin runs `pypy scripts/verify_purge.py job_id1 job_id2`
- Confirms Redis deletion and API 404 responses
- Gets formatted user notification template

## Error Handling

### Redis Connection Issues
```python
try:
    exists = r.exists(key)
except redis.exceptions.ConnectionError:
    print(f"❌ Redis connection failed for {key}")
    results[job_id]['status'] = 'ERROR - Redis connection failed'
```

### API Request Failures
```python
try:
    response = requests.get(url, headers=headers, timeout=10)
except requests.exceptions.RequestException as e:
    print(f"❌ Error testing {job_id}: {e}")
    results[job_id] = {
        'status': f'ERROR - Request failed: {str(e)}',
        'url': url
    }
```

### Frontend 404 Handling
```typescript
// Already implemented in use-tasks.ts
if (err instanceof Error && err.message.includes('404')) {
  setTasks((prevTasks) => {
    const updatedTasks = prevTasks.map((t) =>
      t.id === taskId ? { ...t, status: "failed" as const, error: "Job not found" } : t
    );
    localStorage.setItem("crux-tasks", JSON.stringify(updatedTasks));
    return updatedTasks;
  });
}
```

## Configuration

### Environment Variables
```bash
# Redis connection (used by verification script)
REDIS_URL=redis://localhost:6379/0

# API configuration (used for 404 testing)
API_BASE_URL=http://localhost:8000
API_KEY=demo-api-key-12345
```

### Frontend Configuration
The React app automatically detects purged jobs through existing API error handling. No additional configuration needed.

## Files Created/Modified

### New Files
- `scripts/verify_purge.py` - Main verification script
- `scripts/demo_verify_purge.py` - Demo and testing script
- `docs/STEP_5_POST_DELETION_VERIFICATION.md` - This documentation

### Modified Files
- `crux-mvp/hooks/use-tasks.ts` - Added `removePurgedTasks()` function
- `crux-mvp/app/dashboard/page.tsx` - Added purged tasks notification and cleanup
- `crux-mvp/app/task/[id]/page.tsx` - Enhanced purged task handling

## Testing Checklist

### Redis Verification
- [ ] `EXISTS job:<id>` returns 0 for purged jobs
- [ ] `EXISTS job:<id>` returns 1 for existing jobs
- [ ] Redis connection errors are handled gracefully

### API Verification  
- [ ] GET `/api/v1/jobs/<purged_id>` returns 404
- [ ] GET `/api/v1/jobs/<existing_id>` returns 200 or other valid status
- [ ] API connection errors are handled gracefully

### Frontend Verification
- [ ] Dashboard shows orange notification for purged tasks
- [ ] "Clean Up" button removes purged tasks from localStorage
- [ ] Task detail pages show appropriate purged task messaging
- [ ] 404 errors automatically update task status to "failed - Job not found"

### User Experience
- [ ] Users understand what happened to their reports
- [ ] Users can easily clean up their dashboard
- [ ] No broken links or confusing states remain

## Security Considerations

- Verification script only reads from Redis and API (no destructive operations)
- API endpoints require proper authentication
- Frontend gracefully handles missing/deleted data
- No sensitive information exposed in error messages

## Performance Impact

- Verification script makes minimal Redis and API calls
- Frontend localStorage operations are lightweight
- No impact on running jobs or active users
- Cleanup operations are user-initiated

## Conclusion

Step 5 provides comprehensive verification and cleanup after job purging, ensuring:

1. **Complete Deletion**: Jobs are verified to be deleted from all system components
2. **User Awareness**: Clear notifications explain what happened to purged reports  
3. **Clean UI**: Users can easily remove purged task entries from their dashboard
4. **No Broken States**: All UI components handle purged jobs gracefully
5. **Admin Verification**: Comprehensive tooling to verify purge operations

The implementation maintains a good user experience even when jobs are permanently removed from the system.
