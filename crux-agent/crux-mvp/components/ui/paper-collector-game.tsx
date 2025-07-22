"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";

type Position = { x: number; y: number };
type Paper = { id: number; x: number; y: number; type: 'good' | 'bad'; value: number };

const CANVAS_WIDTH = 400;
const CANVAS_HEIGHT = 300;
const PLAYER_WIDTH = 24;
const PLAYER_HEIGHT = 32;
const PAPER_WIDTH = 16;
const PAPER_HEIGHT = 20;
const GAME_SPEED = 50;
const PAPER_FALL_SPEED = 2;
const PLAYER_SPEED = 5;

// Good papers (green-ish)
const GOOD_PAPER_TYPES = ['📚', '📖', '📝', '🔬', '📊'];
// Bad papers (red-ish) 
const BAD_PAPER_TYPES = ['📄', '🗞️', '📋'];

export function PaperCollectorGame() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [playerX, setPlayerX] = useState(CANVAS_WIDTH / 2);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [score, setScore] = useState(0);
  const [lives, setLives] = useState(3);
  const [gameRunning, setGameRunning] = useState(false);
  const [gameOver, setGameOver] = useState(false);
  const [level, setLevel] = useState(1);
  const gameLoopRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const paperIdCounter = useRef(0);
  const keysPressed = useRef<Set<string>>(new Set());

  const resetGame = useCallback(() => {
    setPlayerX(CANVAS_WIDTH / 2);
    setPapers([]);
    setScore(0);
    setLives(3);
    setLevel(1);
    setGameOver(false);
    setGameRunning(false);
    paperIdCounter.current = 0;
    keysPressed.current.clear();
  }, []);

  const startGame = useCallback(() => {
    resetGame();
    setGameRunning(true);
  }, [resetGame]);

  // Generate new papers
  const generatePaper = useCallback(() => {
    const isGood = Math.random() > 0.3; // 70% good papers
    const paperType = isGood 
      ? GOOD_PAPER_TYPES[Math.floor(Math.random() * GOOD_PAPER_TYPES.length)]
      : BAD_PAPER_TYPES[Math.floor(Math.random() * BAD_PAPER_TYPES.length)];
    
    return {
      id: paperIdCounter.current++,
      x: Math.random() * (CANVAS_WIDTH - PAPER_WIDTH),
      y: -PAPER_HEIGHT,
      type: isGood ? 'good' as const : 'bad' as const,
      value: isGood ? 10 : -5
    };
  }, []);

  // Handle keyboard input
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      keysPressed.current.add(e.key.toLowerCase());
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      keysPressed.current.delete(e.key.toLowerCase());
    };

    if (gameRunning) {
      window.addEventListener('keydown', handleKeyDown);
      window.addEventListener('keyup', handleKeyUp);
    }

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [gameRunning]);

  // Game loop
  useEffect(() => {
    if (!gameRunning || gameOver) return;

    gameLoopRef.current = setInterval(() => {
      // Handle player movement
      setPlayerX(prev => {
        let newX = prev;
        if (keysPressed.current.has('arrowleft') || keysPressed.current.has('a')) {
          newX = Math.max(0, prev - PLAYER_SPEED);
        }
        if (keysPressed.current.has('arrowright') || keysPressed.current.has('d')) {
          newX = Math.min(CANVAS_WIDTH - PLAYER_WIDTH, prev + PLAYER_SPEED);
        }
        return newX;
      });

      // Update papers and check collisions
      setPapers(prevPapers => {
        let newPapers = [...prevPapers];
        
        // Move papers down
        newPapers = newPapers.map(paper => ({
          ...paper,
          y: paper.y + PAPER_FALL_SPEED * level
        }));

        // Remove papers that have fallen off screen
        newPapers = newPapers.filter(paper => paper.y < CANVAS_HEIGHT);

        // Add new papers occasionally
        if (Math.random() < 0.02 + level * 0.005) {
          newPapers.push(generatePaper());
        }

        // Check collisions with player
        const playerRect = {
          x: playerX,
          y: CANVAS_HEIGHT - PLAYER_HEIGHT - 10,
          width: PLAYER_WIDTH,
          height: PLAYER_HEIGHT
        };

        newPapers = newPapers.filter(paper => {
          const paperRect = {
            x: paper.x,
            y: paper.y,
            width: PAPER_WIDTH,
            height: PAPER_HEIGHT
          };

          // Simple collision detection
          if (paperRect.x < playerRect.x + playerRect.width &&
              paperRect.x + paperRect.width > playerRect.x &&
              paperRect.y < playerRect.y + playerRect.height &&
              paperRect.y + paperRect.height > playerRect.y) {
            
            // Collision detected!
            setScore(prev => prev + paper.value);
            
            if (paper.type === 'bad') {
              setLives(prev => {
                const newLives = prev - 1;
                if (newLives <= 0) {
                  setGameOver(true);
                  setGameRunning(false);
                }
                return newLives;
              });
            }

            return false; // Remove the paper
          }
          return true; // Keep the paper
        });

        return newPapers;
      });

      // Level progression
      setScore(prev => {
        const newLevel = Math.floor(prev / 100) + 1;
        if (newLevel !== level) {
          setLevel(newLevel);
        }
        return prev;
      });

    }, GAME_SPEED);

    return () => {
      if (gameLoopRef.current) {
        clearInterval(gameLoopRef.current);
      }
    };
  }, [gameRunning, gameOver, level, playerX, generatePaper]);

  // Canvas rendering
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.fillStyle = '#f0f0f0';
    ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

    if (gameRunning || gameOver) {
      // Draw player
      ctx.fillStyle = '#4a5568';
      ctx.fillRect(playerX, CANVAS_HEIGHT - PLAYER_HEIGHT - 10, PLAYER_WIDTH, PLAYER_HEIGHT);
      
      // Draw simple professor face
      ctx.fillStyle = '#2d3748';
      ctx.fillRect(playerX + 6, CANVAS_HEIGHT - PLAYER_HEIGHT - 5, 3, 3); // left eye
      ctx.fillRect(playerX + 15, CANVAS_HEIGHT - PLAYER_HEIGHT - 5, 3, 3); // right eye
      ctx.fillRect(playerX + 9, CANVAS_HEIGHT - PLAYER_HEIGHT + 2, 6, 2); // mouth

      // Draw papers
      papers.forEach(paper => {
        ctx.fillStyle = paper.type === 'good' ? '#48bb78' : '#f56565';
        ctx.fillRect(paper.x, paper.y, PAPER_WIDTH, PAPER_HEIGHT);
        
        // Add paper icon
        ctx.fillStyle = '#2d3748';
        ctx.font = '12px monospace';
        ctx.fillText(paper.type === 'good' ? '📄' : '❌', paper.x + 2, paper.y + 12);
      });
    }

    // Draw UI text
    ctx.fillStyle = '#2d3748';
    ctx.font = '14px monospace';
    if (!gameRunning && !gameOver) {
      ctx.fillText('Paper Collector Game', 10, 30);
      ctx.fillText('Collect good papers, avoid bad ones!', 10, 50);
      ctx.fillText('Use arrow keys or A/D to move', 10, 70);
    } else {
      ctx.fillText(`Score: ${score}`, 10, 25);
      ctx.fillText(`Lives: ${lives}`, 10, 45);
      ctx.fillText(`Level: ${level}`, 10, 65);
    }

    if (gameOver) {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
      ctx.fillStyle = '#ffffff';
      ctx.font = '24px monospace';
      ctx.fillText('Game Over!', CANVAS_WIDTH / 2 - 60, CANVAS_HEIGHT / 2 - 20);
      ctx.font = '16px monospace';
      ctx.fillText(`Final Score: ${score}`, CANVAS_WIDTH / 2 - 55, CANVAS_HEIGHT / 2 + 10);
    }
  }, [gameRunning, gameOver, playerX, papers, score, lives, level]);

  return (
    <div className="flex flex-col items-center space-y-4 p-6 bg-gray-50 rounded-lg">
      <h2 className="font-mono text-xl text-black mb-4">Paper Collector Game</h2>
      
      <canvas
        ref={canvasRef}
        width={CANVAS_WIDTH}
        height={CANVAS_HEIGHT}
        className="border-2 border-gray-300 bg-white"
      />
      
      <div className="flex space-x-4">
        <Button
          onClick={startGame}
          className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-6 py-2 text-sm"
          disabled={gameRunning}
        >
          {gameOver ? 'Play Again' : 'Start Game'}
        </Button>
        
        {gameRunning && (
          <Button
            onClick={() => {
              setGameRunning(false);
              if (gameLoopRef.current) clearInterval(gameLoopRef.current);
            }}
            variant="outline"
            className="font-mono border-red-300 text-red-600 hover:bg-red-600 hover:text-white px-6 py-2 text-sm"
          >
            Stop Game
          </Button>
        )}
      </div>

      <div className="text-sm font-mono text-gray-600 text-center">
        <p>🎯 Goal: Collect good papers (green) and avoid bad ones (red)</p>
        <p>⌨️ Controls: Arrow keys or A/D to move left/right</p>
        <p>📈 Score increases with good papers, decreases with bad ones</p>
        <p>❤️ You have 3 lives - lose one for each bad paper collected</p>
      </div>
    </div>
  );
}