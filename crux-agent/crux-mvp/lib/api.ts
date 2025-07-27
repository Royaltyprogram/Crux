/**
 * API client and utility functions
 */

// Types
export interface BasicSolveRequest {
  question: string;
  context?: string;
  constraints?: string;
  n_iters?: number;
  llm_provider?: string;
  model_name?: string;
  async_mode?: boolean;
}

export interface EnhancedSolveRequest {
  question: string;
  context?: string;
  specialist_max_iters?: number;
  professor_max_iters?: number;
  llm_provider?: string;
  model_name?: string;
  async_mode?: boolean;
}

export interface TaskResult {
  output: string;
  iterations: number;
  total_tokens: number;
  processing_time: number;
  converged: boolean;
  stop_reason: string;
  metadata?: Record<string, any>;
}

export interface AsyncJobResponse {
  job_id: string;
  status: string;
  created_at: string;
  message: string;
}

export interface JobResponse {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  progress: number;
  current_phase: string;
  model_name?: string;
  result?: TaskResult;
  error?: string;
  partial_results?: any;
}

export interface GetJobOptions {
  include_partial_results?: boolean;
  include_evolution_history?: boolean;
  include_specialist_details?: boolean;
}

export interface SettingsResponse {
  llm_provider: string;
  model_name: string;
  max_iters: number;
  specialist_max_iters: number;
  professor_max_iters: number;
  available_providers: string[];
  openai_models: string[];
  openrouter_models: string[];
}

// API Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const API_VERSION = '/api/v1';

// API Client
class ApiClient {
  private baseURL: string;
  private apiKey: string;

  constructor() {
    this.baseURL = `${API_BASE_URL}${API_VERSION}`;
    this.apiKey = process.env.NEXT_PUBLIC_API_KEY || 'demo-api-key-12345';
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.apiKey}`,
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        const errorText = await response.text();
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        
        try {
          const errorJson = JSON.parse(errorText);
          errorMessage = errorJson.detail || errorMessage;
        } catch {
          // If error text isn't JSON, use the raw text
          errorMessage = errorText || errorMessage;
        }
        
        throw new Error(errorMessage);
      }

      return await response.json();
    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Network error occurred');
    }
  }

  async solveBasic(request: BasicSolveRequest): Promise<TaskResult | AsyncJobResponse> {
    return this.request<TaskResult | AsyncJobResponse>('/solve/basic', {
      method: 'POST',
      body: JSON.stringify({
        ...request,
        async_mode: true, // Always use async mode for UI
      }),
    });
  }

  async solveEnhanced(request: EnhancedSolveRequest): Promise<TaskResult | AsyncJobResponse> {
    return this.request<TaskResult | AsyncJobResponse>('/solve/enhanced', {
      method: 'POST',
      body: JSON.stringify({
        ...request,
        async_mode: true, // Always use async mode for UI
      }),
    });
  }

  async getJob(jobId: string, options: GetJobOptions = {}): Promise<JobResponse> {
    const params = new URLSearchParams();
    
    if (options.include_partial_results) {
      params.append('include_partial_results', 'true');
    }
    if (options.include_evolution_history) {
      params.append('include_evolution_history', 'true');
    }
    if (options.include_specialist_details) {
      params.append('include_specialist_details', 'true');
    }

    const queryString = params.toString();
    const endpoint = `/jobs/${jobId}${queryString ? `?${queryString}` : ''}`;
    
    return this.request<JobResponse>(endpoint);
  }

  async cancelJob(jobId: string): Promise<{ job_id: string; status: string; message: string }> {
    return this.request(`/jobs/${jobId}`, {
      method: 'DELETE',
    });
  }

  async purgeJob(jobId: string): Promise<void> {
    return this.request(`/jobs/${jobId}/purge`, {
      method: 'DELETE',
    });
  }

  async continueTask(jobId: string, additionalIterations: number = 1): Promise<AsyncJobResponse> {
    return this.request<AsyncJobResponse>(`/solve/continue/${jobId}?additional_iterations=${additionalIterations}`, {
      method: 'POST',
    });
  }

  async getSettings(): Promise<SettingsResponse> {
    return this.request<SettingsResponse>('/settings');
  }
}

// Export singleton instance
export const apiClient = new ApiClient();

// Export specific API methods for convenience
export const continueTask = (jobId: string, additionalIterations: number = 1) => 
  apiClient.continueTask(jobId, additionalIterations);

// Also export as named export for better compatibility  
export { continueTask as continueTaskAPI };

// Utility functions
/**
 * Format duration from seconds to human readable format
 * @param seconds - Duration in seconds
 * @returns Formatted duration string
 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const remainingMinutes = Math.floor((seconds % 3600) / 60);
    return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
  }
}

/**
 * Format token count to human readable format with commas
 * @param tokens - Token count number
 * @returns Formatted token string
 */
export function formatTokens(tokens: number): string {
  return tokens.toLocaleString();
}
