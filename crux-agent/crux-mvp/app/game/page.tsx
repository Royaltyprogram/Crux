"use client";

import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { WaitingGame } from "@/components/ui/waiting-game";
import { PaperCollectorGame } from "@/components/ui/paper-collector-game";
import { useState } from "react";

export default function GamePage() {
  const [selectedGame, setSelectedGame] = useState<'snake' | 'papers' | null>(null);

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

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-5 py-12">
        <div className="text-center mb-8">
          <h1 className="font-mono text-3xl text-black mb-4">
            Research Break
          </h1>
          <p className="font-mono text-sm text-gray-600 mb-6 max-w-2xl mx-auto leading-relaxed">
            Take a quick break while your AI agent works on your research. 
            Choose a game to pass the time, then return to check your results.
          </p>
          <div className="flex gap-4 justify-center">
            <Link href="/dashboard">
              <Button 
                variant="outline"
                className="font-mono border-black text-black hover:bg-black hover:text-white px-4 py-2 text-sm bg-transparent"
              >
                ← Back to Dashboard
              </Button>
            </Link>
            {selectedGame && (
              <Button
                onClick={() => setSelectedGame(null)}
                variant="outline"
                className="font-mono border-gray-300 text-gray-600 hover:bg-gray-600 hover:text-white px-4 py-2 text-sm bg-transparent"
              >
                Choose Different Game
              </Button>
            )}
          </div>
        </div>

        {/* Game Selection or Game Container */}
        {!selectedGame ? (
          <div className="grid md:grid-cols-2 gap-6 max-w-4xl mx-auto">
            {/* Snake Game */}
            <div className="border border-gray-300 p-6 hover:border-black transition-colors cursor-pointer"
                 onClick={() => setSelectedGame('snake')}>
              <div className="text-center">
                <div className="font-mono text-4xl mb-4">🐍</div>
                <h3 className="font-mono text-lg text-black mb-3">
                  Classic Snake
                </h3>
                <p className="font-mono text-sm text-gray-600 mb-4 leading-relaxed">
                  The timeless classic. Collect food, grow longer, avoid hitting walls or yourself.
                  Perfect for quick strategic thinking breaks.
                </p>
                <div className="font-mono text-xs text-gray-500 mb-4">
                  • Use arrow keys or WASD<br/>
                  • Progressively challenging<br/>
                  • Quick games (2-5 minutes)
                </div>
                <Button className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-6 py-2 text-sm w-full">
                  Play Snake →
                </Button>
              </div>
            </div>

            {/* Paper Collector Game */}
            <div className="border border-gray-300 p-6 hover:border-black transition-colors cursor-pointer"
                 onClick={() => setSelectedGame('papers')}>
              <div className="text-center">
                <div className="font-mono text-4xl mb-4">📚</div>
                <h3 className="font-mono text-lg text-black mb-3">
                  Paper Collector
                </h3>
                <p className="font-mono text-sm text-gray-600 mb-4 leading-relaxed">
                  Help the professor collect quality research papers while avoiding junk publications.
                  Perfect theme for researchers and students!
                </p>
                <div className="font-mono text-xs text-gray-500 mb-4">
                  • Academic-themed gameplay<br/>
                  • Collect quality papers, avoid junk<br/>
                  • Educational and entertaining
                </div>
                <Button className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-6 py-2 text-sm w-full">
                  Play Paper Collector →
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex justify-center">
            <div className="max-w-md">
              {selectedGame === 'snake' ? <WaitingGame /> : <PaperCollectorGame />}
            </div>
          </div>
        )}

        {/* Game Instructions - only show when game is not selected */}
        {!selectedGame && (
          <div className="mt-12 max-w-2xl mx-auto">
            <div className="border border-gray-300 p-6">
              <h3 className="font-mono text-lg text-black mb-4">Choose Your Break Activity</h3>
              <div className="font-mono text-sm text-gray-600 space-y-2">
                <div>• Both games are designed for quick mental breaks</div>
                <div>• Games automatically prevent page scrolling during play</div>
                <div>• Perfect for 5-15 minute research breaks</div>
                <div>• Return to dashboard anytime to check your research progress</div>
              </div>
            </div>
          </div>
        )}

        {/* Research Status Reminder */}
        <div className="mt-8 text-center">
          <div className="border border-gray-300 p-6 bg-gray-50">
            <h4 className="font-mono text-sm text-black mb-2">
              Research Status
            </h4>
            <p className="font-mono text-xs text-gray-600 mb-4">
              Your AI agent is still working on your research tasks. 
              Check back on your dashboard for updates and results.
            </p>
            <Link href="/dashboard">
              <Button className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-6 py-2 text-sm">
                Check Research Progress
              </Button>
            </Link>
          </div>
        </div>
      </main>

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