"use client";

import type React from "react";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  type AsyncJobResponse,
  type TaskResult,
  type SettingsResponse,
  apiClient,
} from "@/lib/api";
import { useTasks } from "@/hooks/use-tasks";

export default function NewTaskPage() {
  const [topic, setTopic] = useState("");
  const [mode, setMode] = useState<"basic" | "enhanced">("basic");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Override settings
  const [maxIters, setMaxIters] = useState<string>("");
  const [specialistMaxIters, setSpecialistMaxIters] = useState<string>("");
  const [professorMaxIters, setProfessorMaxIters] = useState<string>("");

  const router = useRouter();
  const { addTask, startPolling } = useTasks();

  // Load settings on component mount
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const settingsData = await apiClient.getSettings();
        setSettings(settingsData);
        // Set defaults from settings
        setMaxIters(settingsData.max_iters.toString());
        setSpecialistMaxIters(settingsData.specialist_max_iters.toString());
        setProfessorMaxIters(settingsData.professor_max_iters.toString());
      } catch (err) {
        console.error("Failed to load settings:", err);
      }
    };
    loadSettings();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      let response: TaskResult | AsyncJobResponse;

      // Prepare override values (only include if different from defaults and not empty)
      const overrides: any = {};

      if (maxIters && maxIters !== settings?.max_iters.toString()) {
        overrides.n_iters = parseInt(maxIters);
      }

      if (
        specialistMaxIters &&
        specialistMaxIters !== settings?.specialist_max_iters.toString()
      ) {
        overrides.specialist_max_iters = parseInt(specialistMaxIters);
      }

      if (
        professorMaxIters &&
        professorMaxIters !== settings?.professor_max_iters.toString()
      ) {
        overrides.professor_max_iters = parseInt(professorMaxIters);
      }

      // Add provider and model selection (these will need to be handled by the backend)
      if (settings) {
        overrides.llm_provider = settings.llm_provider;
        overrides.model_name = settings.model_name;
      }

      if (mode === "basic") {
        response = await apiClient.solveBasic({
          question: topic.trim(),
          ...overrides,
        });
      } else {
        response = await apiClient.solveEnhanced({
          question: topic.trim(),
          context: "Academic research and proof generation",
          ...overrides,
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

          {/* Provider Selection */}
          {settings && (
            <div className="space-y-4">
              <Label className="font-mono text-sm text-black">Provider</Label>
              <Select
                onValueChange={(value) => {
                  // When provider changes, update to the first available model for that provider
                  const newModelName =
                    value === "openai"
                      ? settings.openai_models[0]
                      : settings.openrouter_models[0];
                  setSettings({
                    ...settings,
                    llm_provider: value,
                    model_name: newModelName,
                  });
                }}
                value={settings.llm_provider}
                disabled={isSubmitting}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {settings.available_providers.map((provider) => (
                    <SelectItem key={provider} value={provider}>
                      {provider}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Model Selection */}
              <Label className="font-mono text-sm text-black">Model</Label>
              <Select
                key={`${settings.llm_provider}-model-select`}
                onValueChange={(value) => {
                  setSettings({ ...settings, model_name: value });
                }}
                value={settings.model_name}
                disabled={isSubmitting}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                  {(settings.llm_provider === "openai"
                    ? settings.openai_models
                    : settings.openrouter_models
                  ).map((model) => (
                    <SelectItem key={model} value={model}>
                      {model}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Debug info */}
              <div className="font-mono text-xs text-gray-500">
                Available models for {settings.llm_provider}:{" "}
                {(settings.llm_provider === "openai"
                  ? settings.openai_models
                  : settings.openrouter_models
                ).join(", ")}
              </div>
            </div>
          )}
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

          {/* Current Settings Display */}
          {settings && (
            <div className="border border-gray-300 p-6 bg-gray-50">
              <h3 className="font-mono text-sm text-black mb-3">
                Current Configuration
              </h3>
              <div className="grid grid-cols-2 gap-4 font-mono text-xs text-gray-600">
                <div>
                  <span className="text-black">Provider:</span>{" "}
                  {settings.llm_provider}
                </div>
                <div>
                  <span className="text-black">Model:</span>{" "}
                  {settings.model_name}
                </div>
                <div>
                  <span className="text-black">Basic Max Iterations:</span>{" "}
                  {settings.max_iters}
                </div>
                <div>
                  <span className="text-black">
                    Enhanced Specialist Iterations:
                  </span>{" "}
                  {settings.specialist_max_iters}
                </div>
                <div>
                  <span className="text-black">
                    Enhanced Professor Iterations:
                  </span>{" "}
                  {settings.professor_max_iters}
                </div>
              </div>
            </div>
          )}

          {/* Advanced Settings */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label className="font-mono text-sm text-black">
                Advanced Settings
              </Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="font-mono text-xs border-gray-300 hover:bg-gray-50"
                disabled={isSubmitting}
              >
                {showAdvanced ? "Hide" : "Show"} Advanced
              </Button>
            </div>

            {showAdvanced && (
              <div className="border border-gray-300 p-6 space-y-4 bg-orange-50">
                <p className="font-mono text-xs text-orange-600 mb-4">
                  Override default settings for this task only. Leave empty to
                  use system defaults.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label className="font-mono text-xs text-black">
                      Basic Max Iterations
                    </Label>
                    <Input
                      type="number"
                      min="1"
                      max="10"
                      value={maxIters}
                      onChange={(e) => setMaxIters(e.target.value)}
                      placeholder={settings?.max_iters.toString() || "4"}
                      className="font-mono text-xs border-gray-300 focus:border-orange-400"
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label className="font-mono text-xs text-black">
                      Specialist Max Iterations
                    </Label>
                    <Input
                      type="number"
                      min="1"
                      max="8"
                      value={specialistMaxIters}
                      onChange={(e) => setSpecialistMaxIters(e.target.value)}
                      placeholder={
                        settings?.specialist_max_iters.toString() || "4"
                      }
                      className="font-mono text-xs border-gray-300 focus:border-orange-400"
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label className="font-mono text-xs text-black">
                      Professor Max Iterations
                    </Label>
                    <Input
                      type="number"
                      min="1"
                      max="10"
                      value={professorMaxIters}
                      onChange={(e) => setProfessorMaxIters(e.target.value)}
                      placeholder={
                        settings?.professor_max_iters.toString() || "3"
                      }
                      className="font-mono text-xs border-gray-300 focus:border-orange-400"
                      disabled={isSubmitting}
                    />
                  </div>
                </div>

                <div className="font-mono text-xs text-gray-600 space-y-1">
                  <p>
                    • <strong>Basic Mode</strong> uses only "Basic Max
                    Iterations"
                  </p>
                  <p>
                    • <strong>Enhanced Mode</strong> uses both "Specialist" and
                    "Professor" iterations
                  </p>
                  <p>
                    • Higher iterations = more thorough analysis but longer
                    processing time
                  </p>
                </div>
              </div>
            )}
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
