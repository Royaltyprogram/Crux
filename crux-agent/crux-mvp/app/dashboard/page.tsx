"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useTasks, type Task } from "@/hooks/use-tasks";
import { formatDuration, formatTokens } from "@/lib/api";
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function DashboardPage() {
  const { tasks, loading, error, cancelTask, refreshTasks } = useTasks();
  const [cancelling, setCancelling] = useState<string | null>(null);

  // Check if there are any running or pending tasks
  const hasActiveWaitingTasks = tasks.some(task => 
    task.status === "running" || task.status === "pending"
  );

  const handleCancelTask = async (taskId: string) => {
    try {
      setCancelling(taskId);
      await cancelTask(taskId);
    } catch (err) {
      console.error("Failed to cancel task:", err);
    } finally {
      setCancelling(null);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "pending":
        return (
          <Badge
            variant="secondary"
            className="font-mono text-xs bg-blue-100 text-blue-800 border-blue-300"
          >
            Pending
          </Badge>
        );
      case "running":
        return (
          <Badge
            variant="secondary"
            className="font-mono text-xs bg-yellow-100 text-yellow-800 border-yellow-300"
          >
            Running
          </Badge>
        );
      case "completed":
        return (
          <Badge
            variant="secondary"
            className="font-mono text-xs bg-green-100 text-green-800 border-green-300"
          >
            Completed
          </Badge>
        );
      case "failed":
        return (
          <Badge
            variant="secondary"
            className="font-mono text-xs bg-red-100 text-red-800 border-red-300"
          >
            Failed
          </Badge>
        );
      case "cancelled":
        return (
          <Badge
            variant="secondary"
            className="font-mono text-xs bg-gray-100 text-gray-800 border-gray-300"
          >
            Cancelled
          </Badge>
        );
      default:
        return null;
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="font-mono text-sm text-gray-600">Loading tasks...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b border-black">
        <div className="max-w-4xl mx-auto px-5 py-5">
          <div className="flex items-center justify-between">
            <Link
              href="/"
              className="flex items-center gap-4 hover:opacity-80 transition-opacity"
            >
              <Image
                src="/logo-removed.png"
                alt="Crux Logo"
                width={36}
                height={36}
                className="object-contain"
              />
              <div className="font-mono text-3xl font-bold tracking-[-2px] text-black">
                Crux
              </div>
            </Link>
            <nav className="flex items-center gap-8">
              <Button
                onClick={refreshTasks}
                variant="outline"
                className="font-mono border-black text-black hover:bg-black hover:text-white px-3 py-1 text-sm bg-transparent"
              >
                Refresh
              </Button>
              <Link
                href="/new-task"
                className="font-mono text-sm bg-black text-white px-4 py-2 hover:bg-white hover:text-black border border-black transition-all duration-200"
              >
                New Task
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-5 py-12">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="font-mono text-3xl text-black mb-2">
              Research Dashboard
            </h1>
            <p className="font-mono text-sm text-gray-600">
              Track your research tasks and view completed reports
            </p>
          </div>
          <Link href="/new-task">
            <Button className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-6 py-2 text-sm">
              New Task
            </Button>
          </Link>
        </div>

        {error && (
          <Alert className="mb-6 border-red-300 bg-red-50">
            <AlertDescription className="font-mono text-sm text-red-700">
              {error}
            </AlertDescription>
          </Alert>
        )}

        {/* Game Invitation Card */}
        {hasActiveWaitingTasks && (
          <div className="mb-8">
            <div className="border border-gray-300 p-6 bg-gray-50">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <h3 className="font-mono text-lg text-black mb-2">
                    🎮 Take a Break While You Wait
                  </h3>
                  <p className="font-mono text-sm text-gray-600 mb-3 leading-relaxed">
                    Your research is processing in the background. Play our classic Snake game 
                    to pass the time and return to check your results when ready.
                  </p>
                  <div className="font-mono text-xs text-gray-500">
                    Average research time: 20-80 minutes depending on mode
                  </div>
                </div>
                <div className="ml-6">
                  <Link href="/game">
                    <Button className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-6 py-3 text-sm">
                      Play Game →
                    </Button>
                  </Link>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tasks List */}
        {tasks.length === 0 ? (
          <div className="border border-gray-300 p-12 text-center">
            <h3 className="font-mono text-lg text-black mb-4">
              No research tasks yet
            </h3>
            <p className="font-mono text-sm text-gray-600 mb-6">
              Start your first research task to see it appear here
            </p>
            <Link href="/new-task">
              <Button className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-6 py-2 text-sm">
                Create First Task
              </Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {tasks.map((task) => (
              <div
                key={task.id}
                className="border border-gray-300 p-6 hover:border-black transition-colors duration-200"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      {getStatusBadge(task.status)}
                      <span className="font-mono text-xs text-gray-500 uppercase">
                        {task.mode} mode
                      </span>
                      {task.mode === "enhanced" && task.result?.metadata?.specialist_consultations && (
                        <Badge
                          variant="secondary"
                          className="font-mono text-xs bg-purple-100 text-purple-800 border-purple-300"
                          title={`Specialist consultations: ${task.result.metadata.specialist_iterations?.map((s: any, i: number) => `${i+1}: ${s.iterations} iter${s.iterations !== 1 ? 's' : ''}`).join(', ') || 'Details not available'}`}
                        >
                          {task.result.metadata.specialist_consultations} specialist{task.result.metadata.specialist_consultations !== 1 ? 's' : ''}
                          {task.result.metadata.specialist_iterations && (
                            <span className="ml-1 text-purple-600">
                              ({task.result.metadata.specialist_iterations.reduce((total: number, s: any) => total + (s.iterations || 0), 0)} total iters)
                            </span>
                          )}
                        </Badge>
                      )}
                      {(task.status === "running" ||
                        task.status === "pending") && (
                        <span className="font-mono text-xs text-blue-600">
                          {Math.round(task.progress * 100)}% -{" "}
                          {task.currentPhase}
                        </span>
                      )}
                    </div>
                    <h3 className="font-mono text-lg text-black mb-2 leading-tight">
                      {task.topic}
                    </h3>
                    <div className="font-mono text-xs text-gray-500 space-y-1">
                      <div>Started: {formatDate(task.createdAt)}</div>
                      {task.completedAt && (
                        <div className="text-green-700">
                          Completed: {formatDate(task.completedAt)}
                        </div>
                      )}
                      {task.result && (
                        <div className="text-blue-700">
                          {task.result.iterations} iterations •{" "}
                          {formatTokens(task.result.total_tokens)} •{" "}
                          {formatDuration(task.result.processing_time)}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="ml-4 flex gap-2">
                    {task.status === "completed" ? (
                      <Link href={`/task/${task.id}`}>
                        <Button
                          variant="outline"
                          className="font-mono border-black text-black hover:bg-black hover:text-white px-4 py-2 text-sm bg-transparent"
                        >
                          View Report
                        </Button>
                      </Link>
                    ) : task.status === "running" ||
                      task.status === "pending" ? (
                      <>
                        <Link href={`/task/${task.id}`}>
                          <Button
                            variant="outline"
                            className="font-mono border-black text-black hover:bg-black hover:text-white px-4 py-2 text-sm bg-transparent"
                          >
                            View Partial
                          </Button>
                        </Link>
                        <Button
                          onClick={() => handleCancelTask(task.id)}
                          disabled={cancelling === task.id}
                          variant="outline"
                          className="font-mono border-red-300 text-red-600 hover:bg-red-600 hover:text-white px-4 py-2 text-sm bg-transparent"
                        >
                          {cancelling === task.id ? "Cancelling..." : "Cancel"}
                        </Button>
                      </>
                    ) : (
                      <Button
                        variant="outline"
                        disabled
                        className="font-mono border-gray-300 text-gray-400 px-4 py-2 text-sm cursor-not-allowed bg-transparent"
                      >
                        {task.status === "failed" ? "Failed" : "Cancelled"}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Stats */}
        {tasks.length > 0 && (
          <div className="mt-12 grid md:grid-cols-4 gap-6">
            <div className="border border-gray-300 p-6 text-center">
              <div className="font-mono text-2xl text-black mb-2">
                {tasks.filter((t) => t.status === "pending").length}
              </div>
              <div className="font-mono text-sm text-gray-600">Pending</div>
            </div>
            <div className="border border-gray-300 p-6 text-center">
              <div className="font-mono text-2xl text-black mb-2">
                {tasks.filter((t) => t.status === "running").length}
              </div>
              <div className="font-mono text-sm text-gray-600">Running</div>
            </div>
            <div className="border border-gray-300 p-6 text-center">
              <div className="font-mono text-2xl text-black mb-2">
                {tasks.filter((t) => t.status === "completed").length}
              </div>
              <div className="font-mono text-sm text-gray-600">Completed</div>
            </div>
            <div className="border border-gray-300 p-6 text-center">
              <div className="font-mono text-2xl text-black mb-2">
                {tasks.length}
              </div>
              <div className="font-mono text-sm text-gray-600">Total</div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
