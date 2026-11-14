import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownRight,
  ArrowRight,
  BookOpen,
  Check,
  ChevronLeft,
  Clock3,
  Compass,
  History,
  Layers3,
  RotateCcw,
  Settings2,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import { api } from "./lib/api-client";
import { useRealtimeSync } from "./hooks/useRealtimeSync";
import {
  AttemptGrade,
  type AttemptGrade as AttemptGradeValue,
} from "./generated/model/attemptGrade";
import {
  RecallRating,
  type RecallRating as RecallRatingValue,
} from "./generated/model/recallRating";
import { SessionMode, type SessionMode as SessionModeValue } from "./generated/model/sessionMode";
import { TimerDuration } from "./generated/model/timerDuration";

type Mode = SessionModeValue;
type ManualGrade =
  | typeof AttemptGrade.correct
  | typeof AttemptGrade.partial
  | typeof AttemptGrade.incorrect;
type Session = {
  id: string;
  mode: Mode;
  current_index: number;
  total: number;
  config?: { timer_seconds?: number | null };
  shortfall?: number;
  is_complete: boolean;
  question?: {
    category: string;
    clue: string;
    correct_response: string | null;
    difficulty: number | null;
    subject: string | null;
    answered: boolean;
    revealed: boolean;
    answer: string;
    deadline_at?: string | null;
    seconds_per_question?: number | null;
    grading?: AttemptGradeValue | null;
    recall_rating?: RecallRatingValue | null;
  };
};
type Result = {
  score: number;
  total: number;
  accuracy: number;
  attempts: {
    position: number;
    category: string;
    clue: string;
    response: string;
    correct_response: string;
    correctness: AttemptGradeValue;
    recall_rating: RecallRatingValue | null;
    difficulty: number | null;
  }[];
};
type Dashboard = {
  total_attempts: number;
  graded_attempts: number;
  novel_graded_attempts: number;
  uncertain_attempts: number;
  new_attempts: number;
  correct: number;
  accuracy: number;
  novel_accuracy: number;
  proficiency: number;
  lower_bound: number;
  upper_bound: number;
  average_response_ms: number | null;
  review_attempts: number;
  review_accuracy: number;
  subjects: SubjectPerformance[];
  weak_areas: SubjectPerformance[];
  difficulty_levels: { level: number; attempts: number; proficiency: number }[];
  mode_performance: { mode: Mode; attempts: number; proficiency: number }[];
  recent_trend: {
    recent_attempts: number;
    recent_accuracy: number | null;
    previous_attempts: number;
    previous_accuracy: number | null;
    delta: number | null;
  };
  recommendations: string[];
};
type SubjectPerformance = {
  id: number;
  name: string;
  attempts: number;
  proficiency: number;
  lower_bound: number;
  upper_bound: number;
  confidence: string;
  subtopics: {
    id: number;
    name: string;
    attempts: number;
    proficiency: number;
    lower_bound: number;
    upper_bound: number;
    by_difficulty: { level: number; attempts: number; proficiency: number }[];
  }[];
};
type Taxonomy = { id: number; name: string; subtopics: { id: number; name: string }[] }[];
type Job = {
  id: string;
  status: string;
  total: number;
  processed: number;
  failed: number;
  error: string;
  created_at: string;
};
type Preset = {
  id: number;
  name: string;
  mode: Mode;
  config: Record<string, unknown>;
  is_default: boolean;
};

const modes: { id: Mode; title: string; sub: string; icon: typeof Target }[] = [
  {
    id: SessionMode.anytime,
    title: "Anytime test prep",
    sub: "50 clues · 15 seconds each",
    icon: Clock3,
  },
  {
    id: SessionMode.general,
    title: "General practice",
    sub: "Study at your own pace",
    icon: BookOpen,
  },
  {
    id: SessionMode.weak_areas,
    title: "Work on weak areas",
    sub: "Spend time where it counts",
    icon: ArrowDownRight,
  },
  {
    id: SessionMode.review,
    title: "Review mistakes",
    sub: "Revisit clues you missed",
    icon: RotateCcw,
  },
];

const recallRatingLabels: Record<RecallRatingValue, string> = {
  [RecallRating.confident]: "Confident — knew it",
  [RecallRating.guessed]: "Guessed — had a hunch",
  [RecallRating.did_not_know]: "Didn't know it",
};

export default function App() {
  const queryClient = useQueryClient();
  const [screen, setScreen] = useState("dashboard");
  const [mode, setMode] = useState<Mode>(SessionMode.general);
  const [count, setCount] = useState(20);
  const [minDifficulty, setMinDifficulty] = useState(1);
  const [maxDifficulty, setMaxDifficulty] = useState(5);
  const [difficultyWeights, setDifficultyWeights] = useState([10, 25, 35, 25, 5]);
  const [weightsCustomized, setWeightsCustomized] = useState(false);
  const [includeDouble, setIncludeDouble] = useState(true);
  const [includeDailyDoubles, setIncludeDailyDoubles] = useState(false);
  const [includeFinal, setIncludeFinal] = useState(false);
  const [minDate, setMinDate] = useState("");
  const [maxDate, setMaxDate] = useState("");
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [subjectIds, setSubjectIds] = useState<number[]>([]);
  const [subtopicIds, setSubtopicIds] = useState<number[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [entry, setEntry] = useState("");
  const [reveal, setReveal] = useState(false);
  const [seconds, setSeconds] = useState(15);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [presetName, setPresetName] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dashboard>("/dashboard"),
  });
  const taxonomy = useQuery({ queryKey: ["taxonomy"], queryFn: () => api<Taxonomy>("/taxonomy") });
  const presets = useQuery({
    queryKey: ["presets"],
    queryFn: () => api<Preset[]>("/presets"),
    enabled: screen === "setup",
  });
  const history = useQuery({
    queryKey: ["history"],
    queryFn: () =>
      api<
        {
          id: string;
          mode: Mode;
          started_at: string;
          status: string;
          count: number;
          answered: number;
        }[]
      >("/history"),
    enabled: screen === "history",
  });
  const jobs = useQuery({
    queryKey: ["classification-jobs"],
    queryFn: () => api<Job[]>("/classification-jobs"),
    enabled: screen === "settings",
    refetchInterval: 5_000,
  });
  useRealtimeSync();

  useEffect(() => {
    const deadline = session?.question?.deadline_at;
    if (screen === "practice" && deadline && !session?.is_complete && !session.question?.revealed) {
      setSeconds(session.question?.seconds_per_question ?? 15);
      const end = Date.parse(deadline);
      const interval = window.setInterval(() => {
        const left = Math.max(0, Math.ceil((end - Date.now()) / 1000));
        setSeconds(left);
      }, 100);
      return () => window.clearInterval(interval);
    }
  }, [
    screen,
    session?.current_index,
    session?.mode,
    session?.is_complete,
    session?.question?.deadline_at,
    session?.question?.revealed,
  ]);

  useEffect(() => {
    if (
      screen === "practice" &&
      session?.question?.deadline_at &&
      !session.is_complete &&
      !session.question.answered &&
      !session.question.revealed
    ) {
      const deadline = Date.parse(session.question.deadline_at);
      const interval = window.setInterval(() => {
        if (Date.now() >= deadline) {
          window.clearInterval(interval);
          if (session.mode === SessionMode.anytime) void answer("");
          else void revealAnswer();
        }
      }, 100);
      return () => window.clearInterval(interval);
    }
  }, [
    screen,
    session?.id,
    session?.mode,
    session?.question?.deadline_at,
    session?.question?.answered,
    session?.question?.revealed,
  ]);

  useEffect(() => {
    if (screen === "practice" && session?.mode === SessionMode.anytime) input.current?.focus();
  }, [screen, session?.current_index, session?.mode, reveal]);

  useEffect(() => {
    function handlePracticeKeys(event: KeyboardEvent) {
      if (screen !== "practice" || !session || busy || session.mode === SessionMode.anytime) return;
      if (
        event.target instanceof HTMLElement &&
        event.target.closest("button, input, textarea, select, [contenteditable='true']")
      )
        return;
      if (!reveal && event.key === "Enter") {
        event.preventDefault();
        void revealAnswer();
      } else if (reveal && ["1", "2", "3"].includes(event.key)) {
        event.preventDefault();
        const rating: Record<string, RecallRatingValue> = {
          "1": RecallRating.confident,
          "2": RecallRating.guessed,
          "3": RecallRating.did_not_know,
        };
        const selectedRating = rating[event.key];
        if (selectedRating) void rateRecall(selectedRating);
      }
    }
    window.addEventListener("keydown", handlePracticeKeys);
    return () => window.removeEventListener("keydown", handlePracticeKeys);
  }, [screen, session, busy, reveal]);

  function selectedConfig() {
    return {
      count: mode === SessionMode.anytime ? 50 : count,
      min_difficulty: minDifficulty,
      max_difficulty: maxDifficulty,
      difficulty_weights:
        mode === SessionMode.anytime || weightsCustomized
          ? Object.fromEntries(
              difficultyWeights.map((weight, index) => [String(index + 1), weight]),
            )
          : {},
      include_double: includeDouble,
      include_daily_doubles: includeDailyDoubles,
      include_final: includeFinal,
      include_media_required: false,
      min_date: minDate || null,
      max_date: maxDate || null,
      timer_seconds: mode === SessionMode.anytime ? null : timerSeconds || null,
      subject_ids: subjectIds,
      subtopic_ids: subtopicIds,
    };
  }

  function applyPreset(preset: Preset) {
    const config = preset.config;
    setMode(preset.mode);
    if (typeof config.count === "number") setCount(config.count);
    if (typeof config.min_difficulty === "number") setMinDifficulty(config.min_difficulty);
    if (typeof config.max_difficulty === "number") setMaxDifficulty(config.max_difficulty);
    if (typeof config.include_double === "boolean") setIncludeDouble(config.include_double);
    if (typeof config.include_daily_doubles === "boolean")
      setIncludeDailyDoubles(config.include_daily_doubles);
    if (typeof config.include_final === "boolean") setIncludeFinal(config.include_final);
    if (typeof config.min_date === "string") setMinDate(config.min_date);
    else if (config.min_date === null) setMinDate("");
    if (typeof config.max_date === "string") setMaxDate(config.max_date);
    else if (config.max_date === null) setMaxDate("");
    setTimerSeconds(typeof config.timer_seconds === "number" ? config.timer_seconds : 0);
    if (Array.isArray(config.subject_ids))
      setSubjectIds(config.subject_ids.filter(Number.isInteger) as number[]);
    if (Array.isArray(config.subtopic_ids))
      setSubtopicIds(config.subtopic_ids.filter(Number.isInteger) as number[]);
    if (typeof config.difficulty_weights === "object" && config.difficulty_weights !== null) {
      const weights = config.difficulty_weights as Record<string, unknown>;
      setDifficultyWeights([1, 2, 3, 4, 5].map((level) => Number(weights[String(level)] ?? 0)));
      setWeightsCustomized(Object.values(weights).some((weight) => Number(weight) > 0));
    }
  }

  async function savePreset() {
    if (!presetName.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api<Preset>("/presets", {
        method: "POST",
        body: JSON.stringify({ name: presetName.trim(), mode, config: selectedConfig() }),
      });
      setPresetName("");
      await queryClient.invalidateQueries({ queryKey: ["presets"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save preset.");
    } finally {
      setBusy(false);
    }
  }

  async function start() {
    setBusy(true);
    setError("");
    try {
      const started = await api<Session>("/sessions", {
        method: "POST",
        body: JSON.stringify({
          mode,
          ...selectedConfig(),
        }),
      });
      setSession(started);
      if (started.shortfall)
        setError(
          `Only ${started.total} matching clues are available, so this round is shorter than requested.`,
        );
      setEntry("");
      setReveal(Boolean(started.question?.revealed));
      setResult(null);
      setScreen("practice");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start practice.");
    } finally {
      setBusy(false);
    }
  }

  async function startClassification() {
    setBusy(true);
    setError("");
    try {
      await api("/classification-jobs", {
        method: "POST",
        body: JSON.stringify({ concurrency: 2 }),
      });
      await queryClient.invalidateQueries({ queryKey: ["classification-jobs"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start classification.");
    } finally {
      setBusy(false);
    }
  }

  async function answer(text = entry) {
    if (!session || busy) return;
    setBusy(true);
    setError("");
    try {
      const saved = await api<{ saved: boolean; question?: Session }>(
        `/sessions/${session.id}/answer`,
        {
          method: "POST",
          body: JSON.stringify({
            answer: text,
            response_ms:
              current?.deadline_at && current.seconds_per_question
                ? Math.max(
                    0,
                    current.seconds_per_question * 1000 -
                      Math.max(0, Date.parse(current.deadline_at) - Date.now()),
                  )
                : null,
            position: session.current_index,
          }),
        },
      );
      const updated = saved.question!;
      setSession(updated);
      setEntry("");
      if (updated.is_complete) await finish(updated.id);
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["history"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save answer.");
    } finally {
      setBusy(false);
    }
  }

  async function revealAnswer() {
    if (!session || busy || session.mode === SessionMode.anytime || reveal) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api<Session>(`/sessions/${session.id}/reveal`, { method: "POST" });
      setSession(updated);
      setReveal(Boolean(updated.question?.revealed));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reveal the response.");
    } finally {
      setBusy(false);
    }
  }

  async function rateRecall(rating: RecallRatingValue) {
    if (!session || busy) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api<Session>(`/sessions/${session.id}/rate/${session.current_index}`, {
        method: "POST",
        body: JSON.stringify({ rating }),
      });
      setSession(updated);
      setEntry("");
      setReveal(Boolean(updated.question?.revealed));
      if (updated.is_complete) await finish(updated.id);
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["history"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your recall rating.");
    } finally {
      setBusy(false);
    }
  }

  async function finish(id: string) {
    const data = await api<Result>(`/sessions/${id}/results`);
    setResult(data);
    setScreen("results");
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["history"] });
  }

  async function next() {
    if (!session) return;
    setBusy(true);
    try {
      const updated = await api<Session>(`/sessions/${session.id}/advance`, { method: "POST" });
      setSession(updated);
      setEntry("");
      setReveal(Boolean(updated.question?.revealed));
      if (updated.is_complete) await finish(updated.id);
      void queryClient.invalidateQueries({ queryKey: ["history"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not advance.");
    } finally {
      setBusy(false);
    }
  }

  async function endRound() {
    if (!session || busy) return;
    setBusy(true);
    try {
      await api(`/sessions/${session.id}/abandon`, { method: "POST" });
      await finish(session.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not end this round.");
    } finally {
      setBusy(false);
    }
  }

  async function override(position: number, correctness: ManualGrade) {
    if (!session) return;
    setBusy(true);
    try {
      await api(`/sessions/${session.id}/grade/${position}`, {
        method: "POST",
        body: JSON.stringify({ correctness }),
      });
      const updated = await api<Result>(`/sessions/${session.id}/results`);
      setResult(updated);
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    } finally {
      setBusy(false);
    }
  }

  const nav = [
    { id: "dashboard", label: "Overview", icon: Compass },
    { id: "setup", label: "Practice", icon: Sparkles },
    { id: "subjects", label: "Subjects", icon: Layers3 },
    { id: "history", label: "History", icon: History },
    { id: "settings", label: "Settings", icon: Settings2 },
  ];
  const current = session?.question;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">J!</div>
          <div>
            <strong>Study Hall</strong>
            <span>JEOPARDY! PREP</span>
          </div>
        </div>
        <div className="side-label">YOUR SPACE</div>
        <nav>
          {nav.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${screen === item.id ? "active" : ""}`}
              onClick={() => setScreen(item.id)}
            >
              <item.icon size={18} />
              {item.label}
            </button>
          ))}
        </nav>
        <div className="side-note">
          <div className="note-icon">
            <Sparkles size={17} />
          </div>
          <strong>Small steps, sharp recall.</strong>
          <p>Every clue is a chance to build a stronger instinct.</p>
        </div>
        <div className="profile">
          <div className="avatar">S</div>
          <div>
            <strong>Solo study</strong>
            <span>Local profile</span>
          </div>
          <div className="online-dot" />
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="eyebrow">YOUR PERSONAL STUDY SPACE</span>
            <h1>
              {screen === "dashboard"
                ? "Good to see you."
                : screen === "setup"
                  ? "Choose your next round."
                  : screen === "practice"
                    ? "Stay curious."
                    : screen === "results"
                      ? "A round well played."
                      : screen === "subjects"
                        ? "Your knowledge map."
                        : screen === "history"
                          ? "Your study history."
                          : "Your study settings."}
            </h1>
          </div>
          <div className="today-chip">
            <span className="online-dot" /> YOUR PROGRESS IS SAVED LOCALLY
          </div>
        </header>
        {error && (
          <div className="error-banner">
            <X size={16} />
            {error}
            <button onClick={() => setError("")}>Dismiss</button>
          </div>
        )}
        {screen === "dashboard" && (
          <div className="content-grid">
            <section className="welcome-card">
              <div className="welcome-copy">
                <span className="pill">
                  <Sparkles size={14} /> READY WHEN YOU ARE
                </span>
                <h2>
                  A little practice
                  <br />
                  goes a long way.
                </h2>
                <p>Build your breadth, find your blind spots, and get one clue better at a time.</p>
                <button className="button-light" onClick={() => setScreen("setup")}>
                  Start a practice round <ArrowRight size={17} />
                </button>
              </div>
              <div className="welcome-art">
                <div className="orbit orbit-one" />
                <div className="orbit orbit-two" />
                <div className="art-book">
                  <BookOpen size={52} />
                </div>
                <div className="spark spark-a">✳</div>
                <div className="spark spark-b">✦</div>
                <div className="art-tag">
                  LEARN A LITTLE
                  <br />
                  EVERY DAY
                </div>
              </div>
            </section>
            <section className="stat-row">
              <Stat
                label="Clues answered"
                value={dashboard.data?.total_attempts ?? 0}
                hint="All practice rounds"
                icon={BookOpen}
              />
              <Stat
                label="New clues"
                value={dashboard.data?.new_attempts ?? 0}
                hint="First-time attempts"
                icon={Sparkles}
              />
              <Stat
                label="First-try accuracy"
                value={
                  dashboard.data?.novel_graded_attempts
                    ? `${Math.round((dashboard.data.novel_accuracy ?? 0) * 100)}%`
                    : "—"
                }
                hint="New clues only"
                icon={Target}
              />
              <Stat
                label="Avg. response time"
                value={
                  dashboard.data?.average_response_ms == null
                    ? "—"
                    : `${(dashboard.data.average_response_ms / 1000).toFixed(1)}s`
                }
                hint="Across answered clues"
                icon={Clock3}
              />
            </section>
            <section className="panel subject-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">KNOWLEDGE, IN PROGRESS</span>
                  <h3>Subject snapshot</h3>
                </div>
                <button className="text-button" onClick={() => setScreen("subjects")}>
                  Explore subjects <ArrowRight size={15} />
                </button>
              </div>
              {dashboard.data?.subjects?.filter((x) => x.attempts > 0).length ? (
                <div className="subject-list">
                  {dashboard.data.subjects
                    .filter((x) => x.attempts > 0)
                    .slice(0, 6)
                    .map((x) => (
                      <div className="subject-line" key={x.id}>
                        <span>{x.name}</span>
                        <div className="progress-track">
                          <div
                            className="progress-fill"
                            style={{ width: `${Math.round(x.proficiency * 100)}%` }}
                          />
                        </div>
                        <strong>{Math.round(x.proficiency * 100)}%</strong>
                        <small
                          title={`Approx. range ${Math.round(x.lower_bound * 100)}–${Math.round(x.upper_bound * 100)}%`}
                        >
                          n={x.attempts}
                        </small>
                      </div>
                    ))}
                </div>
              ) : (
                <Empty text="Subject classification is optional. Your answers are tracked now; classify clues later whenever you're ready." />
              )}
            </section>
            <section className="panel next-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">A GOOD PLACE TO START</span>
                  <h3>Pick a practice mode</h3>
                </div>
              </div>
              {modes.map((item) => (
                <button
                  className="mode-row"
                  key={item.id}
                  onClick={() => {
                    setMode(item.id);
                    setScreen("setup");
                  }}
                >
                  <span className="mode-icon">
                    <item.icon size={19} />
                  </span>
                  <span>
                    <strong>{item.title}</strong>
                    <small>{item.sub}</small>
                  </span>
                  <ArrowRight size={16} />
                </button>
              ))}
            </section>
            <section className="panel dashboard-insights">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">FIRST-ATTEMPT PERFORMANCE</span>
                  <h3>How your study is going</h3>
                </div>
                <span className="confidence-range">
                  {dashboard.data?.novel_graded_attempts
                    ? `${Math.round(dashboard.data.lower_bound * 100)}–${Math.round(dashboard.data.upper_bound * 100)}% estimated range`
                    : "Prior only until clues are scored"}
                </span>
              </div>
              <div className="insight-grid">
                <div className="insight-stat">
                  <span>Bayesian estimate</span>
                  <strong>{Math.round((dashboard.data?.proficiency ?? 0.5) * 100)}%</strong>
                  <small>Novel clues only · excludes uncertain grades</small>
                </div>
                <div className="insight-stat">
                  <span>Review accuracy</span>
                  <strong>
                    {dashboard.data?.review_attempts
                      ? `${Math.round(dashboard.data.review_accuracy * 100)}%`
                      : "—"}
                  </strong>
                  <small>{dashboard.data?.review_attempts ?? 0} scored review attempts</small>
                </div>
                <div className="insight-stat">
                  <span>Last 50 new clues</span>
                  <strong>
                    {dashboard.data?.recent_trend.recent_accuracy == null
                      ? "—"
                      : `${Math.round(dashboard.data.recent_trend.recent_accuracy * 100)}%`}
                  </strong>
                  <small>
                    {dashboard.data?.recent_trend.delta == null
                      ? "Build more history to see a trend"
                      : `${dashboard.data.recent_trend.delta > 0 ? "+" : ""}${Math.round(dashboard.data.recent_trend.delta * 100)} pts vs. prior clues`}
                  </small>
                </div>
              </div>
              <div className="insight-columns">
                <div>
                  <span className="eyebrow">SUGGESTED NEXT STEPS</span>
                  {dashboard.data?.recommendations.length ? (
                    <ul className="recommendation-list">
                      {dashboard.data.recommendations.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="insight-empty">
                      Recommendations appear when there is enough scored history. Classify clues
                      when you want subject-specific guidance.
                    </p>
                  )}
                </div>
                <div>
                  <span className="eyebrow">BY BOARD ROW</span>
                  <div className="difficulty-summary">
                    {dashboard.data?.difficulty_levels.map((level) => (
                      <div key={level.level}>
                        <span>Row {level.level}</span>
                        <div className="progress-track">
                          <div
                            className="progress-fill"
                            style={{ width: `${level.attempts ? level.proficiency * 100 : 0}%` }}
                          />
                        </div>
                        <small>
                          {level.attempts
                            ? `${Math.round(level.proficiency * 100)}% · n=${level.attempts}`
                            : "—"}
                        </small>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              {dashboard.data?.mode_performance.length ? (
                <div className="mode-summary">
                  {dashboard.data.mode_performance.map((item) => (
                    <span key={item.mode}>
                      {item.mode.replace("_", " ")}: {Math.round(item.proficiency * 100)}% · n=
                      {item.attempts}
                    </span>
                  ))}
                </div>
              ) : null}
            </section>
          </div>
        )}
        {screen === "setup" && (
          <div className="setup-wrap">
            <div className="setup-intro">
              <span className="eyebrow">MAKE IT YOURS</span>
              <h2>
                What would you like
                <br />
                to work on?
              </h2>
              <p>Pick a mode. You can tune the round to fit your time and focus.</p>
            </div>
            <div className="mode-grid">
              {modes.map((item) => (
                <button
                  key={item.id}
                  className={`mode-card ${mode === item.id ? "selected" : ""}`}
                  onClick={() => setMode(item.id)}
                >
                  <span className="mode-icon">
                    <item.icon size={20} />
                  </span>
                  <strong>{item.title}</strong>
                  <small>{item.sub}</small>
                  {mode === item.id && (
                    <span className="selected-check">
                      <Check size={15} />
                    </span>
                  )}
                </button>
              ))}
            </div>
            <div className="preset-controls">
              <label>
                Load a saved setup
                <select
                  value=""
                  onChange={(event) => {
                    const preset = presets.data?.find(
                      (item) => item.id === Number(event.target.value),
                    );
                    if (preset) applyPreset(preset);
                  }}
                >
                  <option value="">Choose a preset…</option>
                  {presets.data?.map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.name}
                      {preset.is_default ? " · default" : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Save this setup
                <input
                  value={presetName}
                  onChange={(event) => setPresetName(event.target.value)}
                  placeholder="Name this setup"
                  maxLength={100}
                />
              </label>
              <button
                className="button-secondary"
                disabled={busy || !presetName.trim()}
                onClick={() => void savePreset()}
              >
                Save preset
              </button>
            </div>
            <div className="setup-controls">
              {mode !== SessionMode.anytime && (
                <label>
                  Questions
                  <select value={count} onChange={(e) => setCount(Number(e.target.value))}>
                    <option value={10}>10 clues · quick warm-up</option>
                    <option value={20}>20 clues · focused round</option>
                    <option value={30}>30 clues · deep practice</option>
                    <option value={50}>50 clues · full session</option>
                  </select>
                </label>
              )}
              {mode !== SessionMode.anytime && (
                <label>
                  Per-clue timer
                  <select
                    value={timerSeconds}
                    onChange={(e) => setTimerSeconds(Number(e.target.value))}
                  >
                    <option value={0}>No timer</option>
                    {[
                      TimerDuration.NUMBER_15,
                      TimerDuration.NUMBER_30,
                      TimerDuration.NUMBER_60,
                    ].map((seconds) => (
                      <option key={seconds} value={seconds}>
                        {seconds} seconds
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <div className="setup-info">
                <span className="eyebrow">A NOTE ABOUT THE DATA</span>
                <p>
                  Clue classification is optional. You can import and study source clues without
                  assigning subjects; subject filters and breakdowns fill in as classifications are
                  added.
                </p>
              </div>
            </div>
            <section className="filter-panel">
              <span className="eyebrow">TUNE THIS ROUND</span>
              <div className="filter-row">
                <label>
                  Difficulty from
                  <select
                    value={minDifficulty}
                    onChange={(e) => setMinDifficulty(Number(e.target.value))}
                  >
                    {[1, 2, 3, 4, 5].map((level) => (
                      <option key={level} value={level}>
                        Row {level}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  through
                  <select
                    value={maxDifficulty}
                    onChange={(e) => setMaxDifficulty(Number(e.target.value))}
                  >
                    {[1, 2, 3, 4, 5].map((level) => (
                      <option key={level} value={level}>
                        Row {level}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  From date
                  <input type="date" value={minDate} onChange={(e) => setMinDate(e.target.value)} />
                </label>
                <label>
                  Through date
                  <input type="date" value={maxDate} onChange={(e) => setMaxDate(e.target.value)} />
                </label>
              </div>
              <div className="difficulty-weights">
                <div>
                  <strong>Difficulty mix</strong>
                  <small>Weights are normalized automatically; use 0 to exclude a row.</small>
                </div>
                {difficultyWeights.map((weight, index) => (
                  <label key={index}>
                    Row {index + 1}
                    <span>
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={weight}
                        onChange={(event) => {
                          const next = [...difficultyWeights];
                          next[index] = Math.max(0, Math.min(100, Number(event.target.value) || 0));
                          setDifficultyWeights(next);
                          setWeightsCustomized(true);
                        }}
                      />
                      %
                    </span>
                  </label>
                ))}
                {mode === SessionMode.anytime && !weightsCustomized && (
                  <p className="fine-print">
                    The starting mix is an approximation for practice, not a published official test
                    distribution.
                  </p>
                )}
              </div>
              <div className="toggle-row">
                <label>
                  <input
                    type="checkbox"
                    checked={includeDouble}
                    onChange={(e) => setIncludeDouble(e.target.checked)}
                  />{" "}
                  Include Double Jeopardy!
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={includeDailyDoubles}
                    onChange={(e) => setIncludeDailyDoubles(e.target.checked)}
                  />{" "}
                  Include Daily Doubles
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={includeFinal}
                    onChange={(e) => setIncludeFinal(e.target.checked)}
                  />{" "}
                  Include Final Jeopardy!
                </label>
              </div>
              {taxonomy.data?.length ? (
                <details className="taxonomy-filter">
                  <summary>
                    Filter by subject or subtopic <span>(optional)</span>
                  </summary>
                  <div className="taxonomy-options">
                    {taxonomy.data.map((subject) => (
                      <details key={subject.id}>
                        <summary>
                          <label>
                            <input
                              type="checkbox"
                              checked={subjectIds.includes(subject.id)}
                              onChange={(e) =>
                                setSubjectIds(
                                  e.target.checked
                                    ? [...subjectIds, subject.id]
                                    : subjectIds.filter((id) => id !== subject.id),
                                )
                              }
                            />{" "}
                            {subject.name}
                          </label>
                        </summary>
                        <div>
                          {subject.subtopics.map((topic) => (
                            <label key={topic.id}>
                              <input
                                type="checkbox"
                                checked={subtopicIds.includes(topic.id)}
                                onChange={(e) =>
                                  setSubtopicIds(
                                    e.target.checked
                                      ? [...subtopicIds, topic.id]
                                      : subtopicIds.filter((id) => id !== topic.id),
                                  )
                                }
                              />{" "}
                              {topic.name}
                            </label>
                          ))}
                        </div>
                      </details>
                    ))}
                  </div>
                </details>
              ) : (
                <p className="filter-hint">
                  Subject and subtopic filters are available after loading the optional taxonomy.
                </p>
              )}
            </section>
            <button className="button-primary" disabled={busy} onClick={start}>
              {busy ? "Preparing your round…" : "Begin practice"}
              <ArrowRight size={17} />
            </button>
            <span className="setup-caption">
              Your questions are selected from your local clue library.
            </span>
          </div>
        )}
        {screen === "practice" && session && current && (
          <section className="practice-wrap">
            <div className="practice-top">
              <button className="back-link" onClick={() => void endRound()} disabled={busy}>
                <ChevronLeft size={17} /> End round
              </button>
              <div className="round-status">
                <span>
                  {session.mode === SessionMode.anytime
                    ? "ANYTIME TEST PREP"
                    : session.mode.replace("_", " ").toUpperCase()}
                </span>
                <strong>
                  {session.current_index + 1}
                  <i> / {session.total}</i>
                </strong>
              </div>
            </div>
            <div className="question-progress">
              <div style={{ width: `${(session.current_index / session.total) * 100}%` }} />
            </div>
            <article className="question-card">
              <div className="question-meta">
                <span className="category-label">{current.category}</span>
                {current.difficulty && <span className="difficulty">ROW {current.difficulty}</span>}
              </div>
              {current.deadline_at && (
                <div className={`timer ${seconds <= 5 ? "urgent" : ""}`}>
                  <Clock3 size={17} />
                  <strong>00:{String(seconds).padStart(2, "0")}</strong>
                </div>
              )}
              <p className="clue-text">{current.clue}</p>
              {session.mode === SessionMode.anytime ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    answer();
                  }}
                >
                  <input
                    ref={input}
                    className="answer-input test-input"
                    value={entry}
                    onChange={(e) => setEntry(e.target.value)}
                    placeholder="Type your response…"
                    autoComplete="off"
                  />
                  <button className="button-primary" disabled={busy}>
                    {busy ? "Saving…" : "Lock in response"}
                    <ArrowRight size={17} />
                  </button>
                </form>
              ) : !reveal ? (
                <div className="answer-reveal">
                  <button className="button-primary" onClick={revealAnswer} disabled={busy}>
                    {busy ? "Turning the card…" : "Reveal response"}
                    <ArrowRight size={17} />
                  </button>
                  <p>Try to recall it first. No typing needed.</p>
                </div>
              ) : (
                <div className="reveal-box">
                  <span className="eyebrow">CORRECT RESPONSE</span>
                  <strong>{current.correct_response}</strong>
                  <p>How well did you recall it?</p>
                  <div className="grade-buttons">
                    <button
                      className="grade-correct"
                      onClick={() => rateRecall(RecallRating.confident)}
                      disabled={busy}
                    >
                      <Check size={17} />
                      <span>
                        <strong>Confident</strong>
                        <small>I knew it before flipping</small>
                      </span>
                      <kbd>1</kbd>
                    </button>
                    <button
                      className="grade-partial"
                      onClick={() => rateRecall(RecallRating.guessed)}
                      disabled={busy}
                    >
                      <Target size={17} />
                      <span>
                        <strong>Guessed</strong>
                        <small>I had a hunch</small>
                      </span>
                      <kbd>2</kbd>
                    </button>
                    <button
                      className="grade-wrong"
                      onClick={() => rateRecall(RecallRating.did_not_know)}
                      disabled={busy}
                    >
                      <X size={17} />
                      <span>
                        <strong>Didn't know</strong>
                        <small>I couldn't recall it</small>
                      </span>
                      <kbd>3</kbd>
                    </button>
                  </div>
                  <small className="rating-hint">
                    Your rating saves this clue and moves to the next.
                  </small>
                </div>
              )}
              <div className="question-footer">
                <span>
                  {reveal ? (
                    <>
                      <kbd>1</kbd> confident · <kbd>2</kbd> guessed · <kbd>3</kbd> didn't know
                    </>
                  ) : (
                    <>
                      <kbd>ENTER</kbd>{" "}
                      {session.mode === SessionMode.anytime ? "to lock in" : "to reveal"}
                    </>
                  )}
                </span>
                <span>{current.subject ?? "Knowledge area not yet assigned"}</span>
              </div>
              {session.mode !== SessionMode.anytime && !reveal && (
                <button
                  className="text-button skip-button"
                  onClick={() => void next()}
                  disabled={busy}
                >
                  Skip this clue <ArrowRight size={14} />
                </button>
              )}
            </article>
          </section>
        )}
        {screen === "results" && result && (
          <section className="results-wrap">
            <div className="score-card">
              <span className="eyebrow">ROUND COMPLETE</span>
              <div className="score-number">
                {result.score}
                <small> / {result.total}</small>
              </div>
              <p>
                {Math.round(result.accuracy * 100)}% credited ·{" "}
                {result.attempts.filter((x) => x.correctness === AttemptGrade.uncertain).length}{" "}
                responses flagged for review
              </p>
              <button
                className="button-primary"
                onClick={() => {
                  setSession(null);
                  setScreen("setup");
                }}
              >
                Practice again <ArrowRight size={17} />
              </button>
            </div>
            <div className="panel review-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">CLUE BY CLUE</span>
                  <h3>Round review</h3>
                </div>
              </div>
              {result.attempts.map((item) => (
                <div className="review-row" key={item.position}>
                  <span className={`result-mark ${item.correctness}`}>
                    {item.correctness === AttemptGrade.correct ? (
                      <Check size={15} />
                    ) : (
                      <X size={15} />
                    )}
                  </span>
                  <div className="review-copy">
                    <span>
                      {item.category} · {item.correctness.toUpperCase()}
                    </span>
                    <p>{item.clue}</p>
                    <small>
                      {item.recall_rating
                        ? `Your recall: ${recallRatingLabels[item.recall_rating]}`
                        : `Your response: ${item.response || "No answer"}`}{" "}
                      · Correct: {item.correct_response}
                    </small>
                  </div>
                  {item.correctness !== AttemptGrade.unanswered && (
                    <div className="review-grade">
                      <button
                        onClick={() => override(item.position, AttemptGrade.correct)}
                        title="Mark correct"
                      >
                        <Check size={15} />
                      </button>
                      <button
                        onClick={() => override(item.position, AttemptGrade.partial)}
                        title="Mark partially correct"
                      >
                        <span>½</span>
                      </button>
                      <button
                        onClick={() => override(item.position, AttemptGrade.incorrect)}
                        title="Mark incorrect"
                      >
                        <X size={15} />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
        {screen === "subjects" && (
          <section className="panel full-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">PRIMARY SUBJECT ATTRIBUTION</span>
                <h3>Subjects and proficiency</h3>
                <p>
                  Each first attempt counts once, under its clue’s primary subject. Classification
                  is optional.
                </p>
              </div>
            </div>
            {dashboard.data?.subjects?.length ? (
              dashboard.data.subjects.map((x) => (
                <div className="subject-explorer" key={x.id}>
                  <div className="subject-line subject-expanded">
                    <span>{x.name}</span>
                    <div className="progress-track">
                      <div
                        className="progress-fill"
                        style={{ width: `${Math.round(x.proficiency * 100)}%` }}
                      />
                    </div>
                    <strong>{Math.round(x.proficiency * 100)}%</strong>
                    <small>{x.attempts} first attempts</small>
                  </div>
                  <div className="subject-subtopics">
                    {x.subtopics
                      .filter((topic) => topic.attempts > 0)
                      .map((topic) => (
                        <details key={topic.id}>
                          <summary>
                            <span>{topic.name}</span>
                            <strong>{Math.round(topic.proficiency * 100)}%</strong>
                            <small>
                              n={topic.attempts} · range {Math.round(topic.lower_bound * 100)}–
                              {Math.round(topic.upper_bound * 100)}%
                            </small>
                          </summary>
                          <div className="topic-difficulty-list">
                            {topic.by_difficulty
                              .filter((level) => level.attempts > 0)
                              .map((level) => (
                                <div key={level.level}>
                                  <span>Difficulty {level.level}</span>
                                  <div className="progress-track">
                                    <div
                                      className="progress-fill"
                                      style={{ width: `${Math.round(level.proficiency * 100)}%` }}
                                    />
                                  </div>
                                  <strong>{Math.round(level.proficiency * 100)}%</strong>
                                  <small>n={level.attempts}</small>
                                </div>
                              ))}
                          </div>
                        </details>
                      ))}
                  </div>
                </div>
              ))
            ) : (
              <Empty text="No classified first attempts yet. Study any clues now; load the optional taxonomy and classify clues when you want subject-level insights." />
            )}
          </section>
        )}
        {screen === "history" && (
          <section className="panel full-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">YOUR RECENT ROUNDS</span>
                <h3>Study history</h3>
              </div>
            </div>
            {history.data?.length ? (
              history.data.map((item) => (
                <button
                  className="history-row"
                  key={item.id}
                  onClick={async () => {
                    try {
                      if (item.status === "active") {
                        const active = await api<Session>(`/sessions/${item.id}`);
                        setSession(active);
                        setEntry(active.question?.answer ?? "");
                        setReveal(
                          Boolean(active.question?.revealed && active.mode !== SessionMode.anytime),
                        );
                        setScreen("practice");
                        return;
                      }
                      const r = await api<Result>(`/sessions/${item.id}/results`);
                      setResult(r);
                      setSession({
                        id: item.id,
                        mode: item.mode,
                        current_index: 0,
                        total: r.total,
                        is_complete: true,
                      });
                      setScreen("results");
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Could not load round");
                    }
                  }}
                >
                  <span className="history-icon">
                    <BookOpen size={17} />
                  </span>
                  <span>
                    <strong>{item.mode.replace("_", " ")}</strong>
                    <small>{new Date(item.started_at).toLocaleString()}</small>
                  </span>
                  <span className="history-count">
                    {item.answered} / {item.count} answered
                  </span>
                  <ArrowRight size={16} />
                </button>
              ))
            ) : (
              <Empty text="Your completed rounds will appear here." />
            )}
          </section>
        )}
        {screen === "settings" && (
          <section className="settings-grid">
            <div className="panel settings-card">
              <span className="settings-icon">
                <Layers3 size={19} />
              </span>
              <span className="eyebrow">OPTIONAL KNOWLEDGE MAP</span>
              <h3>Subject classification</h3>
              <p>
                Clues work without classification. Loading a taxonomy and running the classifier
                unlocks subject filters, weak-area practice, and knowledge breakdowns. It requires
                no classifier for ordinary study.
              </p>
              <code>uv run python backend/manage.py seed_taxonomy</code>
              <code>uv run python backend/manage.py classify_clues --limit 100</code>
              <button
                className="button-primary classify-button"
                disabled={busy}
                onClick={startClassification}
              >
                Start optional classification <ArrowRight size={16} />
              </button>
              {jobs.data?.map((job) => (
                <div className="job-row" key={job.id}>
                  <span className={`job-dot ${job.status}`} />
                  <span>
                    <strong>{job.status}</strong>
                    <small>
                      {job.processed + job.failed} / {job.total} processed · {job.processed}{" "}
                      classified · {job.failed} failed
                    </small>
                  </span>
                </div>
              ))}
            </div>
            <div className="panel settings-card">
              <span className="settings-icon">
                <BookOpen size={19} />
              </span>
              <span className="eyebrow">YOUR CLUE LIBRARY</span>
              <h3>Import clues</h3>
              <p>
                Import a locally available TSV, CSV, or JSON file with the command below. This
                repository includes only synthetic sample clues.
              </p>
              <code>
                uv run python backend/manage.py import_clues /path/to/clues.tsv --revision source-v1
              </code>
              <p className="fine-print">
                Only import material you are authorized to use. Keep source files outside version
                control.
              </p>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

function Stat({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  hint: string;
  icon: typeof Target;
}) {
  return (
    <div className="stat-card">
      <span className="stat-icon">
        <Icon size={17} />
      </span>
      <span className="stat-label">{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </div>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <div className="empty-state">
      <span className="empty-mark">
        <Sparkles size={17} />
      </span>
      <p>{text}</p>
    </div>
  );
}
