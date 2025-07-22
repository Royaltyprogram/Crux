"use client";

import type React from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { type AsyncJobResponse, type TaskResult, apiClient } from "@/lib/api";
import { useTasks } from "@/hooks/use-tasks";

export default function NewTaskPage() {
  const [topic, setTopic] = useState("");
  const [mode, setMode] = useState<"basic" | "enhanced">("basic");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const { addTask, startPolling } = useTasks();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      let response: TaskResult | AsyncJobResponse;

      if (mode === "basic") {
        response = await apiClient.solveBasic({
          question: topic.trim(),
        });
      } else {
        response = await apiClient.solveEnhanced({
          question: topic.trim(),
          context: "Academic research and proof generation",
        });
      }

      // In async mode, a job_id is returned
      if ("job_id" in response) {
        const newTask = {
          id: response.job_id,
          topic: topic.trim(),
          mode,
          status: "pending" as const,
          createdAt: response.created_at,
          progress: 0,
          currentPhase: "Initializing...",
        };

        addTask(newTask);
        startPolling(response.job_id);
        router.push("/dashboard");
      } else {
        // Sync mode (not typically used)
        const taskId = Math.random().toString(36).substr(2, 9);
        const newTask = {
          id: taskId,
          topic: topic.trim(),
          mode,
          status: "completed" as const,
          createdAt: new Date().toISOString(),
          completedAt: new Date().toISOString(),
          progress: 1,
          currentPhase: "Completed",
          result: response,
        };

        addTask(newTask);
        router.push("/dashboard");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit task");
    } finally {
      setIsSubmitting(false);
    }
  };

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
              <Link
                href="/dashboard"
                className="font-mono text-sm text-black hover:bg-black hover:text-white px-3 py-1 transition-all duration-200"
              >
                Dashboard
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-2xl mx-auto px-5 py-12">
        <div className="mb-8">
          <h1 className="font-mono text-3xl text-black mb-4">
            New Research Task
          </h1>
          <p className="font-mono text-sm text-gray-600 leading-relaxed">
            Submit your research topic or thesis statement. Our AI agent will
            transform it into a comprehensive proof and analysis.
          </p>
        </div>

        {error && (
          <Alert className="mb-6 border-red-300 bg-red-50">
            <AlertDescription className="font-mono text-sm text-red-700">
              {error}
            </AlertDescription>
          </Alert>
        )}

        <form onSubmit={handleSubmit} className="space-y-8">
          {/* Topic Input */}
          <div className="space-y-3">
            <Label className="font-mono text-sm text-black">
              Research Topic
            </Label>
            <Textarea
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Enter your research topic or thesis statement here..."
              className="font-mono text-sm min-h-32 border-black focus:ring-0 focus:border-black resize-none"
              required
              disabled={isSubmitting}
            />
            <p className="font-mono text-xs text-gray-500">
              Example: "The relationship between quantum entanglement and
              information theory"
            </p>
          </div>

          {/* Mode Selection */}
          <div className="space-y-4">
            <Label className="font-mono text-sm text-black">
              Research Mode
            </Label>
            <RadioGroup
              value={mode}
              onValueChange={(value) => setMode(value as "basic" | "enhanced")}
              className="space-y-4"
              disabled={isSubmitting}
            >
              <div className="border border-gray-300 p-6 space-y-3">
                <div className="flex items-center space-x-3">
                  <RadioGroupItem
                    value="basic"
                    id="basic"
                    className="border-black"
                  />
                  <Label
                    htmlFor="basic"
                    className="font-mono text-sm text-black cursor-pointer"
                  >
                    Basic Mode
                  </Label>
                </div>
                <p className="font-mono text-xs text-gray-600 leading-relaxed ml-6">
                  Single Self-Evolve loop with focused analysis (~20 minutes).
                  Perfect for initial exploration and concept validation.
                </p>
              </div>

              <div className="border border-gray-300 p-6 space-y-3">
                <div className="flex items-center space-x-3">
                  <RadioGroupItem
                    value="enhanced"
                    id="enhanced"
                    className="border-black"
                  />
                  <Label
                    htmlFor="enhanced"
                    className="font-mono text-sm text-black cursor-pointer"
                  >
                    Enhanced Mode
                  </Label>
                </div>
                <p className="font-mono text-xs text-gray-600 leading-relaxed ml-6">
                  Professor agent with autonomous specialist consultations (~1
                  hour 20 minutes). Includes detailed proofs, theoretical
                  explanations, and multi-domain analysis.
                </p>
              </div>
            </RadioGroup>
          </div>

          {/* Submit Button */}
          <div className="pt-4">
            <Button
              type="submit"
              disabled={!topic.trim() || isSubmitting}
              className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-8 py-3 text-sm w-full disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? "Starting Research..." : "Start Research"}
            </Button>
          </div>
        </form>

        {/* Info Box */}
        <div className="mt-12 border border-gray-300 p-6 bg-gray-50">
          <h3 className="font-mono text-sm text-black mb-3">
            What happens next?
          </h3>
          <ul className="font-mono text-xs text-gray-600 space-y-2 leading-relaxed">
            <li>• Your task will be queued and begin processing immediately</li>
            <li>• You can track real-time progress on your dashboard</li>
            <li>• Multiple tasks can run simultaneously</li>
            <li>• You'll receive a detailed research report upon completion</li>
            <li>• Tasks can be cancelled if needed</li>
          </ul>
        </div>
      </main>
    </div>
  );
}
