"use client";

import { useState, useEffect, useCallback } from "react";
import { type JobResponse, type TaskResult, apiClient } from "@/lib/api";

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
  result?: TaskResult;
  error?: string;
}

export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load task list from local storage
  const loadTasks = useCallback(async () => {
    try {
      setLoading(true);
      const storedTasks = localStorage.getItem("crux-tasks");
      if (storedTasks) {
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
                localStorage.setItem("crux-tasks", JSON.stringify(updatedTasks));
                return updatedTasks;
              });
            }
          }
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
            const updatedTask: Task = {
              ...task,
              status: jobResponse.status,
              progress: jobResponse.progress,
              currentPhase: jobResponse.current_phase,
              startedAt: jobResponse.started_at,
              completedAt: jobResponse.completed_at,
              result: jobResponse.result,
            };
            return updatedTask;
          }
          return task;
        });

        // Save to local storage
        localStorage.setItem("crux-tasks", JSON.stringify(updatedTasks));
        return updatedTasks;
      });
    },
    []
  );

  // Add new task
  const addTask = useCallback((task: Task) => {
    setTasks((prevTasks) => {
      const newTasks = [task, ...prevTasks];
      localStorage.setItem("crux-tasks", JSON.stringify(newTasks));
      return newTasks;
    });
  }, []);

  // Start polling task status
  const startPolling = useCallback(
    (taskId: string) => {
      const pollInterval = setInterval(async () => {
        try {
          const jobResponse = await apiClient.getJob(taskId, {
            include_evolution_history: true,
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
              localStorage.setItem("crux-tasks", JSON.stringify(updatedTasks));
              return updatedTasks;
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
        localStorage.setItem("crux-tasks", JSON.stringify(updatedTasks));
        return updatedTasks;
      });
    } catch (err) {
      throw new Error(
        err instanceof Error ? err.message : "Failed to cancel task"
      );
    }
  }, []);

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
  };
}
