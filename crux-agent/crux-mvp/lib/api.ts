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
  provider_name?: string;
  result?: TaskResult;
  error?: string;
  partial_results?: any;
  metadata?: Record<string, any>;
  job_params?: Record<string, any>;
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
  lmstudio_models: string[];
}

export interface ContextLimitsResponse {
  providers: {
    openai: {
      context_limit: number;
      models: Record<string, number>;
    };
    openrouter: {
      context_limit: number;
      models: Record<string, number>;
    };
    lmstudio: {
      context_limit: number;
      models: Record<string, number>;
    };
  };
  management: {
    summarization_threshold: number;
    response_reserve: number;
  };
  fallback_limit?: number;
}

// API Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_VERSION = '/api/v1';

// API Client
class ApiClient {
  private baseURL: string;

  constructor() {
    this.baseURL = `${API_BASE_URL}${API_VERSION}`;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
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

  async listJobs(statusFilter?: string, limit: number = 50): Promise<JobResponse[]> {
    const params = new URLSearchParams();
    
    if (statusFilter) {
      params.append('status_filter', statusFilter);
    }
    params.append('limit', limit.toString());

    const queryString = params.toString();
    const endpoint = `/jobs${queryString ? `?${queryString}` : ''}`;
    
    return this.request<JobResponse[]>(endpoint);
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

  async getContextLimits(): Promise<ContextLimitsResponse> {
    return this.request<ContextLimitsResponse>('/jobs/config/context-limits');
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

/**
 * Get context limit for a specific model and provider
 * @param modelName - Model name
 * @param providerName - Provider name (openai, openrouter, lmstudio)
 * @param contextLimits - Context limits configuration from API
 * @returns Context limit in tokens or fallback value
 */
export function getModelContextLimit(
  modelName: string | undefined,
  providerName: string | undefined,
  contextLimits: ContextLimitsResponse | null
): number {
  if (!contextLimits) {
    return 50000; // Fallback for unknown models
  }

  // If we have the provider name, use it directly
  if (providerName && contextLimits.providers[providerName as keyof typeof contextLimits.providers]) {
    const provider = contextLimits.providers[providerName as keyof typeof contextLimits.providers];
    
    // Check if there's a specific model limit
    if (modelName && provider.models[modelName]) {
      return provider.models[modelName];
    }
    
    // Fall back to provider's default context limit
    return provider.context_limit;
  }

  // Fallback: If no provider name, try to guess from model name (legacy behavior)
  if (modelName) {
    // Try exact match first for OpenRouter models
    const openrouterModels = contextLimits.providers.openrouter.models;
    if (openrouterModels[modelName]) {
      return openrouterModels[modelName];
    }

    // Try exact match for OpenAI models
    const openaiModels = contextLimits.providers.openai.models;
    if (openaiModels[modelName]) {
      return openaiModels[modelName];
    }

    // For LMStudio models, use the configured limit from .env
    // This respects whatever is set in LMSTUDIO_CONTEXT_LIMIT
    if (modelName.includes('lmstudio') || modelName.includes('localhost') || modelName.includes('127.0.0.1')) {
      return contextLimits.providers.lmstudio.context_limit;
    }
  }

  // Use the API-provided fallback limit, or 50000 as final fallback
  return contextLimits.fallback_limit || 50000;
}

/**
 * Determines task mode (basic or enhanced) from a JobResponse
 * @param job - The job response from the API
 * @returns "basic" or "enhanced" mode
 */
export function detectTaskMode(job: JobResponse): "basic" | "enhanced" {
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
