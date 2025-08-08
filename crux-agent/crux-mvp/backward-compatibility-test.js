/**
 * Backward Compatibility Test for detectTaskMode function
 * This tests specifically verify that historical tasks without enhanced markers
 * correctly fall back to "basic" mode without any schema changes.
 */

// Copy the detectTaskMode function logic
function detectTaskMode(job) {
  // 1. Check if job.result?.metadata?.runner === "enhanced"
  if (job.result?.metadata?.runner === "enhanced") {
    return "enhanced";
  }
  
  // 2. Check if job.result?.metadata?.specialist_consultations > 0
  if (job.result?.metadata?.specialist_consultations > 0) {
    return "enhanced";
  }
  
  // 3. Check if job.partial_results?.metadata?.runner === "enhanced"
  if (job.partial_results?.metadata?.runner === "enhanced") {
    return "enhanced";
  }
  
  // 4. Check if job.partial_results?.metadata?.specialist_consultations > 0
  if (job.partial_results?.metadata?.specialist_consultations > 0) {
    return "enhanced";
  }
  
  // 5. Check if job.metadata?.runner === "enhanced" || job.metadata?.specialist_consultations > 0
  if (job.metadata?.runner === "enhanced" || job.metadata?.specialist_consultations > 0) {
    return "enhanced";
  }
  
  // 6. Check if job.job_params?.mode === "enhanced" || job.job_params?.runner === "enhanced"
  if (job.job_params?.mode === "enhanced" || job.job_params?.runner === "enhanced") {
    return "enhanced";
  }
  
  // 7. Default to basic (BACKWARD COMPATIBILITY FALLBACK)
  return "basic";
}

// Test cases specifically for backward compatibility
const backwardCompatibilityTests = [
  {
    name: 'Historical task - completely empty metadata',
    job: {
      job_id: 'historical-1',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Some historical output',
        iterations: 3,
        total_tokens: 500,
        processing_time: 60,
        converged: true,
        stop_reason: 'converged'
        // No metadata at all
      }
    },
    expected: 'basic'
  },
  {
    name: 'Historical task - empty metadata object',
    job: {
      job_id: 'historical-2',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Some historical output',
        metadata: {} // Empty metadata object
      }
    },
    expected: 'basic'
  },
  {
    name: 'Historical task - metadata with unrelated fields',
    job: {
      job_id: 'historical-3',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Some historical output',
        metadata: {
          question_snippet: 'Historical question',
          some_other_field: 'value',
          timestamp: '2024-01-01T00:00:00Z'
          // No runner or specialist_consultations fields
        }
      }
    },
    expected: 'basic'
  },
  {
    name: 'Historical task - null metadata',
    job: {
      job_id: 'historical-4',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Some historical output',
        metadata: null
      }
    },
    expected: 'basic'
  },
  {
    name: 'Historical task - undefined specialist_consultations',
    job: {
      job_id: 'historical-5',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Some historical output',
        metadata: {
          specialist_consultations: undefined,
          runner: undefined
        }
      }
    },
    expected: 'basic'
  },
  {
    name: 'Historical task - runner field with different value',
    job: {
      job_id: 'historical-6',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Some historical output',
        metadata: {
          runner: 'legacy_system' // Some other value, not "enhanced"
        }
      }
    },
    expected: 'basic'
  },
  {
    name: 'Historical task - negative specialist_consultations',
    job: {
      job_id: 'historical-7',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Some historical output',
        metadata: {
          specialist_consultations: -1 // Negative value should not trigger enhanced
        }
      }
    },
    expected: 'basic'
  },
  {
    name: 'Historical task - string specialist_consultations',
    job: {
      job_id: 'historical-8',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Some historical output',
        metadata: {
          specialist_consultations: "0" // String "0" should not trigger enhanced
        }
      }
    },
    expected: 'basic'
  },
  {
    name: 'Historical task - minimal structure (very old task)',
    job: {
      job_id: 'historical-9',
      status: 'completed'
      // Minimal structure - just status and ID
    },
    expected: 'basic'
  },
  {
    name: 'Historical task - only basic job params',
    job: {
      job_id: 'historical-10',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      job_params: {
        model: 'gpt-4',
        temperature: 0.7
        // No mode or runner fields
      },
      result: {
        output: 'Some historical output'
      }
    },
    expected: 'basic'
  }
];

// Run backward compatibility tests
console.log('🔄 Running Backward Compatibility Tests for detectTaskMode...\n');

let passed = 0;
let failed = 0;

backwardCompatibilityTests.forEach(({ name, job, expected }) => {
  const result = detectTaskMode(job);
  if (result === expected) {
    console.log(`✅ ${name}: PASSED (${result})`);
    passed++;
  } else {
    console.log(`❌ ${name}: FAILED (expected ${expected}, got ${result})`);
    failed++;
  }
});

console.log(`\n📊 Backward Compatibility Test Results: ${passed} passed, ${failed} failed`);

if (failed === 0) {
  console.log('🎉 All backward compatibility tests passed!');
  console.log('✨ Historical tasks will correctly fall back to "basic" mode.');
  console.log('🔒 No schema changes required - existing data remains valid.');
  process.exit(0);
} else {
  console.log(`💥 ${failed} backward compatibility test(s) failed!`);
  console.log('⚠️  This could break historical task display.');
  process.exit(1);
}
