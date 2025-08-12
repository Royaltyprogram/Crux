/**
 * Simple test runner for detectTaskMode function
 * This can be run with Node.js to test the function without Jest
 */

// Since we're using Node.js, we need to simulate the ES modules
const path = require('path');

// Mock detectTaskMode function (we'll copy the logic here for testing)
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
  
  // 7. Default to basic
  return "basic";
}

// Test cases
const testCases = [
  {
    name: 'Enhanced mode via result.metadata.runner',
    job: {
      job_id: 'test-1',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Test output',
        iterations: 5,
        total_tokens: 1000,
        processing_time: 120,
        converged: true,
        stop_reason: 'converged',
        metadata: {
          runner: 'enhanced'
        }
      }
    },
    expected: 'enhanced'
  },
  {
    name: 'Enhanced mode via specialist_consultations > 0',
    job: {
      job_id: 'test-2',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Test output',
        iterations: 3,
        total_tokens: 800,
        processing_time: 90,
        converged: true,
        stop_reason: 'converged',
        metadata: {
          runner: 'basic', // This should be overridden by specialist_consultations
          specialist_consultations: 2
        }
      }
    },
    expected: 'enhanced'
  },
  {
    name: 'Enhanced mode via partial_results.metadata.runner',
    job: {
      job_id: 'test-3',
      status: 'running',
      progress: 60,
      current_phase: 'Processing',
      partial_results: {
        metadata: {
          runner: 'enhanced'
        }
      }
    },
    expected: 'enhanced'
  },
  {
    name: 'Enhanced mode via partial_results specialist_consultations',
    job: {
      job_id: 'test-4',
      status: 'running',
      progress: 45,
      current_phase: 'Consulting specialists',
      partial_results: {
        metadata: {
          specialist_consultations: 1
        }
      }
    },
    expected: 'enhanced'
  },
  {
    name: 'Enhanced mode via job.metadata.runner',
    job: {
      job_id: 'test-5',
      status: 'pending',
      progress: 0,
      current_phase: 'Initializing',
      metadata: {
        runner: 'enhanced'
      }
    },
    expected: 'enhanced'
  },
  {
    name: 'Enhanced mode via job.metadata specialist_consultations',
    job: {
      job_id: 'test-6',
      status: 'running',
      progress: 30,
      current_phase: 'Processing',
      metadata: {
        specialist_consultations: 3
      }
    },
    expected: 'enhanced'
  },
  {
    name: 'Enhanced mode via job.job_params.mode',
    job: {
      job_id: 'test-7',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      job_params: {
        mode: 'enhanced'
      }
    },
    expected: 'enhanced'
  },
  {
    name: 'Enhanced mode via job.job_params.runner',
    job: {
      job_id: 'test-8',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      job_params: {
        runner: 'enhanced'
      }
    },
    expected: 'enhanced'
  },
  {
    name: 'Basic mode (no enhanced indicators)',
    job: {
      job_id: 'test-9',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Test output',
        iterations: 2,
        total_tokens: 500,
        processing_time: 60,
        converged: true,
        stop_reason: 'converged',
        metadata: {
          runner: 'basic'
        }
      }
    },
    expected: 'basic'
  },
  {
    name: 'Basic mode (minimal job object)',
    job: {
      job_id: 'test-10',
      status: 'pending',
      progress: 0,
      current_phase: 'Initializing'
    },
    expected: 'basic'
  },
  {
    name: 'specialist_consultations = 0 should not trigger enhanced mode',
    job: {
      job_id: 'test-11',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Test output',
        iterations: 3,
        total_tokens: 600,
        processing_time: 80,
        converged: true,
        stop_reason: 'converged',
        metadata: {
          runner: 'basic',
          specialist_consultations: 0
        }
      }
    },
    expected: 'basic'
  },
  {
    name: 'Mixed signals - enhanced should win',
    job: {
      job_id: 'test-12',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Test output',
        iterations: 5,
        total_tokens: 1200,
        processing_time: 150,
        converged: true,
        stop_reason: 'converged',
        metadata: {
          runner: 'basic', // This should be overridden
          specialist_consultations: 1 // This should trigger enhanced
        }
      },
      metadata: {
        runner: 'basic' // This should also be overridden
      }
    },
    expected: 'enhanced'
  }
];

// Run tests
console.log('Running tests for detectTaskMode function...\n');

let passed = 0;
let failed = 0;

testCases.forEach(({ name, job, expected }) => {
  const result = detectTaskMode(job);
  if (result === expected) {
    console.log(`✅ ${name}: PASSED (${result})`);
    passed++;
  } else {
    console.log(`❌ ${name}: FAILED (expected ${expected}, got ${result})`);
    failed++;
  }
});

console.log(`\nTest Results: ${passed} passed, ${failed} failed`);

if (failed === 0) {
  console.log('🎉 All tests passed!');
  process.exit(0);
} else {
  console.log(`💥 ${failed} test(s) failed!`);
  process.exit(1);
}
