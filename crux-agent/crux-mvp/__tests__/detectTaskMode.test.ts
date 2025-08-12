/**
 * Tests for detectTaskMode function
 * These tests verify that the detectTaskMode function correctly identifies
 * whether a task is running in "basic" or "enhanced" mode based on various
 * metadata fields in the JobResponse object.
 */

import { detectTaskMode, type JobResponse } from '../lib/api';

describe('detectTaskMode', () => {
  // Test case 1: Enhanced mode detected via job.result.metadata.runner
  test('should detect enhanced mode from job.result.metadata.runner', () => {
    const job: JobResponse = {
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
    };

    expect(detectTaskMode(job)).toBe('enhanced');
  });

  // Test case 2: Enhanced mode detected via job.result.metadata.specialist_consultations
  test('should detect enhanced mode from specialist_consultations > 0', () => {
    const job: JobResponse = {
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
    };

    expect(detectTaskMode(job)).toBe('enhanced');
  });

  // Test case 3: Enhanced mode detected via job.partial_results.metadata.runner
  test('should detect enhanced mode from partial_results.metadata.runner', () => {
    const job: JobResponse = {
      job_id: 'test-3',
      status: 'running',
      progress: 60,
      current_phase: 'Processing',
      partial_results: {
        metadata: {
          runner: 'enhanced'
        }
      }
    };

    expect(detectTaskMode(job)).toBe('enhanced');
  });

  // Test case 4: Enhanced mode detected via job.partial_results.metadata.specialist_consultations
  test('should detect enhanced mode from partial_results specialist_consultations', () => {
    const job: JobResponse = {
      job_id: 'test-4',
      status: 'running',
      progress: 45,
      current_phase: 'Consulting specialists',
      partial_results: {
        metadata: {
          specialist_consultations: 1
        }
      }
    };

    expect(detectTaskMode(job)).toBe('enhanced');
  });

  // Test case 5: Enhanced mode detected via job.metadata.runner
  test('should detect enhanced mode from job.metadata.runner', () => {
    const job: JobResponse = {
      job_id: 'test-5',
      status: 'pending',
      progress: 0,
      current_phase: 'Initializing',
      metadata: {
        runner: 'enhanced'
      }
    };

    expect(detectTaskMode(job)).toBe('enhanced');
  });

  // Test case 6: Enhanced mode detected via job.metadata.specialist_consultations
  test('should detect enhanced mode from job.metadata specialist_consultations', () => {
    const job: JobResponse = {
      job_id: 'test-6',
      status: 'running',
      progress: 30,
      current_phase: 'Processing',
      metadata: {
        specialist_consultations: 3
      }
    };

    expect(detectTaskMode(job)).toBe('enhanced');
  });

  // Test case 7: Enhanced mode detected via job.job_params.mode
  test('should detect enhanced mode from job.job_params.mode', () => {
    const job: JobResponse = {
      job_id: 'test-7',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      job_params: {
        mode: 'enhanced'
      }
    };

    expect(detectTaskMode(job)).toBe('enhanced');
  });

  // Test case 8: Enhanced mode detected via job.job_params.runner
  test('should detect enhanced mode from job.job_params.runner', () => {
    const job: JobResponse = {
      job_id: 'test-8',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      job_params: {
        runner: 'enhanced'
      }
    };

    expect(detectTaskMode(job)).toBe('enhanced');
  });

  // Test case 9: Basic mode (no enhanced indicators)
  test('should default to basic mode when no enhanced indicators present', () => {
    const job: JobResponse = {
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
    };

    expect(detectTaskMode(job)).toBe('basic');
  });

  // Test case 10: Basic mode (minimal job object)
  test('should default to basic mode for minimal job object', () => {
    const job: JobResponse = {
      job_id: 'test-10',
      status: 'pending',
      progress: 0,
      current_phase: 'Initializing'
    };

    expect(detectTaskMode(job)).toBe('basic');
  });

  // Test case 11: Enhanced mode priority test (multiple indicators)
  test('should detect enhanced mode when multiple enhanced indicators present', () => {
    const job: JobResponse = {
      job_id: 'test-11',
      status: 'completed',
      progress: 100,
      current_phase: 'Completed',
      result: {
        output: 'Test output',
        iterations: 8,
        total_tokens: 2000,
        processing_time: 300,
        converged: true,
        stop_reason: 'converged',
        metadata: {
          runner: 'enhanced',
          specialist_consultations: 4
        }
      },
      metadata: {
        runner: 'enhanced',
        specialist_consultations: 2
      },
      job_params: {
        mode: 'enhanced',
        runner: 'enhanced'
      }
    };

    expect(detectTaskMode(job)).toBe('enhanced');
  });

  // Test case 12: specialist_consultations = 0 should not trigger enhanced mode
  test('should not detect enhanced mode when specialist_consultations is 0', () => {
    const job: JobResponse = {
      job_id: 'test-12',
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
    };

    expect(detectTaskMode(job)).toBe('basic');
  });

  // Test case 13: Edge case with undefined specialist_consultations
  test('should handle undefined specialist_consultations gracefully', () => {
    const job: JobResponse = {
      job_id: 'test-13',
      status: 'running',
      progress: 50,
      current_phase: 'Processing',
      result: {
        output: 'Test output',
        iterations: 2,
        total_tokens: 400,
        processing_time: 50,
        converged: false,
        stop_reason: 'max_iterations',
        metadata: {
          runner: 'basic',
          specialist_consultations: undefined
        }
      }
    };

    expect(detectTaskMode(job)).toBe('basic');
  });

  // Test case 14: Running task with partial results showing enhanced mode
  test('should detect enhanced mode for running task with partial enhanced results', () => {
    const job: JobResponse = {
      job_id: 'test-14',
      status: 'running',
      progress: 75,
      current_phase: 'Consulting specialists',
      partial_results: {
        evolution_history: [
          {
            iteration: 1,
            output: 'Initial analysis',
            prompt: 'Analyze this problem',
            feedback: 'Need more depth',
            should_stop: false
          }
        ],
        metadata: {
          runner: 'enhanced',
          specialist_consultations: 2
        }
      }
    };

    expect(detectTaskMode(job)).toBe('enhanced');
  });

  // Test case 15: Mixed signals - enhanced should win
  test('should prioritize enhanced indicators over basic indicators', () => {
    const job: JobResponse = {
      job_id: 'test-15',
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
    };

    expect(detectTaskMode(job)).toBe('enhanced');
  });
});

// Manual test runner function (since Jest might not be set up)
export function runManualTests() {
  console.log('Running manual tests for detectTaskMode...\n');

  const tests = [
    {
      name: 'Enhanced mode via result.metadata.runner',
      job: {
        job_id: 'manual-1',
        status: 'completed' as const,
        progress: 100,
        current_phase: 'Completed',
        result: {
          output: 'Test output',
          iterations: 5,
          total_tokens: 1000,
          processing_time: 120,
          converged: true,
          stop_reason: 'converged',
          metadata: { runner: 'enhanced' }
        }
      } as JobResponse,
      expected: 'enhanced'
    },
    {
      name: 'Enhanced mode via specialist_consultations',
      job: {
        job_id: 'manual-2',
        status: 'completed' as const,
        progress: 100,
        current_phase: 'Completed',
        result: {
          output: 'Test output',
          iterations: 3,
          total_tokens: 800,
          processing_time: 90,
          converged: true,
          stop_reason: 'converged',
          metadata: { specialist_consultations: 2 }
        }
      } as JobResponse,
      expected: 'enhanced'
    },
    {
      name: 'Basic mode (no enhanced indicators)',
      job: {
        job_id: 'manual-3',
        status: 'completed' as const,
        progress: 100,
        current_phase: 'Completed',
        result: {
          output: 'Test output',
          iterations: 2,
          total_tokens: 500,
          processing_time: 60,
          converged: true,
          stop_reason: 'converged'
        }
      } as JobResponse,
      expected: 'basic'
    }
  ];

  let passed = 0;
  let failed = 0;

  tests.forEach(({ name, job, expected }) => {
    const result = detectTaskMode(job);
    if (result === expected) {
      console.log(`✅ ${name}: PASSED (${result})`);
      passed++;
    } else {
      console.log(`❌ ${name}: FAILED (expected ${expected}, got ${result})`);
      failed++;
    }
  });

  console.log(`\nResults: ${passed} passed, ${failed} failed`);
  return { passed, failed };
}
