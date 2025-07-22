'use client'

import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";

export default function HomePage() {
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

      {/* Hero Section */}
      <section className="max-w-4xl mx-auto px-5 py-20">
        <div className="text-center">
          <h1 className="font-mono text-4xl text-black mb-6 leading-tight">
            Academic Research Agent
          </h1>
          <p className="font-mono text-lg text-gray-600 mb-8 max-w-2xl mx-auto leading-relaxed">
            Transform your research topics into comprehensive proofs and
            academic discoveries. Submit your thesis and let our AI agent
            conduct deep research while you focus on other work.
          </p>
          <div className="flex gap-4 justify-center">
            <Link href="/new-task">
              <Button className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-8 py-3 text-sm">
                Start Research
              </Button>
            </Link>
            <Link href="/dashboard">
              <Button
                variant="outline"
                className="font-mono border-black text-black hover:bg-black hover:text-white px-8 py-3 text-sm bg-transparent"
              >
                View Dashboard
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-4xl mx-auto px-5 py-16 border-t border-gray-300">
        <div className="grid md:grid-cols-2 gap-12">
          <div className="border border-gray-300 p-8">
            <h3 className="font-mono text-xl text-black mb-4">Basic Mode</h3>
            <p className="font-mono text-sm text-gray-600 mb-4 leading-relaxed">
              Quick research and proof generation in approximately 20 minutes.
              Perfect for initial exploration and concept validation.
            </p>
            <div className="font-mono text-xs text-gray-500">
              ~20 minutes runtime
            </div>
          </div>
          <div className="border border-gray-300 p-8">
            <h3 className="font-mono text-xl text-black mb-4">Enhanced Mode</h3>
            <p className="font-mono text-sm text-gray-600 mb-4 leading-relaxed">
              Comprehensive research with deep analysis and detailed proofs.
              Includes theoretical explanations and academic discoveries.
            </p>
            <div className="font-mono text-xs text-gray-500">
              ~1 hour 20 minutes runtime
            </div>
          </div>
        </div>
      </section>

      {/* How it Works */}
      <section className="max-w-4xl mx-auto px-5 py-16 border-t border-gray-300">
        <h2 className="font-mono text-2xl text-black mb-12 text-center">
          How It Works
        </h2>
        <div className="grid md:grid-cols-3 gap-8">
          <div className="text-center">
            <div className="w-12 h-12 border-2 border-black rounded-full flex items-center justify-center font-mono text-lg mb-4 mx-auto">
              1
            </div>
            <h4 className="font-mono text-lg text-black mb-2">Submit Topic</h4>
            <p className="font-mono text-sm text-gray-600 leading-relaxed">
              Enter your research topic or thesis statement
            </p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 border-2 border-black rounded-full flex items-center justify-center font-mono text-lg mb-4 mx-auto">
              2
            </div>
            <h4 className="font-mono text-lg text-black mb-2">AI Research</h4>
            <p className="font-mono text-sm text-gray-600 leading-relaxed">
              Our agent conducts comprehensive research and analysis
            </p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 border-2 border-black rounded-full flex items-center justify-center font-mono text-lg mb-4 mx-auto">
              3
            </div>
            <h4 className="font-mono text-lg text-black mb-2">Get Results</h4>
            <p className="font-mono text-sm text-gray-600 leading-relaxed">
              Receive detailed proofs and academic insights
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-black mt-20">
        <div className="max-w-4xl mx-auto px-5 py-8">
          <div className="flex items-center justify-between">
            <div className="font-mono text-sm text-gray-600">
              © 2024 Crux by tooliense
            </div>
            <div className="font-mono text-xs text-gray-500">
              Academic Research Agent
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}