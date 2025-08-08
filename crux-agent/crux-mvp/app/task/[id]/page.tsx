"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Progress } from "@/components/ui/progress";
import { useTasks, type Task } from "@/hooks/use-tasks";
import { formatDuration, formatTokens, apiClient, getModelContextLimit, detectTaskMode, type ContextLimitsResponse } from "@/lib/api";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

// Custom markdown component with syntax highlighting
const MarkdownRenderer = ({
  content,
  maxLength,
}: {
  content: string;
  maxLength?: number;
}) => {
  const [copiedCode, setCopiedCode] = useState<string>("");

  const copyToClipboard = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCode(code);
      setTimeout(() => setCopiedCode(""), 2000);
    } catch (err) {
      console.error("Failed to copy: ", err);
    }
  };

  // \( … \), \[ … \] 형태의 수식을 remark-math 형식으로 변환
  const normalizeMath = (src: string) => {
    // 코드 블록과 인라인 코드를 임시로 저장하여 보호
    const codeBlocks: string[] = [];
    const inlineCode: string[] = [];
    const codeBlockPlaceholder = "___CODE_BLOCK_PLACEHOLDER___";
    const inlineCodePlaceholder = "___INLINE_CODE_PLACEHOLDER___";

    // 코드 블록 추출 및 보호
    let withProtectedCode = src.replace(/```[\s\S]*?```/g, (match) => {
      codeBlocks.push(match);
      return `${codeBlockPlaceholder}${codeBlocks.length - 1}`;
    });

    // 인라인 코드 추출 및 보호
    withProtectedCode = withProtectedCode.replace(/`[^`\n]+`/g, (match) => {
      inlineCode.push(match);
      return `${inlineCodePlaceholder}${inlineCode.length - 1}`;
    });

    // 수식 변환 및 기타 정규화 (코드 블록 제외)
    let normalized = withProtectedCode
      // LaTeX 수식 구분자 변환
      .replace(/\\\[/g, "\n$$\n")
      .replace(/\\\]/g, "\n$$\n")
      .replace(/\\\(/g, "$")
      .replace(/\\\)/g, "$")
      // 일반적인 LaTeX 명령어들 정리
      .replace(/\\big[gG]?[\\ ]*\\gcd/g, "\\gcd")
      .replace(/\\big[gG]?[\\ ]*\\lcm/g, "\\lcm")
      .replace(/\\big[gG]?[\\ ]*\\max/g, "\\max")
      .replace(/\\big[gG]?[\\ ]*\\min/g, "\\min")
      // 지원되지 않는 명령어들 정리
      .replace(/\\Bigl?[\\/\\|]/g, "")
      .replace(/\\Bigr?[\\/\\|]/g, "")
      .replace(/\\!+/g, "")
      // 여러 연속된 공백을 단일 공백으로
      .replace(/[ \t]+/g, " ")
      // 수식 앞뒤 공백 정리
      .replace(/\$\s+/g, "$")
      .replace(/\s+\$/g, "$")
      .replace(/\$\$\s+/g, "$$\n")
      .replace(/\s+\$\$/g, "\n$$");

    // Handle custom XML-like tags (escape them to prevent React errors)
    normalized = normalized
      .replace(/<answer>/gi, "**[ANSWER]**")
      .replace(/<\/answer>/gi, "**[/ANSWER]**")
      .replace(/<thinking>/gi, "**[THINKING]**")
      .replace(/<\/thinking>/gi, "**[/THINKING]**")
      .replace(/<reasoning>/gi, "**[REASONING]**")
      .replace(/<\/reasoning>/gi, "**[/REASONING]**")
      .replace(/<solution>/gi, "**[SOLUTION]**")
      .replace(/<\/solution>/gi, "**[/SOLUTION]**");

    // 인라인 코드 복원
    let restored = normalized.replace(
      new RegExp(`${inlineCodePlaceholder}(\\d+)`, "g"),
      (_, index) => inlineCode[parseInt(index)]
    );

    // 코드 블록 복원
    restored = restored.replace(
      new RegExp(`${codeBlockPlaceholder}(\\d+)`, "g"),
      (_, index) => codeBlocks[parseInt(index)]
    );

    return restored;
  };

  const normalized = normalizeMath(content);

  const displayContent =
    maxLength && normalized.length > maxLength
      ? normalized.substring(0, maxLength) + "..."
      : normalized;

  return (
    <div className="prose prose-sm max-w-none prose-headings:text-black prose-p:text-gray-700 prose-strong:text-black prose-code:text-purple-600 prose-code:bg-purple-50 prose-pre:bg-gray-900">
      <style jsx global>{`
        .katex { font-size: 1.1em; }
        .katex-display { 
          margin: 1.5em 0; 
          text-align: center;
        }
        .katex-display > .katex {
          display: inline-block;
          text-align: initial;
        }
        .katex .mord {
          color: inherit;
        }
        .katex-error {
          color: #cc0000;
          background-color: #ffeeee;
          padding: 2px 4px;
          border-radius: 3px;
        }
      `}</style>
      <ReactMarkdown
        remarkPlugins={[remarkMath, remarkGfm]}
        rehypePlugins={[
          [rehypeKatex, { 
            strict: false, 
            output: "html",
            displayMode: false,
            throwOnError: false,
            errorColor: '#cc0000',
            macros: {
              "\\RR": "\\mathbb{R}",
              "\\NN": "\\mathbb{N}",
              "\\ZZ": "\\mathbb{Z}",
              "\\QQ": "\\mathbb{Q}",
              "\\CC": "\\mathbb{C}"
            }
          }],
          rehypeRaw,
        ]}
        components={{
          code(props) {
            const { children, className, ...rest } = props;
            const match = /language-(\w+)/.exec(className || "");
            const isInline = !match;
            const codeString = String(children).replace(/\n$/, "");

            return isInline ? (
              <code className={className} {...rest}>
                {children}
              </code>
            ) : (
              <div className="relative group">
                <button
                  onClick={() => copyToClipboard(codeString)}
                  className="absolute top-2 right-2 px-2 py-1 text-xs bg-gray-700 text-white rounded opacity-0 group-hover:opacity-100 transition-opacity duration-200 hover:bg-gray-600 z-10"
                >
                  {copiedCode === codeString ? "Copied!" : "Copy"}
                </button>
                <SyntaxHighlighter
                  style={oneDark as any}
                  language={match[1]}
                  PreTag="div"
                  className="text-sm"
                >
                  {codeString}
                </SyntaxHighlighter>
              </div>
            );
          },
        }}
      >
        {displayContent}
      </ReactMarkdown>
    </div>
  );
};

// Types for better type safety
interface EvolutionHistoryItem {
  iteration: number;
  prompt: string;
  output: string;
  feedback: string;
  should_stop: boolean;
  reasoning_summary?: string;
  evaluator_reasoning_summary?: string;
  refiner_reasoning_summary?: string;
}

interface SpecialistResult {
  specialization: string;
  task: string;
  output: string;
  iterations: number;
  converged: boolean;
  total_tokens: number;
}

interface TaskMetadata {
  runner: "basic" | "enhanced";
  converged: boolean;
  evolution_history?: EvolutionHistoryItem[];
  approach?: string;
  specialist_consultations?: number;
  function_calling_used?: boolean;
  specialist_results?: SpecialistResult[];
}

export default function TaskDetailPage() {
  const params = useParams();
  const [cancelling, setCancelling] = useState(false);
  const router = useRouter();

  const handleCancelTask = async (taskId: string) => {
    if (cancelling) return;
    setCancelling(true);
    // Attempt backend cancel but proceed regardless of outcome
    try {
      await cancelTask(taskId);
    } catch (_) {/* ignore */}

    // Always attempt purge locally (will also hit backend purge endpoint)
    try {
      await purgeTask(taskId);
    } catch (_) {/* ignore */}

    toast.success("Task removed");
    router.push("/dashboard");

    setCancelling(false);
  };
  const { tasks, cancelTask, purgeTask, refreshTasks, fetchFullTaskDetails } = useTasks();
  const [loading, setLoading] = useState(true);
  const [continuing, setContinuing] = useState(false);
  const [fullTask, setFullTask] = useState<Task | null>(null);
  const [fetchingDetails, setFetchingDetails] = useState(false);
  const [contextLimits, setContextLimits] = useState<ContextLimitsResponse | null>(null);

  const [taskFromApi, setTaskFromApi] = useState<Task | null>(null);
  const task = fullTask || taskFromApi || tasks.find((t) => t.id === params.id);

  // Debug: Log task data
  useEffect(() => {
    if (task) {
      console.log('Task data:', {
        id: task.id,
        status: task.status,
        progress: task.progress,
        currentPhase: task.currentPhase,
        hasPartialResults: !!task.partial_results,
        partialResults: task.partial_results,
        hasResult: !!task.result
      });
    }
  }, [task]);

  const handleContinueTask = async () => {
    if (!task || continuing) return;
    
    setContinuing(true);
    try {
      const response = await apiClient.continueTask(task.id, 1); // Add 1 more iteration
      
      // Add the new continuation task to the task list
      const newTask = {
        id: response.job_id,
        topic: `${task.topic} (Continued +1)`,
        mode: task.mode,
        status: "pending" as const,
        createdAt: response.created_at,
        progress: 0,
        currentPhase: "Initializing",
      };
      
      // Get the current tasks from localStorage and add the new one
      const storedTasks = localStorage.getItem("crux-tasks");
      const currentTasks = storedTasks ? JSON.parse(storedTasks) : [];
      const updatedTasks = [newTask, ...currentTasks];
      localStorage.setItem("crux-tasks", JSON.stringify(updatedTasks));
      
      toast.success("Task continuation started successfully!");
      await refreshTasks();
      router.push(`/task/${response.job_id}`);
    } catch (error) {
      console.error("Error continuing task:", error);
      toast.error("Failed to continue task. Please try again.");
    } finally {
      setContinuing(false);
    }
  };

  // Debug: Clear cache and force refresh
  useEffect(() => {
    // Add debug function to window for easy access
    (window as any).clearTaskCache = () => {
      localStorage.removeItem("crux-tasks");
      window.location.reload();
    };
    
    // Add debug function to force fetch full details
    (window as any).forceFetchDetails = async (taskId: string) => {
      console.log("Force fetching details for task:", taskId);
      setFetchingDetails(true);
      try {
        const fullDetails = await fetchFullTaskDetails(taskId);
        if (fullDetails) {
          console.log("Full details fetched:", fullDetails);
          setFullTask(fullDetails);
        }
      } catch (error) {
        console.error("Failed to fetch full task details:", error);
      } finally {
        setFetchingDetails(false);
      }
    };
  }, [fetchFullTaskDetails]);

  // Fetch task from API if not found in cache
  useEffect(() => {
    const loadTaskFromApi = async () => {
      const taskId = params.id as string;
      
      // If we don't have the task in cache or from previous API calls, fetch it
      if (!fullTask && !taskFromApi && !tasks.find(t => t.id === taskId)) {
        console.log("Task not found in cache, fetching from API:", taskId);
        setFetchingDetails(true);
        try {
          const jobResponse = await apiClient.getJob(taskId, {
            include_evolution_history: true,
            include_partial_results: true, // Include partial results for running tasks
          });
          
          // Debug: Log job response details for mode detection
          console.log("JobResponse for mode detection:", {
            status: jobResponse.status,
            result_metadata_runner: jobResponse.result?.metadata?.runner,
            result_metadata_specialist_consultations: jobResponse.result?.metadata?.specialist_consultations,
            partial_results_metadata_runner: jobResponse.partial_results?.metadata?.runner,
            partial_results_metadata_specialist_consultations: jobResponse.partial_results?.metadata?.specialist_consultations,
            metadata_runner: jobResponse.metadata?.runner,
            metadata_specialist_consultations: jobResponse.metadata?.specialist_consultations,
            job_params_mode: jobResponse.job_params?.mode,
            job_params_runner: jobResponse.job_params?.runner,
            full_job_params: jobResponse.job_params
          });
          
          const taskMode = detectTaskMode(jobResponse);
          console.log("Detected task mode:", taskMode);

          const taskFromApiResponse: Task = {
            id: taskId,
            topic: "Task from API", // We don't have the original topic, will be displayed from result
            mode: taskMode,
            status: jobResponse.status,
            createdAt: jobResponse.created_at || new Date().toISOString(),
            startedAt: jobResponse.started_at,
            completedAt: jobResponse.completed_at,
            progress: jobResponse.progress,
            currentPhase: jobResponse.current_phase,
            modelName: jobResponse.model_name,
            providerName: jobResponse.provider_name,
            result: jobResponse.result,
            partial_results: jobResponse.partial_results, // Include partial results
          };
          
          console.log("Task fetched from API:", taskFromApiResponse);
          setTaskFromApi(taskFromApiResponse);
        } catch (error) {
          console.error("Failed to fetch task from API:", error);
        } finally {
          setFetchingDetails(false);
        }
      }
    };
    
    loadTaskFromApi();
  }, [params.id, fullTask, taskFromApi, tasks]);

  // Fetch full task details if needed
  useEffect(() => {
    const loadFullDetails = async () => {
      if (!task || fullTask || fetchingDetails) return;
      
      // Always try to fetch full details for completed tasks to ensure we have complete data
      const needsFullDetails = task.status === "completed" && 
        (!task.result?.output || !task.result?.metadata?.evolution_history);
      
      console.log("Task analysis:", {
        taskId: task.id,
        status: task.status,
        hasOutput: !!task.result?.output,
        hasEvolutionHistory: !!task.result?.metadata?.evolution_history,
        needsFullDetails
      });
      
      if (needsFullDetails) {
        console.log("Fetching full details for task:", task.id);
        setFetchingDetails(true);
        try {
          const fullDetails = await fetchFullTaskDetails(task.id);
          if (fullDetails) {
            console.log("Full details received, output length:", fullDetails.result?.output?.length || 0);
            setFullTask(fullDetails);
          }
        } catch (error) {
          console.error("Failed to fetch full task details:", error);
        } finally {
          setFetchingDetails(false);
        }
      }
    };
    
    loadFullDetails();
  }, [task, fullTask, fetchingDetails, fetchFullTaskDetails]);

  // Fetch context limits configuration
  useEffect(() => {
    const loadContextLimits = async () => {
      try {
        const limits = await apiClient.getContextLimits();
        setContextLimits(limits);
      } catch (error) {
        console.error("Failed to fetch context limits:", error);
        // Continue without context limits (fallbacks will be used)
      }
    };
    
    loadContextLimits();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 1000);
    return () => clearTimeout(timer);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="font-mono text-sm text-gray-600">Loading...</div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="min-h-screen bg-white">
        <header className="border-b border-black">
          <div className="max-w-4xl mx-auto px-5 py-5">
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
          </div>
        </header>
        <main className="max-w-4xl mx-auto px-5 py-12 text-center">
          <h1 className="font-mono text-2xl text-black mb-4">Task Not Found</h1>
          <Link href="/dashboard">
            <Button className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-6 py-2 text-sm">
              Back to Dashboard
            </Button>
          </Link>
        </main>
      </div>
    );
  }

  // For running tasks, show partial results if available
  if (task.status !== "completed") {
    // Check if we have partial results to show
    const hasPartialResults = task.partial_results && 
      (task.partial_results.evolution_history?.length > 0 || task.partial_results.output);
    
    if (task.status === "running" && hasPartialResults) {
      // Show running task with partial results - similar layout to completed task
      const partialResult = task.partial_results;
      const evolutionHistory = partialResult.evolution_history || [];
      const isEnhanced = task.mode === "enhanced";
      const fullQuestion = partialResult.problem?.question || task.topic;
      
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
          <main className="max-w-6xl mx-auto px-5 py-12">
            {/* Task Header */}
            <div className="mb-8">
              <div className="flex items-center gap-3 mb-4">
                <Badge
                  variant="secondary"
                  className="font-mono text-xs bg-blue-100 text-blue-800 border-blue-300"
                >
                  Running - {Math.round(task.progress * 100)}%
                </Badge>
                <span className="font-mono text-xs text-gray-500 uppercase">
                  {task.mode} mode
                </span>
                <Badge variant="outline" className="font-mono text-xs bg-orange-50 text-orange-700 border-orange-300">
                  {evolutionHistory.length} iteration{evolutionHistory.length !== 1 ? 's' : ''} so far
                </Badge>
              </div>
              <h1 className="font-mono text-3xl text-black mb-2 leading-tight">
                {fullQuestion}
              </h1>
              <div className="font-mono text-sm text-gray-600 space-y-1">
                <div>Started: {new Date(task.createdAt).toLocaleString()}</div>
                <div>Current phase: {task.currentPhase}</div>
                {task.modelName && (
                  <div>Model: {task.modelName}</div>
                )}
              </div>
              
              {/* Progress bar */}
              <div className="mt-4">
                <div className="font-mono text-sm text-blue-600 mb-2">
                  Progress: {Math.round(task.progress * 100)}%
                </div>
                <Progress value={task.progress * 100} className="w-full" />
              </div>
            </div>
            
            {/* Partial Results Card */}
            <Card>
              <CardHeader>
                <CardTitle className="font-mono text-lg flex items-center gap-2">
                  <span>🔄</span>
                  Research Progress (Live Updates)
                </CardTitle>
              </CardHeader>
              <CardContent>
                {/* Thinking Process Section */}
                {evolutionHistory.length > 0 && (
                  <div className="mb-6">
                    <Accordion type="single" collapsible className="w-full">
                      <AccordionItem value="thinking-process">
                        <AccordionTrigger className="font-mono text-sm text-gray-600 hover:text-black">
                          <div className="flex items-center gap-2">
                            <span>🧠</span>
                            <span>Thinking Process ({evolutionHistory.length} iterations)</span>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent className="pt-4">
                          <div className="space-y-4">
                            <h3 className="font-mono text-sm font-bold text-gray-800">
                              {isEnhanced ? "Professor's" : "Generator's"} Progress
                            </h3>
                            <div className="space-y-3">
                              {evolutionHistory.map((iteration, index) => (
                                <div
                                  key={index}
                                  className="border border-gray-200 rounded-lg p-4"
                                >
                                  <div className="flex items-center gap-2 mb-3">
                                    <div className="w-3 h-3 bg-blue-500 rounded-full" />
                                    <span className="font-mono text-sm font-bold text-gray-800">
                                      Iteration {iteration.iteration}
                                    </span>
                                    <Badge
                                      variant="outline"
                                      className="font-mono text-xs"
                                    >
                                      {index === evolutionHistory.length - 1 ? "Latest" : "Completed"}
                                    </Badge>
                                  </div>
                                  <div className="bg-blue-50 p-3 rounded">
                                    <div className="font-mono text-xs text-blue-600 mb-1">
                                      {isEnhanced
                                        ? "Professor's Response:"
                                        : "Generator's Response:"}
                                    </div>
                                    <MarkdownRenderer
                                      content={iteration.output}
                                      // No maxLength restriction for partial results - show full content
                                    />
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    </Accordion>
                  </div>
                )}
                
                {/* Current output if available */}
                {partialResult.output && (
                  <div className="mb-6">
                    <h3 className="font-mono text-sm font-bold text-gray-800 mb-4">
                      Current Progress
                    </h3>
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                      <div className="font-mono text-xs text-yellow-800 mb-2">
                        ⚠️ This is a work-in-progress. The final result may differ.
                      </div>
                      <MarkdownRenderer content={partialResult.output} maxLength={3000} />
                    </div>
                  </div>
                )}
                
                {/* Token Usage Section for Running Tasks */}
                {partialResult && (
                  <div className="mb-6">
                    <Accordion type="single" collapsible className="w-full">
                      <AccordionItem value="token-usage">
                        <AccordionTrigger className="font-mono text-sm text-gray-600 hover:text-black">
                          <div className="flex items-center gap-2">
                            <span>📊</span>
                            <span>Token Usage & Context Management (Live)</span>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent className="pt-4">
                          <div className="space-y-4">
                            {/* Total Token Usage */}
                            <div className="border border-gray-200 rounded-lg p-4">
                              <h4 className="font-mono text-sm font-bold text-gray-800 mb-3">Total Token Usage</h4>
                              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                                <div className="text-center">
                                  <div className="font-mono text-lg font-bold text-blue-600">
                                    {formatTokens(partialResult.total_tokens || 0)}
                                  </div>
                                  <div className="font-mono text-xs text-gray-500">Total Tokens</div>
                                </div>
                                {isEnhanced && partialResult.metadata?.professor_tokens && (
                                  <div className="text-center">
                                    <div className="font-mono text-lg font-bold text-green-600">
                                      {formatTokens(partialResult.metadata.professor_tokens)}
                                    </div>
                                    <div className="font-mono text-xs text-gray-500">Professor</div>
                                  </div>
                                )}
                                <div className="text-center">
                                  <div className="font-mono text-lg font-bold text-amber-600">
                                    {formatTokens(partialResult.metadata?.reasoning_tokens || 0)}
                                  </div>
                                  <div className="font-mono text-xs text-gray-500">Reasoning</div>
                                </div>
                                {isEnhanced && partialResult.metadata?.specialist_tokens && (
                                  <div className="text-center">
                                    <div className="font-mono text-lg font-bold text-purple-600">
                                      {formatTokens(partialResult.metadata.specialist_tokens)}
                                    </div>
                                    <div className="font-mono text-xs text-gray-500">Specialists</div>
                                  </div>
                                )}
                                <div className="text-center">
                                  <div className="font-mono text-lg font-bold text-orange-600">
                                    {formatTokens(Math.floor((partialResult.total_tokens || 0) / Math.max(partialResult.iterations || 1, 1)))}
                                  </div>
                                  <div className="font-mono text-xs text-gray-500">Avg/Iteration</div>
                                </div>
                              </div>
                            </div>

                            {/* Context Limits */}
                            <div className="border border-gray-200 rounded-lg p-4">
                              <h4 className="font-mono text-sm font-bold text-gray-800 mb-3">Context Limits & Usage</h4>
                              <div className="space-y-3">
                                {/* Model Context Limit */}
                                <div className="flex justify-between items-center">
                                  <span className="font-mono text-sm text-gray-600">Model Context Limit:</span>
                                  <span className="font-mono text-sm font-bold">
                                    {getModelContextLimit(task.modelName, task.providerName, contextLimits).toLocaleString()} tokens
                                  </span>
                                </div>
                                
                                {/* Peak Usage Estimate */}
                                <div className="flex justify-between items-center">
                                  <span className="font-mono text-sm text-gray-600">Current Usage (est.):</span>
                                  <span className="font-mono text-sm font-bold">
                                    {(partialResult.total_tokens || 0).toLocaleString()} tokens
                                  </span>
                                </div>
                                
                                {/* Context Pressure Indicator */}
                                <div className="flex justify-between items-center">
                                  <span className="font-mono text-sm text-gray-600">Context Pressure:</span>
                                  <div className="flex items-center gap-2">
                                    {(() => {
                                      const contextLimit = getModelContextLimit(task.modelName, task.providerName, contextLimits);
                                      const currentUsage = partialResult.total_tokens || 0;
                                      const pressure = (currentUsage / contextLimit) * 100;
                                      
                                      return (
                                        <>
                                          <div className={`w-20 h-2 rounded-full ${
                                            pressure < 50 ? 'bg-green-200' :
                                            pressure < 80 ? 'bg-yellow-200' : 'bg-red-200'
                                          }`}>
                                            <div className={`h-full rounded-full ${
                                              pressure < 50 ? 'bg-green-500' :
                                              pressure < 80 ? 'bg-yellow-500' : 'bg-red-500'
                                            }`} style={{ width: `${Math.min(pressure, 100)}%` }}></div>
                                          </div>
                                          <span className={`font-mono text-xs ${
                                            pressure < 50 ? 'text-green-600' :
                                            pressure < 80 ? 'text-yellow-600' : 'text-red-600'
                                          }`}>
                                            {pressure.toFixed(1)}%
                                          </span>
                                        </>
                                      );
                                    })()}
                                  </div>
                                </div>
                              </div>
                            </div>

                            {/* Context Management Indicators */}
                            <div className="border border-gray-200 rounded-lg p-4">
                              <h4 className="font-mono text-sm font-bold text-gray-800 mb-3">Context Management</h4>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="flex items-center gap-2">
                                  <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                                  <span className="font-mono text-sm text-gray-600">
                                    Task in progress
                                  </span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <div className={`w-3 h-3 rounded-full ${(partialResult.iterations || 0) > 3 ? 'bg-yellow-500' : 'bg-green-500'}`}></div>
                                  <span className="font-mono text-sm text-gray-600">
                                    {(partialResult.iterations || 0) > 3 ? 'Extended reasoning' : 'Standard reasoning'}
                                  </span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <div className="w-3 h-3 rounded-full bg-orange-500"></div>
                                  <span className="font-mono text-sm text-gray-600">
                                    {partialResult.iterations || 0} iterations so far
                                  </span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                                  <span className="font-mono text-sm text-gray-600">
                                    Live monitoring active
                                  </span>
                                </div>
                              </div>
                              
                              <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded">
                                <div className="font-mono text-xs text-blue-800">
                                  📊 Token usage is being tracked in real-time. Final numbers may vary slightly upon completion.
                                </div>
                              </div>
                            </div>
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    </Accordion>
                  </div>
                )}
                
                {/* Status message */}
                <div className="text-center py-4">
                  <div className="font-mono text-sm text-gray-600">
                    Task is still running... This page will update automatically as progress is made.
                  </div>
                </div>
              </CardContent>
            </Card>
            
            {/* Actions */}
            <div className="mt-8 flex gap-4">
              <Link href="/dashboard">
                <Button
                  variant="outline"
                  className="font-mono border-black text-black hover:bg-black hover:text-white px-6 py-2 text-sm bg-transparent"
                >
                  Back to Dashboard
                </Button>
              </Link>
              <Button
                onClick={() => handleCancelTask(task.id)}
                disabled={cancelling}
                variant="outline"
                className="font-mono border-red-300 text-red-600 hover:bg-red-600 hover:text-white px-6 py-2 text-sm bg-transparent"
              >
                {cancelling ? "Cancelling..." : "Cancel Task"}
              </Button>
            </div>
          </main>
        </div>
      );
    }
    
    // Enhanced view for non-completed tasks (even without partial results)
    return (
      <div className="min-h-screen bg-white">
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
        
        <main className="max-w-4xl mx-auto px-5 py-12">
          {/* Task Header */}
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-4">
              <Badge
                variant="secondary"
                className={`font-mono text-xs ${
                  task.status === "failed" 
                    ? "bg-red-100 text-red-800 border-red-300"
                    : task.status === "running"
                    ? "bg-blue-100 text-blue-800 border-blue-300" 
                    : "bg-yellow-100 text-yellow-800 border-yellow-300"
                }`}
              >
                {task.status === "failed" ? "Failed" : 
                 task.status === "running" ? `Running - ${Math.round(task.progress * 100)}%` :
                 task.status === "pending" ? "Pending" : task.status}
              </Badge>
              <span className="font-mono text-xs text-gray-500 uppercase">
                {task.mode} mode
              </span>
              {task.modelName && (
                <Badge variant="outline" className="font-mono text-xs">
                  {task.modelName}
                </Badge>
              )}
            </div>
            
            <h1 className="font-mono text-3xl text-black mb-2 leading-tight">
              {task.status === "failed" ? "Task Failed" : 
               task.topic === "Task from API" ? "Research Task" : task.topic}
            </h1>
            
            <div className="font-mono text-sm text-gray-600 space-y-1">
              <div>Started: {new Date(task.createdAt).toLocaleString()}</div>
              {task.status === "running" && task.currentPhase && (
                <div className="text-blue-700">Current phase: {task.currentPhase}</div>
              )}
              {task.modelName && (
                <div>Model: {task.modelName}</div>
              )}
            </div>
          </div>
          
          {/* Status Card */}
          <Card>
            <CardHeader>
              <CardTitle className="font-mono text-lg flex items-center gap-2">
                <span>{task.status === "failed" ? "❌" : task.status === "running" ? "⏳" : "⏸️"}</span>
                {task.status === "failed" ? "Task Failed" : 
                 task.status === "running" ? "Task In Progress" : "Task Processing"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {task.status === "failed" ? (
                <div className="text-center py-8">
                  <div className="font-mono text-sm text-red-600 mb-4">
                    This research task encountered an error during processing.
                  </div>
                  {task.error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-left">
                      <div className="font-mono text-xs text-red-800 mb-2">Error Details:</div>
                      <div className="font-mono text-sm text-red-700">{task.error}</div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Progress Section */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-mono text-sm text-gray-600">Progress</span>
                      <span className="font-mono text-sm font-bold text-blue-600">
                        {Math.round(task.progress * 100)}%
                      </span>
                    </div>
                    <Progress value={task.progress * 100} className="w-full" />
                  </div>
                  
                  {/* Current Phase */}
                  {task.currentPhase && (
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <div className="font-mono text-xs text-blue-600 mb-1">Current Phase:</div>
                      <div className="font-mono text-sm text-blue-800">{task.currentPhase}</div>
                    </div>
                  )}
                  
                  {/* Status Information */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                      <div className="font-mono text-xs text-gray-600 mb-1">Mode:</div>
                      <div className="font-mono text-sm text-gray-800 capitalize">{task.mode}</div>
                    </div>
                    {task.modelName && (
                      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <div className="font-mono text-xs text-gray-600 mb-1">Model:</div>
                        <div className="font-mono text-sm text-gray-800">{task.modelName}</div>
                      </div>
                    )}
                  </div>
                  
                  {/* Status Message */}
                  <div className="text-center py-4">
                    <div className="font-mono text-sm text-gray-600">
                      {task.status === "running" 
                        ? "Task is actively running... This page will update automatically as progress is made."
                        : task.status === "pending"
                        ? "Task is queued and will start shortly..."
                        : "Task is being processed..."}
                    </div>
                    <div className="font-mono text-xs text-gray-500 mt-2">
                      Estimated completion time varies based on task complexity (typically 20-80 minutes)
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
          
          {/* Actions */}
          <div className="mt-8 flex gap-4">
            <Link href="/dashboard">
              <Button
                variant="outline"
                className="font-mono border-black text-black hover:bg-black hover:text-white px-6 py-2 text-sm bg-transparent"
              >
                Back to Dashboard
              </Button>
            </Link>
            <Link href="/new-task">
              <Button className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-6 py-2 text-sm">
                Start New Research
              </Button>
            </Link>
            <Button
              onClick={() => handleCancelTask(task.id)}
              disabled={cancelling}
              variant="outline"
              className="font-mono border-red-300 text-red-600 hover:bg-red-600 hover:text-white px-6 py-2 text-sm bg-transparent"
            >
              {cancelling ? "Cancelling..." : "Cancel Task"}
            </Button>
          </div>
        </main>
      </div>
    );
  }

  const result = task.result;
  const metadata = (result?.metadata || {}) as TaskMetadata;
  const evolutionHistory = metadata.evolution_history || [];
  const specialistResults = metadata.specialist_results || [];
  const isEnhanced = task.mode === "enhanced";
  
  // Extract the full question from metadata or use the topic as fallback
  const fullQuestion = metadata.problem?.question || task.topic;
  
  // Check if task can be continued (completed, not converged, reached max iterations)
  const canContinueTask = result && !result.converged && task.status === "completed";

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
      <main className="max-w-6xl mx-auto px-5 py-12">
        {/* Task Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <Badge
              variant="secondary"
              className="font-mono text-xs bg-green-100 text-green-800 border-green-300"
            >
              Completed
            </Badge>
            <span className="font-mono text-xs text-gray-500 uppercase">
              {task.mode} mode
            </span>
            {isEnhanced && metadata.specialist_consultations && (
              <Badge variant="outline" className="font-mono text-xs">
                {metadata.specialist_consultations} specialist consultations
              </Badge>
            )}
          </div>
          <h1 className="font-mono text-3xl text-black mb-2 leading-tight">
            {fullQuestion}
          </h1>
          <div className="font-mono text-sm text-gray-600 space-y-1">
            <div>Started: {new Date(task.createdAt).toLocaleString()}</div>
            {task.completedAt && (
              <div>
                Completed: {new Date(task.completedAt).toLocaleString()}
              </div>
            )}
            {result && (
              <div className="flex gap-4">
                <span>{result.iterations} iterations</span>
                <span>{formatTokens(result.total_tokens || 0)}</span>
                <span>{formatDuration(result.processing_time || 0)}</span>
                <span>
                  {result.converged ? "Converged" : "Max iterations reached"}
                </span>
                <span>
                  Model: {task.modelName || "Unknown (legacy task)"}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Full Report Card */}
        <Card>
          <CardHeader>
            <CardTitle className="font-mono text-lg">Research Report</CardTitle>
          </CardHeader>
          <CardContent>
            {/* Thinking Process Section */}
            <div className="mb-6">
              <Accordion type="single" collapsible className="w-full">
                <AccordionItem value="thinking-process">
                  <AccordionTrigger className="font-mono text-sm text-gray-600 hover:text-black">
                    <div className="flex items-center gap-2">
                      <span>🧠</span>
                      <span>Thinking Process</span>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="pt-4">
                    <div className="space-y-4">
                      {/* Professor/Generator Messages */}
                      {evolutionHistory.length > 0 ? (
                        <div className="space-y-4">
                          <h3 className="font-mono text-sm font-bold text-gray-800">
                            {isEnhanced ? "Professor's" : "Generator's"}{" "}
                            Thinking Process
                          </h3>
                          <div className="space-y-3">
                            {evolutionHistory.map((iteration, index) => (
                              <div
                                key={index}
                                className="border border-gray-200 rounded-lg p-4"
                              >
                                <div className="flex items-center gap-2 mb-3">
                                  <div className="w-3 h-3 bg-blue-500 rounded-full" />
                                  <span className="font-mono text-sm font-bold text-gray-800">
                                    Step {iteration.iteration}
                                  </span>
                                  <Badge
                                    variant="outline"
                                    className="font-mono text-xs"
                                  >
                                    {iteration.should_stop
                                      ? "Final"
                                      : "Continuing"}
                                  </Badge>
                                </div>
                                <div className="bg-blue-50 p-3 rounded">
                                  <div className="font-mono text-xs text-blue-600 mb-1">
                                    {isEnhanced
                                      ? "Professor's Response:"
                                      : "Generator's Response:"}
                                  </div>
                                  <MarkdownRenderer
                                    content={iteration.output}
                                  />
                                </div>

                                {/* Reasoning summaries */}
                                {(iteration.reasoning_summary ||
                                  iteration.evaluator_reasoning_summary ||
                                  iteration.refiner_reasoning_summary) && (
                                  <div className="mt-3">
                                    <Accordion type="single" collapsible className="w-full">
                                      {iteration.reasoning_summary && (
                                        <AccordionItem value={`gen-reasoning-${index}`}>
                                          <AccordionTrigger className="font-mono text-sm text-gray-600 hover:text-black">
                                            <div className="flex items-center gap-2">
                                              <span>💭</span>
                                              <span>{isEnhanced ? "Professor" : "Generator"} Reasoning</span>
                                            </div>
                                          </AccordionTrigger>
                                          <AccordionContent className="pt-2">
                                            <MarkdownRenderer content={iteration.reasoning_summary} />
                                          </AccordionContent>
                                        </AccordionItem>
                                      )}
                                      {iteration.evaluator_reasoning_summary && (
                                        <AccordionItem value={`eval-reasoning-${index}`}>
                                          <AccordionTrigger className="font-mono text-sm text-gray-600 hover:text-black">
                                            <div className="flex items-center gap-2">
                                              <span>🧐</span>
                                              <span>Evaluator Reasoning</span>
                                            </div>
                                          </AccordionTrigger>
                                          <AccordionContent className="pt-2">
                                            <MarkdownRenderer content={iteration.evaluator_reasoning_summary} />
                                          </AccordionContent>
                                        </AccordionItem>
                                      )}
                                      {iteration.refiner_reasoning_summary && (
                                        <AccordionItem value={`refiner-reasoning-${index}`}>
                                          <AccordionTrigger className="font-mono text-sm text-gray-600 hover:text-black">
                                            <div className="flex items-center gap-2">
                                              <span>📝</span>
                                              <span>Prompt Refiner Reasoning</span>
                                            </div>
                                          </AccordionTrigger>
                                          <AccordionContent className="pt-2">
                                            <MarkdownRenderer content={iteration.refiner_reasoning_summary} />
                                          </AccordionContent>
                                        </AccordionItem>
                                      )}
                                    </Accordion>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="font-mono text-sm text-gray-500 text-center py-8">
                          No thinking process data available for this task
                        </div>
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </div>

            {/* Token Usage & Context Management Section */}
            {result && (
              <div className="mb-6">
                <Accordion type="single" collapsible className="w-full">
                  <AccordionItem value="token-usage">
                    <AccordionTrigger className="font-mono text-sm text-gray-600 hover:text-black">
                      <div className="flex items-center gap-2">
                        <span>📊</span>
                        <span>Token Usage & Context Management</span>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="pt-4">
                      <div className="space-y-4">
                        {/* Total Token Usage */}
                        <div className="border border-gray-200 rounded-lg p-4">
                          <h4 className="font-mono text-sm font-bold text-gray-800 mb-3">Total Token Usage</h4>
                          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                            <div className="text-center">
                              <div className="font-mono text-lg font-bold text-blue-600">
                                {formatTokens(result.total_tokens || 0)}
                              </div>
                              <div className="font-mono text-xs text-gray-500">Total Tokens</div>
                            </div>
                            {isEnhanced && (
                              <div className="text-center">
                                <div className="font-mono text-lg font-bold text-green-600">
                                  {formatTokens(metadata.professor_tokens || 0)}
                                </div>
                                <div className="font-mono text-xs text-gray-500">Professor</div>
                              </div>
                            )}
<div className="text-center">
                                <div className="font-mono text-lg font-bold text-amber-600">
                                  {formatTokens(metadata.reasoning_tokens || 0)}
                                </div>
                                <div className="font-mono text-xs text-gray-500">Reasoning</div>
                              </div>
                            {isEnhanced && (
                              <div className="text-center">
                                <div className="font-mono text-lg font-bold text-purple-600">
                                  {formatTokens(metadata.specialist_tokens || 0)}
                                </div>
                                <div className="font-mono text-xs text-gray-500">Specialists</div>
                              </div>
                            )}
                            <div className="text-center">
                              <div className="font-mono text-lg font-bold text-orange-600">
                                {formatTokens(Math.floor(result.total_tokens / result.iterations))}
                              </div>
                              <div className="font-mono text-xs text-gray-500">Avg/Iteration</div>
                            </div>
                          </div>
                        </div>

                        {/* Context Limits */}
                        <div className="border border-gray-200 rounded-lg p-4">
                          <h4 className="font-mono text-sm font-bold text-gray-800 mb-3">Context Limits & Usage</h4>
                          <div className="space-y-3">
                            {/* Model Context Limit */}
                            <div className="flex justify-between items-center">
                              <span className="font-mono text-sm text-gray-600">Model Context Limit:</span>
                              <span className="font-mono text-sm font-bold">
                                {getModelContextLimit(task.modelName, task.providerName, contextLimits).toLocaleString()} tokens
                              </span>
                            </div>
                            
                            {/* Peak Usage Estimate */}
                            <div className="flex justify-between items-center">
                              <span className="font-mono text-sm text-gray-600">Peak Usage (est.):</span>
                              <span className="font-mono text-sm font-bold">
                                {Math.max(...evolutionHistory.map((_, i) => 
                                  Math.floor((result.total_tokens / result.iterations) * (i + 1))
                                ), result.total_tokens / result.iterations).toLocaleString()} tokens
                              </span>
                            </div>
                            
                            {/* Context Pressure Indicator */}
                            <div className="flex justify-between items-center">
                              <span className="font-mono text-sm text-gray-600">Context Pressure:</span>
                              <div className="flex items-center gap-2">
                                {(() => {
                                  const contextLimit = getModelContextLimit(task.modelName, task.providerName, contextLimits);
                            // For enhanced mode, estimate peak usage considering professor tokens + context accumulation
                            // For basic mode, use simpler progressive accumulation
                            const avgTokensPerIteration = result.total_tokens / result.iterations;
                            let peakUsage;
                            
                            if (isEnhanced && metadata.professor_tokens) {
                              // Enhanced mode: professor tokens dominate the context
                              peakUsage = Math.max(metadata.professor_tokens, avgTokensPerIteration * result.iterations);
                            } else if (evolutionHistory.length > 0) {
                              // Progressive accumulation based on evolution history
                              peakUsage = Math.max(...evolutionHistory.map((_, i) => 
                                Math.floor(avgTokensPerIteration * (i + 1))
                              ), avgTokensPerIteration);
                            } else {
                              // Fallback: assume peak usage is average per iteration
                              peakUsage = avgTokensPerIteration;
                            }
                                  const pressure = (peakUsage / contextLimit) * 100;
                                  
                                  return (
                                    <>
                                      <div className={`w-20 h-2 rounded-full ${
                                        pressure < 50 ? 'bg-green-200' :
                                        pressure < 80 ? 'bg-yellow-200' : 'bg-red-200'
                                      }`}>
                                        <div className={`h-full rounded-full ${
                                          pressure < 50 ? 'bg-green-500' :
                                          pressure < 80 ? 'bg-yellow-500' : 'bg-red-500'
                                        }`} style={{ width: `${Math.min(pressure, 100)}%` }}></div>
                                      </div>
                                      <span className={`font-mono text-xs ${
                                        pressure < 50 ? 'text-green-600' :
                                        pressure < 80 ? 'text-yellow-600' : 'text-red-600'
                                      }`}>
                                        {pressure.toFixed(1)}%
                                      </span>
                                    </>
                                  );
                                })()}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Context Management Indicators */}
                        <div className="border border-gray-200 rounded-lg p-4">
                          <h4 className="font-mono text-sm font-bold text-gray-800 mb-3">Context Management</h4>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="flex items-center gap-2">
                              <div className={`w-3 h-3 rounded-full ${metadata.context_summarized ? 'bg-yellow-500' : 'bg-green-500'}`}></div>
                              <span className="font-mono text-sm text-gray-600">
                                {metadata.context_summarized ? 'Context was summarized' : 'No summarization needed'}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className={`w-3 h-3 rounded-full ${metadata.context_truncated ? 'bg-red-500' : 'bg-green-500'}`}></div>
                              <span className="font-mono text-sm text-gray-600">
                                {metadata.context_truncated ? 'Context was truncated' : 'No truncation occurred'}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className={`w-3 h-3 rounded-full ${result.iterations > 3 ? 'bg-yellow-500' : 'bg-green-500'}`}></div>
                              <span className="font-mono text-sm text-gray-600">
                                {result.iterations > 3 ? 'Extended reasoning' : 'Standard reasoning'}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className={`w-3 h-3 rounded-full ${!result.converged ? 'bg-orange-500' : 'bg-green-500'}`}></div>
                              <span className="font-mono text-sm text-gray-600">
                                {!result.converged ? 'Hit iteration limit' : 'Converged naturally'}
                              </span>
                            </div>
                          </div>
                          
                          {(metadata.context_summarized || metadata.context_truncated) && (
                            <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded">
                              <div className="font-mono text-xs text-yellow-800">
                                ⚠️ Context management was triggered during this task. Some reasoning history may have been compressed to fit within model limits.
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </div>
            )}

            {/* Specialist Consultations Section */}
            {isEnhanced && specialistResults.length > 0 && (
              <>
                <div className="mb-6">
                  <Accordion type="single" collapsible className="w-full">
                    <AccordionItem value="specialist-consultations">
                      <AccordionTrigger className="font-mono text-sm text-gray-600 hover:text-black">
                        <div className="flex items-center gap-2">
                          <span>👥</span>
                          <span>Specialist Consultations ({specialistResults.length})</span>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent className="pt-4">
                        <div className="space-y-4">
                          {specialistResults.map((specialist, index) => (
                            <div
                              key={index}
                              className="border border-gray-200 rounded-lg p-4"
                            >
                              <div className="flex items-center gap-2 mb-3">
                                <div className="w-3 h-3 bg-purple-500 rounded-full" />
                                <span className="font-mono text-sm font-bold text-purple-800">
                                  Specialist {index + 1}
                                </span>
                                <Badge
                                  variant="outline"
                                  className="font-mono text-xs bg-purple-50 text-purple-700 border-purple-300"
                                >
                                  {specialist.metadata?.iterations || 0} iterations
                                </Badge>
                                <Badge
                                  variant="outline"
                                  className="font-mono text-xs"
                                >
                                  {specialist.metadata?.converged ? "Converged" : "Max iterations"}
                                </Badge>
                                <Badge
                                  variant="outline"
                                  className="font-mono text-xs bg-blue-50 text-blue-700 border-blue-300"
                                >
                                  {formatTokens(specialist.metadata?.total_tokens || 0)}
                                </Badge>
                              </div>
                              <div className="mb-3">
                                <div className="font-mono text-xs text-purple-600 mb-1">
                                  Specialization:
                                </div>
                                <div className="font-mono text-sm text-gray-800 italic mb-2">
                                  {specialist.specialization}
                                </div>
                                <div className="font-mono text-xs text-purple-600 mb-1">
                                  Task:
                                </div>
                                <div className="font-mono text-sm text-gray-700 mb-3">
                                  {specialist.task}
                                </div>
                              </div>
                              <div className="bg-purple-50 p-3 rounded">
                                <div className="font-mono text-xs text-purple-600 mb-1">
                                  Specialist's Analysis:
                                </div>
                                <MarkdownRenderer
                                  content={specialist.output}
                                  maxLength={1000}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  </Accordion>
                </div>
                {/* Divider */}
                <div className="border-t border-gray-200 my-6"></div>
              </>
            )}

            {/* Final Report */}
            <div>
              <h3 className="font-mono text-sm font-bold text-gray-800 mb-4">
                Final Report
              </h3>
              {fetchingDetails ? (
                <div className="flex items-center justify-center py-8">
                  <div className="font-mono text-sm text-gray-500">Loading full report details...</div>
                </div>
              ) : (
                <MarkdownRenderer content={result?.output || ""} />
              )}
            </div>
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="mt-8 flex gap-4">
          <Link href="/dashboard">
            <Button
              variant="outline"
              className="font-mono border-black text-black hover:bg-black hover:text-white px-6 py-2 text-sm bg-transparent"
            >
              Back to Dashboard
            </Button>
          </Link>
          <Link href="/new-task">
            <Button className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-6 py-2 text-sm">
              Start New Research
            </Button>
          </Link>
          {canContinueTask && (
            <Button
              onClick={handleContinueTask}
              disabled={continuing}
              className="font-mono bg-blue-600 text-white hover:bg-blue-700 border border-blue-600 px-6 py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {continuing ? "Starting..." : "Continue +1 Iteration"}
            </Button>
          )}
        </div>
      </main>
    </div>
  );
}
