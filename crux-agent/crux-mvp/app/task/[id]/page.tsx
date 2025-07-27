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
import { formatDuration, formatTokens, apiClient } from "@/lib/api";
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
    const normalized = withProtectedCode
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
  const router = useRouter();
  const { tasks, refreshTasks } = useTasks();
  const [loading, setLoading] = useState(true);
  const [continuing, setContinuing] = useState(false);

  const task = tasks.find((t) => t.id === params.id);

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

  if (task.status !== "completed") {
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
          <h1 className="font-mono text-2xl text-black mb-4">
            {task.status === "failed" ? "Task Failed" : "Task Still Processing"}
          </h1>
          <p className="font-mono text-sm text-gray-600 mb-6">
            {task.status === "failed"
              ? "This research task encountered an error during processing."
              : `This research task is ${task.status}. Current phase: ${task.currentPhase}`}
          </p>
          {task.status === "running" && (
            <div className="mb-6">
              <div className="font-mono text-sm text-blue-600 mb-2">
                Progress: {Math.round(task.progress * 100)}%
              </div>
              <Progress value={task.progress * 100} className="w-full" />
            </div>
          )}
          <Link href="/dashboard">
            <Button className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-6 py-2 text-sm">
              Back to Dashboard
            </Button>
          </Link>
        </main>
      </div>
    );
  }

  const result = task.result;
  const metadata = (result?.metadata || {}) as TaskMetadata;
  const evolutionHistory = metadata.evolution_history || [];
  const specialistResults = metadata.specialist_results || [];
  const isEnhanced = task.mode === "enhanced";
  
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
            {task.topic}
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

            {/* Divider */}
            <div className="border-t border-gray-200 my-6"></div>

            {/* Final Report */}
            <div>
              <h3 className="font-mono text-sm font-bold text-gray-800 mb-4">
                Final Report
              </h3>
              <MarkdownRenderer content={result?.output || ""} />
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
