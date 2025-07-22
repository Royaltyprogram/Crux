"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";

type Position = { x: number; y: number };
type Direction = "UP" | "DOWN" | "LEFT" | "RIGHT";

const GRID_SIZE = 20;
const CANVAS_SIZE = 300;
const INITIAL_SNAKE = [{ x: 10, y: 10 }];
const INITIAL_FOOD = { x: 15, y: 15 };
const GAME_SPEED = 150;

export function WaitingGame() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [snake, setSnake] = useState<Position[]>(INITIAL_SNAKE);
  const [food, setFood] = useState<Position>(INITIAL_FOOD);
  const [direction, setDirection] = useState<Direction>("RIGHT");
  const [gameRunning, setGameRunning] = useState(false);
  const [score, setScore] = useState(0);
  const [gameOver, setGameOver] = useState(false);
  const gameLoopRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const generateFood = useCallback((snakeBody: Position[]): Position => {
    let newFood: Position;
    do {
      newFood = {
        x: Math.floor(Math.random() * GRID_SIZE),
        y: Math.floor(Math.random() * GRID_SIZE),
      };
    } while (snakeBody.some(segment => segment.x === newFood.x && segment.y === newFood.y));
    return newFood;
  }, []);

  const resetGame = useCallback(() => {
    setSnake(INITIAL_SNAKE);
    setFood(INITIAL_FOOD);
    setDirection("RIGHT");
    setScore(0);
    setGameOver(false);
    setGameRunning(false);
  }, []);

  const startGame = useCallback(() => {
    resetGame();
    setGameRunning(true);
  }, [resetGame]);

  const moveSnake = useCallback(() => {
    setSnake(currentSnake => {
      const newSnake = [...currentSnake];
      const head = { ...newSnake[0] };

      switch (direction) {
        case "UP":
          head.y -= 1;
          break;
        case "DOWN":
          head.y += 1;
          break;
        case "LEFT":
          head.x -= 1;
          break;
        case "RIGHT":
          head.x += 1;
          break;
      }

      // Check wall collision
      if (head.x < 0 || head.x >= GRID_SIZE || head.y < 0 || head.y >= GRID_SIZE) {
        setGameOver(true);
        setGameRunning(false);
        return currentSnake;
      }

      // Check self collision
      if (newSnake.some(segment => segment.x === head.x && segment.y === head.y)) {
        setGameOver(true);
        setGameRunning(false);
        return currentSnake;
      }

      newSnake.unshift(head);

      // Check food collision
      if (head.x === food.x && head.y === food.y) {
        setScore(prev => prev + 10);
        setFood(generateFood(newSnake));
      } else {
        newSnake.pop();
      }

      return newSnake;
    });
  }, [direction, food, generateFood]);

  // Handle keyboard input
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (!gameRunning) return;

      switch (e.key.toLowerCase()) {
        case "arrowup":
        case "w":
          if (direction !== "DOWN") setDirection("UP");
          break;
        case "arrowdown":
        case "s":
          if (direction !== "UP") setDirection("DOWN");
          break;
        case "arrowleft":
        case "a":
          if (direction !== "RIGHT") setDirection("LEFT");
          break;
        case "arrowright":
        case "d":
          if (direction !== "LEFT") setDirection("RIGHT");
          break;
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [gameRunning, direction]);

  // Game loop
  useEffect(() => {
    if (gameRunning && !gameOver) {
      gameLoopRef.current = setInterval(moveSnake, GAME_SPEED);
    } else if (gameLoopRef.current) {
      clearInterval(gameLoopRef.current);
    }

    return () => {
      if (gameLoopRef.current) {
        clearInterval(gameLoopRef.current);
      }
    };
  }, [gameRunning, gameOver, moveSnake]);

  // Canvas rendering
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const cellSize = CANVAS_SIZE / GRID_SIZE;

    // Clear canvas
    ctx.fillStyle = "#f7fafc";
    ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

    // Draw grid
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = 1;
    for (let i = 0; i <= GRID_SIZE; i++) {
      ctx.beginPath();
      ctx.moveTo(i * cellSize, 0);
      ctx.lineTo(i * cellSize, CANVAS_SIZE);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(0, i * cellSize);
      ctx.lineTo(CANVAS_SIZE, i * cellSize);
      ctx.stroke();
    }

    if (gameRunning || gameOver) {
      // Draw snake
      snake.forEach((segment, index) => {
        ctx.fillStyle = index === 0 ? "#2d3748" : "#4a5568"; // Head darker than body
        ctx.fillRect(
          segment.x * cellSize + 1,
          segment.y * cellSize + 1,
          cellSize - 2,
          cellSize - 2
        );
      });

      // Draw food
      ctx.fillStyle = "#e53e3e";
      ctx.fillRect(
        food.x * cellSize + 2,
        food.y * cellSize + 2,
        cellSize - 4,
        cellSize - 4
      );
    }

    // Draw text
    ctx.fillStyle = "#2d3748";
    ctx.font = "16px monospace";
    
    if (!gameRunning && !gameOver) {
      ctx.fillText("Snake Game", 10, 25);
      ctx.font = "12px monospace";
      ctx.fillText("Use WASD or arrow keys", 10, 45);
      ctx.fillText("Press Start to begin", 10, 60);
    } else {
      ctx.fillText(`Score: ${score}`, 10, 25);
    }

    if (gameOver) {
      ctx.fillStyle = "rgba(0, 0, 0, 0.8)";
      ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
      
      ctx.fillStyle = "#ffffff";
      ctx.font = "20px monospace";
      ctx.fillText("Game Over!", CANVAS_SIZE / 2 - 55, CANVAS_SIZE / 2 - 10);
      ctx.font = "14px monospace";
      ctx.fillText(`Final Score: ${score}`, CANVAS_SIZE / 2 - 45, CANVAS_SIZE / 2 + 15);
    }
  }, [snake, food, gameRunning, gameOver, score]);

  return (
    <div className="flex flex-col items-center space-y-4 p-6 bg-gray-50 rounded-lg">
      <h2 className="font-mono text-xl text-black mb-4">Snake Game</h2>
      
      <canvas
        ref={canvasRef}
        width={CANVAS_SIZE}
        height={CANVAS_SIZE}
        className="border-2 border-gray-300 bg-white"
      />
      
      <div className="flex space-x-4">
        <Button
          onClick={startGame}
          className="font-mono bg-black text-white hover:bg-white hover:text-black border border-black px-6 py-2 text-sm"
          disabled={gameRunning}
        >
          {gameOver ? "Play Again" : "Start Game"}
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
            Pause Game
          </Button>
        )}
      </div>

      <div className="text-sm font-mono text-gray-600 text-center">
        <p>🐍 Classic Snake game to pass the time</p>
        <p>⌨️ Use WASD or arrow keys to control</p>
        <p>🍎 Eat the red food to grow and score points</p>
        <p>💀 Don't hit the walls or your own tail!</p>
      </div>
    </div>
  );
}