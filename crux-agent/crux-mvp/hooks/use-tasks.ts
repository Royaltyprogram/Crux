"use client";

import { useState, useEffect, useCallback } from "react";
import { type JobResponse, type TaskResult, apiClient, detectTaskMode } from "@/lib/api";

export interface Task {
  id: string;
  topic: string;
  mode: "basic" | "enhanced";
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  progress: number;
  currentPhase: string;
  modelName?: string;
  providerName?: string;
  result?: TaskResult;
  error?: string;
  partial_results?: any;
}

// Storage management constants
const MAX_TASKS_IN_STORAGE = 100; // Limit number of tasks in cache

// Helper function to create minimal task info for storage (dashboard view)
function createMinimalTask(task: Task): Task {
  return {
    id: task.id,
    topic: task.topic,
    mode: task.mode,
    status: task.status,
    createdAt: task.createdAt,
    startedAt: task.startedAt,
    completedAt: task.completedAt,
    progress: task.progress,
    currentPhase: task.currentPhase,
    modelName: task.modelName,
    providerName: task.providerName,
    error: task.error,
    // Store minimal result info for dashboard display
    result: task.result ? {
      iterations: task.result.iterations,
      converged: task.result.converged,
      total_tokens: task.result.total_tokens,
      processing_time: task.result.processing_time,
      // Don't store the full output or metadata - fetch on demand
      output: undefined,
      metadata: undefined
    } : undefined
  };
}

// Helper function to safely save minimal tasks to localStorage
function safelySetTasks(tasks: Task[]): Task[] {
  try {
    // Sort tasks by creation date (newest first) and limit count
    const sortedTasks = [...tasks]
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, MAX_TASKS_IN_STORAGE);
    
    // Store only minimal task info to save space
    const minimalTasks = sortedTasks.map(createMinimalTask);
    
    localStorage.setItem("crux-tasks", JSON.stringify(minimalTasks));
    return sortedTasks; // Return original tasks for state, not minimal ones
  } catch (error) {
    console.warn("LocalStorage quota exceeded, reducing task count...");
    
    // If still failing, progressively reduce task count
    for (let maxTasks = 75; maxTasks >= 10; maxTasks -= 10) {
      try {
        const limitedTasks = [...tasks]
          .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
          .slice(0, maxTasks);
        
        const minimalTasks = limitedTasks.map(createMinimalTask);
        localStorage.setItem("crux-tasks", JSON.stringify(minimalTasks));
        console.log(`Successfully saved ${maxTasks} minimal tasks after cleanup`);
        return limitedTasks;
      } catch (e) {
        console.warn(`Still too large with ${maxTasks} tasks, trying fewer...`);
        continue;
      }
    }
    
    // Last resort - clear storage
    console.error("Could not save even minimal task data, clearing storage");
    localStorage.removeItem("crux-tasks");
    return tasks.slice(0, 10); // Keep at least some tasks in memory
  }
}

export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load task list from local storage or API
  const loadTasks = useCallback(async () => {
    try {
      setLoading(true);
      const storedTasks = localStorage.getItem("crux-tasks");
      
      if (storedTasks) {
        // Load from cache
        const parsedTasks: Task[] = JSON.parse(storedTasks);
        setTasks(parsedTasks);

        // Update status of running tasks
        const runningTasks = parsedTasks.filter(
          (task) => task.status === "pending" || task.status === "running"
        );

        for (const task of runningTasks) {
          try {
            const jobResponse = await apiClient.getJob(task.id, {
              include_evolution_history: true,
              include_partial_results: true, // Get partial results for running tasks
            });
            updateTaskFromJobResponse(task.id, jobResponse);
          } catch (err) {
            console.error(`Failed to update task ${task.id}:`, err);
            // If job not found (404), mark task as failed
            if (err instanceof Error && err.message.includes('404')) {
              setTasks((prevTasks) => {
                const updatedTasks = prevTasks.map((t) =>
                  t.id === task.id ? { ...t, status: "failed" as const, error: "Job not found" } : t
                );
                return safelySetTasks(updatedTasks);
              });
            }
          }
        }
      } else {
        // Cache is empty, fetch completed tasks from API
        console.log("Cache is empty, fetching completed tasks from API...");
        try {
          const completedJobs = await apiClient.listJobs("completed", 50);
          console.log(`Fetched ${completedJobs.length} completed tasks from API`);
          
          const tasksFromApi: Task[] = completedJobs.map(job => {
            // Determine mode using centralized helper
            const mode = detectTaskMode(job);
            
            // Use question snippet from job metadata if available
            const topic = job.metadata?.question_snippet || "Research Task";
            
            return {
              id: job.job_id,
              topic,
              mode,
              status: job.status,
              createdAt: job.created_at || new Date().toISOString(),
              startedAt: job.started_at,
              completedAt: job.completed_at,
              progress: job.progress,
              currentPhase: job.current_phase,
              modelName: job.model_name,
              providerName: job.provider_name,
              result: job.result,
              error: job.error,
            };
          });
          
          setTasks(tasksFromApi);
          // Save minimal task info to cache for next time
          safelySetTasks(tasksFromApi);
        } catch (apiError) {
          console.error("Failed to fetch tasks from API:", apiError);
          // If API fails, just start with empty list
          setTasks([]);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  }, []);

  // Update task status from JobResponse
  const updateTaskFromJobResponse = useCallback(
    (taskId: string, jobResponse: JobResponse) => {
      setTasks((prevTasks) => {
        const updatedTasks = prevTasks.map((task) => {
          if (task.id === taskId) {
            // Re-detect task mode from current job response
            const detectedMode = detectTaskMode(jobResponse);
            
            // Smart mode updating: 
            // - If we detect "enhanced", always use it (definitive evidence)
            // - If we detect "basic" but original was "enhanced", keep "enhanced" 
            //   until we have definitive evidence (for early-stage tasks)
            // - If original was "basic" and we detect "basic", keep "basic"
            let finalMode = task.mode;
            if (detectedMode === "enhanced") {
              finalMode = "enhanced"; // Definitive evidence of enhanced mode
            } else if (task.mode === "basic") {
              finalMode = "basic"; // Was basic, stays basic
            }
            // If task.mode was "enhanced" and detectedMode is "basic", 
            // keep "enhanced" (this handles early-stage enhanced tasks)
            
            const updatedTask: Task = {
              ...task,
              mode: finalMode, // Use smart mode detection
              status: jobResponse.status,
              progress: jobResponse.progress,
              currentPhase: jobResponse.current_phase,
              startedAt: jobResponse.started_at,
              completedAt: jobResponse.completed_at,
              modelName: jobResponse.model_name,
              providerName: jobResponse.provider_name,
              result: jobResponse.result,
              partial_results: jobResponse.partial_results,
            };
            return updatedTask;
          }
          return task;
        });

        // Save to local storage with quota management
        const savedTasks = safelySetTasks(updatedTasks);
        return savedTasks;
      });
    },
    []
  );

  // Add new task
  const addTask = useCallback((task: Task) => {
    setTasks((prevTasks) => {
      const newTasks = [task, ...prevTasks];
      return safelySetTasks(newTasks);
    });
  }, []);

  // Start polling task status
  const startPolling = useCallback(
    (taskId: string) => {
      const pollInterval = setInterval(async () => {
        try {
          const jobResponse = await apiClient.getJob(taskId, {
            include_evolution_history: true,
            include_partial_results: true, // Get partial results for running tasks
          });
          updateTaskFromJobResponse(taskId, jobResponse);

          // Stop polling for completed tasks
          if (
            jobResponse.status === "completed" ||
            jobResponse.status === "failed" ||
            jobResponse.status === "cancelled"
          ) {
            clearInterval(pollInterval);
          }
        } catch (err) {
          console.error(`Polling failed for task ${taskId}:`, err);
          // If job not found (404), mark task as failed and stop polling
          if (err instanceof Error && err.message.includes('404')) {
            setTasks((prevTasks) => {
              const updatedTasks = prevTasks.map((t) =>
                t.id === taskId ? { ...t, status: "failed" as const, error: "Job not found" } : t
              );
              return safelySetTasks(updatedTasks);
            });
          }
          clearInterval(pollInterval);
        }
      }, 3000); // Poll every 3 seconds

      // Automatically stop after 15 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
      }, 15 * 60 * 1000);

      return () => clearInterval(pollInterval);
    },
    [updateTaskFromJobResponse]
  );

  // Cancel task
  const cancelTask = useCallback(async (taskId: string) => {
    try {
      await apiClient.cancelJob(taskId);
      setTasks((prevTasks) => {
        const updatedTasks = prevTasks.map((task) =>
          task.id === taskId ? { ...task, status: "cancelled" as const } : task
        );
        return safelySetTasks(updatedTasks);
      });
    } catch (err) {
      throw new Error(
        err instanceof Error ? err.message : "Failed to cancel task"
      );
    }
  }, []);

  // Purge/delete task
  const purgeTask = useCallback(async (taskId: string) => {
    // Optimistically remove from local state/storage first
    setTasks((prevTasks) => {
      const updatedTasks = prevTasks.filter((task) => task.id !== taskId);
      return safelySetTasks(updatedTasks);
    });

    try {
      await apiClient.purgeJob(taskId);
    } catch (err) {
      // If backend returns 404 or other error, we keep local removal
      console.warn("purgeJob backend error ignored:", err);
    }
  }, []);

  // Fetch full task details on demand (for individual task view)
  const fetchFullTaskDetails = useCallback(async (taskId: string): Promise<Task | null> => {
    try {
      const jobResponse = await apiClient.getJob(taskId, {
        include_evolution_history: true,
        include_partial_results: true, // Include partial results for running tasks
      });
      
      // Find the basic task info from our cache
      const cachedTask = tasks.find(t => t.id === taskId);
      
      // Re-detect task mode from current job response
      const currentMode = detectTaskMode(jobResponse);
      
      const fullTask: Task = {
        id: taskId,
        topic: cachedTask?.topic || "Unknown Task",
        mode: currentMode, // Use detected mode from job response
        status: jobResponse.status,
        createdAt: cachedTask?.createdAt || jobResponse.created_at || new Date().toISOString(),
        startedAt: jobResponse.started_at,
        completedAt: jobResponse.completed_at,
        progress: jobResponse.progress,
        currentPhase: jobResponse.current_phase,
        modelName: jobResponse.model_name,
        providerName: jobResponse.provider_name,
        result: jobResponse.result, // Full result with all data
        partial_results: jobResponse.partial_results, // Include partial results
        error: cachedTask?.error
      };
      
      // Optionally update the cached task with full data (but don't save to localStorage)
      setTasks(prevTasks => 
        prevTasks.map(task => 
          task.id === taskId ? fullTask : task
        )
      );
      
      return fullTask;
    } catch (error) {
      console.error(`Failed to fetch full details for task ${taskId}:`, error);
      return null;
    }
  }, [tasks]);

  // Clear all tasks (useful for development)
  const clearAllTasks = useCallback(() => {
    localStorage.removeItem("crux-tasks");
    setTasks([]);
  }, []);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  return {
    tasks,
    loading,
    error,
    addTask,
    startPolling,
    cancelTask,
    refreshTasks: loadTasks,
    clearAllTasks,
    purgeTask,
    fetchFullTaskDetails,
  };
}
