import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Icon, type IconName } from "../../ui/Icon";

type ActivityId = "tic-tac-toe" | "memory" | "number-guess";
type Cell = "X" | "O" | null;

const activities: { id: ActivityId; name: string; description: string; icon: IconName }[] = [
  { id: "tic-tac-toe", name: "Tic-tac-toe", description: "A quick two-player game.", icon: "tic-tac-toe" },
  { id: "memory", name: "Memory match", description: "Find all six matching pairs.", icon: "memory" },
  { id: "number-guess", name: "Number guess", description: "Find the hidden number from 1 to 100.", icon: "guess" },
];

export function ActivitiesPage() {
  const [selected, setSelected] = useState<ActivityId>("tic-tac-toe");

  return (
    <section className="page-wrap activities-page">
      <header className="page-heading">
        <span className="eyebrow">Take a short break</span>
        <h1>Offline activities</h1>
        <p className="muted">Open the app once while online to cache it. After that, these games can be played without a network connection.</p>
      </header>

      <div className="activity-picker" role="group" aria-label="Choose an activity">
        {activities.map((activity) => (
          <button key={activity.id} type="button" aria-pressed={selected === activity.id} className={`activity-option ${selected === activity.id ? "activity-option-active" : ""}`} onClick={() => setSelected(activity.id)}>
            <span className="activity-option-icon"><Icon name={activity.icon} /></span>
            <span><strong>{activity.name}</strong><small>{activity.description}</small></span>
          </button>
        ))}
      </div>

      <section className="activity-panel" id="activity-panel" aria-label={activities.find((activity) => activity.id === selected)?.name}>
        {selected === "tic-tac-toe" && <TicTacToe />}
        {selected === "memory" && <MemoryMatch />}
        {selected === "number-guess" && <NumberGuess />}
      </section>
    </section>
  );
}

function TicTacToe() {
  const [board, setBoard] = useState<Cell[]>(Array(9).fill(null));
  const [turn, setTurn] = useState<Exclude<Cell, null>>("X");
  const winner = findWinner(board);
  const draw = !winner && board.every(Boolean);

  function play(index: number) {
    if (board[index] || winner || draw) return;
    const next = [...board];
    next[index] = turn;
    setBoard(next);
    setTurn(turn === "X" ? "O" : "X");
  }

  function restart() {
    setBoard(Array(9).fill(null));
    setTurn("X");
  }

  return <div className="game-layout">
    <div><span className="eyebrow">Two players · one device</span><h2>Tic-tac-toe</h2><p className="game-status" aria-live="polite">{winner ? `${winner} wins!` : draw ? "It's a draw." : `${turn}'s turn`}</p></div>
    <div className="tic-board" role="group" aria-label="Tic-tac-toe board">
      {board.map((cell, index) => <button key={index} type="button" className={`tic-cell ${cell ? `tic-cell-${cell.toLowerCase()}` : ""}`} aria-label={`Row ${Math.floor(index / 3) + 1}, column ${index % 3 + 1}${cell ? `, ${cell}` : ""}`} onClick={() => play(index)} disabled={Boolean(cell || winner || draw)}>{cell}</button>)}
    </div>
    <button type="button" className="button button-secondary" onClick={restart}>New game</button>
  </div>;
}

function findWinner(board: Cell[]): Exclude<Cell, null> | null {
  const lines = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]];
  for (const [a, b, c] of lines) {
    if (board[a] && board[a] === board[b] && board[b] === board[c]) return board[a];
  }
  return null;
}

type MemoryCard = { id: number; value: string };
const memorySymbols = ["☀", "☂", "♫", "✿", "☕", "★"];

function shuffledDeck(): MemoryCard[] {
  const deck = [...memorySymbols, ...memorySymbols].map((value, id) => ({ id, value }));
  for (let index = deck.length - 1; index > 0; index--) {
    const other = Math.floor(Math.random() * (index + 1));
    [deck[index], deck[other]] = [deck[other], deck[index]];
  }
  return deck;
}

function MemoryMatch() {
  const [cards, setCards] = useState(shuffledDeck);
  const [open, setOpen] = useState<number[]>([]);
  const [matched, setMatched] = useState<number[]>([]);
  const [moves, setMoves] = useState(0);
  const [feedback, setFeedback] = useState("Choose a card to start.");
  const mismatchTimer = useRef<number | null>(null);
  const complete = matched.length === cards.length;

  useEffect(() => () => {
    if (mismatchTimer.current !== null) window.clearTimeout(mismatchTimer.current);
  }, []);

  function flip(card: MemoryCard) {
    if (complete || open.length === 2 || matched.includes(card.id) || open.includes(card.id)) return;
    if (open.length === 0) {
      setOpen([card.id]);
      setFeedback(`${card.value} revealed. Choose one more card.`);
      return;
    }

    const firstId = open[0];
    const firstCard = cards.find((item) => item.id === firstId);
    setOpen([firstId, card.id]);
    setMoves((count) => count + 1);
    if (firstCard?.value === card.value) {
      setMatched((current) => [...current, firstId, card.id]);
      setOpen([]);
      setFeedback(`Match found: ${card.value}.`);
    } else {
      setFeedback("No match. Those cards will turn back over.");
      mismatchTimer.current = window.setTimeout(() => {
        setOpen([]);
        mismatchTimer.current = null;
      }, 650);
    }
  }

  function restart() {
    if (mismatchTimer.current !== null) window.clearTimeout(mismatchTimer.current);
    mismatchTimer.current = null;
    setCards(shuffledDeck());
    setOpen([]);
    setMatched([]);
    setMoves(0);
    setFeedback("Choose a card to start.");
  }

  return <div className="game-layout memory-layout">
    <div><span className="eyebrow">Find the pairs</span><h2>Memory match</h2><p className="game-status" aria-live="polite">{complete ? `All pairs found in ${moves} moves!` : `${moves} ${moves === 1 ? "move" : "moves"} · ${feedback}`}</p></div>
    <div className="memory-board" role="group" aria-label="Memory match cards">
      {cards.map((card, index) => {
        const revealed = open.includes(card.id) || matched.includes(card.id);
        const cardPosition = index + 1;
        const isMatched = matched.includes(card.id);
        return <button key={card.id} type="button" className={`memory-card ${revealed ? "memory-card-revealed" : ""} ${isMatched ? "memory-card-matched" : ""}`} aria-label={revealed ? `Card ${cardPosition}: ${card.value}${isMatched ? ", matched" : ""}` : `Card ${cardPosition}, hidden`} aria-pressed={revealed} onClick={() => flip(card)} disabled={isMatched || open.length === 2}>{revealed ? card.value : "?"}</button>;
      })}
    </div>
    <button type="button" className="button button-secondary" onClick={restart}>Shuffle and restart</button>
  </div>;
}

function NumberGuess() {
  const [target, setTarget] = useState(randomTarget);
  const [guess, setGuess] = useState("");
  const [attempts, setAttempts] = useState<number[]>([]);
  const [message, setMessage] = useState("Enter a number from 1 to 100.");
  const won = attempts.at(-1) === target;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = Number(guess);
    if (!Number.isInteger(value) || value < 1 || value > 100) {
      setMessage("Choose a whole number from 1 to 100.");
      return;
    }
    setAttempts((current) => [...current, value]);
    setMessage(value === target ? `You got it in ${attempts.length + 1} ${attempts.length === 0 ? "guess" : "guesses"}!` : value < target ? "Too low. Try a higher number." : "Too high. Try a lower number.");
    setGuess("");
  }

  function restart() {
    setTarget(randomTarget());
    setGuess("");
    setAttempts([]);
    setMessage("Enter a number from 1 to 100.");
  }

  return <div className="game-layout number-game">
    <div><span className="eyebrow">A number is hiding</span><h2>Number guess</h2><p className="game-status" aria-live="polite">{message}</p></div>
    <form className="guess-form" onSubmit={submit}>
      <label className="field-label" htmlFor="number-guess">Your guess</label>
      <div className="guess-controls"><input id="number-guess" className="form-input" type="number" min="1" max="100" step="1" value={guess} onChange={(event) => setGuess(event.target.value)} disabled={won} /><button className="button button-primary" type="submit" disabled={won}>Guess</button></div>
    </form>
    {attempts.length > 0 && <p className="guess-history">Previous guesses: {attempts.join(", ")}</p>}
    <button type="button" className="button button-secondary" onClick={restart}>New number</button>
  </div>;
}

function randomTarget(): number {
  return Math.floor(Math.random() * 100) + 1;
}
