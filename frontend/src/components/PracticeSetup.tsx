import { useState } from "react";
import {
  ArrowDownRight,
  ArrowRight,
  BookOpen,
  Bookmark,
  Check,
  ChevronDown,
  Clock3,
  Info,
  Lock,
  RotateCcw,
  Search,
} from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Toggle } from "@/components/ui/toggle";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils";
import { SessionMode, type SessionMode as Mode } from "../generated/model/sessionMode";
import { TimerDuration } from "../generated/model/timerDuration";

export type SetupPreset = { id: number; name: string; is_default: boolean };
export type SetupTaxonomy = {
  id: number;
  name: string;
  subtopics: { id: number; name: string }[];
}[];

const modes: { id: Mode; title: string; sub: string; icon: typeof Clock3; badge?: string }[] = [
  {
    id: SessionMode.anytime,
    title: "Anytime test prep",
    sub: "50 clues · 15 seconds each",
    icon: Clock3,
    badge: "Timed",
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
    badge: "Adaptive",
  },
  {
    id: SessionMode.review,
    title: "Review mistakes",
    sub: "Revisit clues you missed",
    icon: RotateCcw,
  },
];
const counts = [
  { value: 10, label: "Quick warm-up" },
  { value: 20, label: "Focused round" },
  { value: 30, label: "Deep practice" },
  { value: 50, label: "Full session" },
];
const timers = [
  { value: 0, label: "Off" },
  { value: TimerDuration.NUMBER_15, label: "15s" },
  { value: TimerDuration.NUMBER_30, label: "30s" },
  { value: TimerDuration.NUMBER_60, label: "60s" },
];
const rowColors = ["#3d57ff", "#5f7cff", "#ffcf4a", "#ffae4a", "#ff8a6b"];
const money = (n: number) => `$${n.toLocaleString()}`;

type Props = {
  mode: Mode;
  setMode: (mode: Mode) => void;
  count: number;
  setCount: (n: number) => void;
  timerSeconds: number;
  setTimerSeconds: (n: number) => void;
  minDifficulty: number;
  setMinDifficulty: (n: number) => void;
  maxDifficulty: number;
  setMaxDifficulty: (n: number) => void;
  minDate: string;
  setMinDate: (v: string) => void;
  maxDate: string;
  setMaxDate: (v: string) => void;
  weights: number[];
  setWeight: (index: number, value: number) => void;
  weightsCustomized: boolean;
  includeDouble: boolean;
  setIncludeDouble: (v: boolean) => void;
  includeDailyDoubles: boolean;
  setIncludeDailyDoubles: (v: boolean) => void;
  includeFinal: boolean;
  setIncludeFinal: (v: boolean) => void;
  taxonomy?: SetupTaxonomy;
  subjectIds: number[];
  setSubjectIds: (ids: number[]) => void;
  subtopicIds: number[];
  setSubtopicIds: (ids: number[]) => void;
  presets?: SetupPreset[];
  onLoadPreset: (id: number) => void;
  presetName: string;
  setPresetName: (v: string) => void;
  onSavePreset: () => Promise<boolean>;
  onReset: () => void;
  busy: boolean;
  onStart: () => void;
};

export function PracticeSetup(p: Props) {
  const anytime = p.mode === SessionMode.anytime;
  const [saveOpen, setSaveOpen] = useState(false);
  const [poolOpen, setPoolOpen] = useState(false);
  const [subjectSearch, setSubjectSearch] = useState("");

  const effectiveCount = anytime ? 50 : p.count;
  const effectiveTimer = anytime ? 15 : p.timerSeconds;
  const weights = p.weights.map((w, i) =>
    i + 1 >= p.minDifficulty && i + 1 <= p.maxDifficulty ? w : 0,
  );
  const total = weights.reduce((a, b) => a + b, 0) || 1;
  const average =
    Math.round(weights.reduce((a, w, i) => a + w * (i + 1) * 200, 0) / total / 10) * 10;
  const modeInfo = modes.find((m) => m.id === p.mode)!;
  const countLabel = counts.find((c) => c.value === p.count)?.label ?? "Custom round";
  const selectedSubjects = p.subjectIds.length + p.subtopicIds.length;
  const dateText = (value: string) =>
    value
      ? new Date(`${value}T00:00`).toLocaleDateString(undefined, {
          month: "short",
          year: "numeric",
        })
      : "";
  const rounds = [
    "J!",
    p.includeDouble && "DJ!",
    p.includeDailyDoubles && "Daily Doubles",
    p.includeFinal && "FJ!",
  ]
    .filter(Boolean)
    .join(", ");
  const subjectQuery = subjectSearch.trim().toLowerCase();
  const visibleSubjects = (p.taxonomy ?? []).filter(
    (s) =>
      !subjectQuery ||
      s.name.toLowerCase().includes(subjectQuery) ||
      s.subtopics.some((t) => t.name.toLowerCase().includes(subjectQuery)),
  );
  const toggleId = (ids: number[], id: number, on: boolean, set: (ids: number[]) => void) =>
    set(on ? [...ids, id] : ids.filter((x) => x !== id));
  const rowOptions = [1, 2, 3, 4, 5].map((level) => (
    <SelectItem key={level} value={String(level)}>
      {money(level * 200)}
    </SelectItem>
  ));

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <p className="m-0 text-base text-muted-foreground">
          Pick a mode, then tune the round to fit your time and focus.
        </p>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline">
              <Bookmark /> Presets <ChevronDown />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-60">
            <DropdownMenuLabel className="text-muted-foreground">
              Load a saved setup
            </DropdownMenuLabel>
            {p.presets?.length ? (
              p.presets.map((preset) => (
                <DropdownMenuItem
                  key={preset.id}
                  onSelect={() => {
                    p.onLoadPreset(preset.id);
                    toast.success(`Loaded “${preset.name}”`);
                  }}
                >
                  {preset.name}
                  {preset.is_default && (
                    <Badge variant="outline" className="ml-auto">
                      default
                    </Badge>
                  )}
                </DropdownMenuItem>
              ))
            ) : (
              <DropdownMenuItem disabled>No saved setups yet</DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => setSaveOpen(true)}>
              Save current setup…
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>

      <div className="grid items-start gap-6 min-[961px]:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-6">
          <Card aria-labelledby="setup-mode">
            <CardHeader>
              <CardTitle id="setup-mode" className="flex items-center gap-2">
                <Step n={1} /> Mode
              </CardTitle>
              <CardDescription>How this round should feel.</CardDescription>
            </CardHeader>
            <CardContent>
              <RadioGroup
                aria-labelledby="setup-mode"
                value={p.mode}
                onValueChange={(v) => p.setMode(v as Mode)}
                className="grid grid-cols-1 gap-3 min-[480px]:grid-cols-2 min-[1100px]:grid-cols-4"
              >
                {modes.map((m) => (
                  <label
                    key={m.id}
                    className={cn(
                      "relative flex cursor-pointer flex-col gap-1.5 rounded-lg border bg-muted p-3.5 transition hover:border-input has-focus-visible:ring-[3px] has-focus-visible:ring-ring/50",
                      p.mode === m.id &&
                        "border-primary bg-primary/5 shadow-[0_0_0_3px_rgba(255,207,74,.12)]",
                    )}
                  >
                    <RadioGroupItem
                      value={m.id}
                      aria-label={m.title}
                      className="absolute top-3.5 right-3.5"
                    />
                    <span className="grid size-9 place-items-center rounded-lg bg-accent text-primary">
                      <m.icon className="size-[18px]" aria-hidden />
                    </span>
                    <strong className="text-[14.5px]">{m.title}</strong>
                    <small className="text-[12.5px] text-muted-foreground">{m.sub}</small>
                    {m.badge && (
                      <Badge variant="outline" className="w-max text-muted-foreground">
                        {m.badge}
                      </Badge>
                    )}
                  </label>
                ))}
              </RadioGroup>
            </CardContent>
          </Card>

          <Card aria-labelledby="setup-length">
            <CardHeader>
              <CardTitle id="setup-length" className="flex items-center gap-2">
                <Step n={2} /> Round length
              </CardTitle>
              <CardDescription>Number of clues and time per clue.</CardDescription>
            </CardHeader>
            <CardContent>
              {anytime ? (
                <div className="flex items-center gap-2.5 rounded-lg border border-dashed border-primary/40 bg-primary/5 p-3 text-sm text-muted-foreground">
                  <Lock className="size-4 shrink-0 text-primary" aria-hidden />
                  <span>
                    Anytime test prep always runs{" "}
                    <b className="text-foreground">50 clues at 15 seconds each</b>, like the online
                    test.
                  </span>
                </div>
              ) : (
                <div className="grid gap-5 min-[641px]:grid-cols-2">
                  <div className="flex min-w-0 flex-col gap-2">
                    <Label id="setup-count">Clues</Label>
                    <ToggleGroup
                      type="single"
                      variant="outline"
                      aria-labelledby="setup-count"
                      value={String(p.count)}
                      onValueChange={(v) => v && p.setCount(Number(v))}
                      className="w-full"
                    >
                      {counts.map((c) => (
                        <ToggleGroupItem key={c.value} value={String(c.value)} className="flex-1">
                          {c.value}
                        </ToggleGroupItem>
                      ))}
                    </ToggleGroup>
                    <span className="text-[12.5px] text-muted-foreground">{countLabel}</span>
                  </div>
                  <div className="flex min-w-0 flex-col gap-2">
                    <Label id="setup-timer">Per-clue timer</Label>
                    <ToggleGroup
                      type="single"
                      variant="outline"
                      aria-labelledby="setup-timer"
                      value={String(p.timerSeconds)}
                      onValueChange={(v) => v !== "" && p.setTimerSeconds(Number(v))}
                      className="w-full"
                    >
                      {timers.map((t) => (
                        <ToggleGroupItem key={t.value} value={String(t.value)} className="flex-1">
                          {t.label}
                        </ToggleGroupItem>
                      ))}
                    </ToggleGroup>
                    <span className="text-[12.5px] text-muted-foreground">
                      {p.timerSeconds ? `${p.timerSeconds} seconds per clue` : "No timer"}
                    </span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card aria-labelledby="setup-pool">
            <CardHeader>
              <CardTitle id="setup-pool" className="flex items-center gap-2">
                <Step n={3} /> Clue pool
              </CardTitle>
              <CardDescription>Which clues can be drawn, and how often.</CardDescription>
              <CardAction>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    p.onReset();
                    toast("Clue pool reset");
                  }}
                >
                  Reset
                </Button>
              </CardAction>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              <div className="grid gap-5 min-[641px]:grid-cols-2">
                <div className="flex min-w-0 flex-col gap-2">
                  <Label id="setup-values">Clue values</Label>
                  <div
                    role="group"
                    aria-labelledby="setup-values"
                    className="flex items-center gap-2"
                  >
                    <Select
                      value={String(p.minDifficulty)}
                      onValueChange={(v) => p.setMinDifficulty(Number(v))}
                    >
                      <SelectTrigger aria-label="Lowest value" className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>{rowOptions}</SelectContent>
                    </Select>
                    <span className="text-sm text-muted-foreground" aria-hidden>
                      to
                    </span>
                    <Select
                      value={String(p.maxDifficulty)}
                      onValueChange={(v) => p.setMaxDifficulty(Number(v))}
                    >
                      <SelectTrigger aria-label="Highest value" className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>{rowOptions}</SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="flex min-w-0 flex-col gap-2">
                  <Label id="setup-air">Air dates</Label>
                  <div role="group" aria-labelledby="setup-air" className="flex items-center gap-2">
                    <Input
                      type="date"
                      aria-label="From date"
                      value={p.minDate}
                      onChange={(e) => p.setMinDate(e.target.value)}
                    />
                    <span className="text-sm text-muted-foreground" aria-hidden>
                      to
                    </span>
                    <Input
                      type="date"
                      aria-label="Through date"
                      value={p.maxDate}
                      onChange={(e) => p.setMaxDate(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <Separator />

              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <Label id="setup-mix">Difficulty mix</Label>
                  <span className="text-[12.5px] text-muted-foreground">
                    Weights are normalized automatically; use 0 to exclude a row.
                  </span>
                </div>
                <div
                  role="img"
                  aria-label={`Difficulty mix: ${weights.map((w, i) => `${money((i + 1) * 200)} ${Math.round((w / total) * 100)}%`).join(", ")}`}
                  className="flex h-3 overflow-hidden rounded-full border bg-black/35"
                >
                  {weights.map((w, i) => (
                    <span
                      key={i}
                      className="block h-full transition-[width]"
                      style={{ width: `${(w / total) * 100}%`, background: rowColors[i] }}
                    />
                  ))}
                </div>
                <div role="group" aria-labelledby="setup-mix" className="flex flex-col gap-2.5">
                  {p.weights.map((w, i) => {
                    const on = i + 1 >= p.minDifficulty && i + 1 <= p.maxDifficulty;
                    return (
                      <div
                        key={i}
                        className={cn(
                          "grid grid-cols-[72px_minmax(0,1fr)_72px] items-center gap-3.5",
                          !on && "opacity-40",
                        )}
                      >
                        <span
                          aria-hidden
                          className="rounded-md bg-gradient-to-b from-[#1230c9] to-[#0a1d93] py-1 text-center font-[family-name:var(--font-category)] text-base font-bold tracking-wide text-primary [text-shadow:0_1px_0_#000]"
                        >
                          {money((i + 1) * 200)}
                        </span>
                        <Slider
                          min={0}
                          max={100}
                          step={5}
                          value={[w]}
                          disabled={!on}
                          aria-label={`Weight for ${money((i + 1) * 200)} clues`}
                          onValueChange={([v]) => p.setWeight(i, v)}
                        />
                        <span className="text-right text-sm tabular-nums text-muted-foreground">
                          {on ? `${Math.round((weights[i] / total) * 100)}%` : "—"}
                        </span>
                      </div>
                    );
                  })}
                </div>
                {anytime && !p.weightsCustomized && (
                  <p className="m-0 text-[12.5px] text-muted-foreground">
                    The starting mix is an approximation for practice, not a published official test
                    distribution.
                  </p>
                )}
              </div>

              <Separator />

              <div className="flex flex-col gap-2">
                <Label id="setup-rounds">Rounds &amp; specials</Label>
                <div
                  role="group"
                  aria-labelledby="setup-rounds"
                  className="overflow-hidden rounded-lg border"
                >
                  {[
                    {
                      key: "dj",
                      title: "Include Double Jeopardy!",
                      desc: "Second-round clues, doubled values",
                      on: p.includeDouble,
                      set: p.setIncludeDouble,
                    },
                    {
                      key: "dd",
                      title: "Include Daily Doubles",
                      desc: "Clues that were hidden wagers",
                      on: p.includeDailyDoubles,
                      set: p.setIncludeDailyDoubles,
                    },
                    {
                      key: "fj",
                      title: "Include Final Jeopardy!",
                      desc: "One-clue final round",
                      on: p.includeFinal,
                      set: p.setIncludeFinal,
                    },
                  ].map((row, i) => (
                    <div
                      key={row.key}
                      className={cn(
                        "flex items-center justify-between gap-3 bg-black/15 px-3.5 py-3",
                        i > 0 && "border-t",
                      )}
                    >
                      <div>
                        <Label htmlFor={`switch-${row.key}`}>{row.title}</Label>
                        <div className="text-[12.5px] text-muted-foreground">{row.desc}</div>
                      </div>
                      <Switch id={`switch-${row.key}`} checked={row.on} onCheckedChange={row.set} />
                    </div>
                  ))}
                </div>
              </div>

              <Collapsible open={poolOpen} onOpenChange={setPoolOpen}>
                <CollapsibleTrigger asChild>
                  <button
                    type="button"
                    className="flex w-full items-center justify-between rounded-lg border px-3.5 py-3 text-left outline-none hover:bg-white/[.02] focus-visible:ring-[3px] focus-visible:ring-ring/50"
                  >
                    <span className="text-sm font-medium">
                      Filter by subject or subtopic{" "}
                      <span className="font-normal text-muted-foreground">(optional)</span>
                      {selectedSubjects > 0 && (
                        <Badge className="ml-2 border-primary/40 bg-primary/10 text-primary">
                          {selectedSubjects} selected
                        </Badge>
                      )}
                    </span>
                    <ChevronDown
                      className={cn(
                        "size-4 text-muted-foreground transition-transform",
                        poolOpen && "rotate-180",
                      )}
                      aria-hidden
                    />
                  </button>
                </CollapsibleTrigger>
                <CollapsibleContent className="flex flex-col gap-4 pt-4">
                  {p.taxonomy?.length ? (
                    <>
                      <div className="relative">
                        <Search
                          className="absolute top-2.5 left-3 size-4 text-muted-foreground"
                          aria-hidden
                        />
                        <Input
                          aria-label="Search subjects"
                          placeholder="Search subjects…"
                          className="pl-9"
                          value={subjectSearch}
                          onChange={(e) => setSubjectSearch(e.target.value)}
                        />
                      </div>
                      <div className="flex flex-col gap-3">
                        {visibleSubjects.map((subject) => {
                          const subjectOn = p.subjectIds.includes(subject.id);
                          return (
                            <div key={subject.id} className="flex flex-col gap-2">
                              <Toggle
                                variant="outline"
                                size="sm"
                                className="w-max rounded-full data-[state=on]:border-primary/50 data-[state=on]:bg-primary/10 data-[state=on]:text-primary"
                                pressed={subjectOn}
                                onPressedChange={(on) =>
                                  toggleId(p.subjectIds, subject.id, on, p.setSubjectIds)
                                }
                              >
                                {subjectOn && <Check aria-hidden />}
                                {subject.name}
                              </Toggle>
                              {subject.subtopics.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 pl-4">
                                  {subject.subtopics.map((topic) => {
                                    const on = p.subtopicIds.includes(topic.id);
                                    return (
                                      <Toggle
                                        key={topic.id}
                                        variant="outline"
                                        size="sm"
                                        className="h-7 rounded-full px-2.5 text-xs data-[state=on]:border-primary/50 data-[state=on]:bg-primary/10 data-[state=on]:text-primary"
                                        pressed={on}
                                        onPressedChange={(v) =>
                                          toggleId(p.subtopicIds, topic.id, v, p.setSubtopicIds)
                                        }
                                      >
                                        {topic.name}
                                      </Toggle>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </>
                  ) : (
                    <p className="m-0 text-sm text-muted-foreground">
                      Subject and subtopic filters are available after loading the optional
                      taxonomy.
                    </p>
                  )}
                  <Alert>
                    <Info />
                    <AlertTitle>About the data</AlertTitle>
                    <AlertDescription>
                      Clue classification is optional. You can import and study source clues without
                      assigning subjects; subject filters and breakdowns fill in as classifications
                      are added.
                    </AlertDescription>
                  </Alert>
                </CollapsibleContent>
              </Collapsible>
            </CardContent>
          </Card>
        </div>

        <aside className="min-[961px]:sticky min-[961px]:top-5">
          <Card aria-labelledby="setup-summary">
            <CardHeader>
              <CardTitle id="setup-summary">Your round</CardTitle>
              <CardDescription>{modeInfo.title}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              <div
                aria-live="polite"
                className="rounded-lg bg-gradient-to-b from-[#1230c9] to-[#0a1d93] p-4 text-center shadow-[inset_0_0_0_1px_rgba(255,255,255,.08)]"
              >
                <div className="font-[family-name:var(--font-category)] text-xs tracking-[.08em] text-[#dfe3ff] uppercase">
                  {anytime ? "Test simulation" : countLabel}
                </div>
                <div className="font-[family-name:var(--font-category)] text-[42px] leading-[1.1] font-bold text-primary [text-shadow:2px_2px_0_#000]">
                  {effectiveCount}
                </div>
                <div className="text-[12.5px] text-[#dfe3ff]">
                  clues · average value {money(average)}
                  {p.includeDouble ? "+" : ""}
                </div>
              </div>
              <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2.5 text-sm">
                <Row term="Timer">
                  {effectiveTimer
                    ? `${effectiveTimer}s per clue · ~${Math.ceil((effectiveCount * effectiveTimer) / 60)} min`
                    : "None"}
                </Row>
                <Row term="Values">
                  {p.minDifficulty === p.maxDifficulty
                    ? money(p.minDifficulty * 200)
                    : `${money(p.minDifficulty * 200)}–${money(p.maxDifficulty * 200)}`}
                </Row>
                <Row term="Air dates">
                  {!p.minDate && !p.maxDate
                    ? "All"
                    : `${dateText(p.minDate) || "Any"} – ${dateText(p.maxDate) || "now"}`}
                </Row>
                <Row term="Rounds">{rounds}</Row>
                <Row term="Subjects">
                  {selectedSubjects ? `${selectedSubjects} selected` : "All"}
                </Row>
              </dl>
              <Button
                size="lg"
                className="h-12 w-full text-base font-semibold"
                disabled={p.busy}
                onClick={p.onStart}
              >
                {p.busy ? "Preparing your round…" : "Begin practice"}
                <ArrowRight />
              </Button>
              <Button variant="outline" className="w-full" onClick={() => setSaveOpen(true)}>
                Save as preset
              </Button>
            </CardContent>
          </Card>
        </aside>
      </div>

      <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
        <DialogContent className="sm:max-w-md">
          <form
            className="flex flex-col gap-4"
            onSubmit={async (e) => {
              e.preventDefault();
              const name = p.presetName.trim();
              if (!name) return;
              if (await p.onSavePreset()) {
                setSaveOpen(false);
                toast.success(`Saved “${name}”`);
              }
            }}
          >
            <DialogHeader>
              <DialogTitle>Save this setup</DialogTitle>
              <DialogDescription>
                Save the mode, length and clue pool so you can load them again from Presets.
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-2">
              <Label htmlFor="preset-name">Name</Label>
              <Input
                id="preset-name"
                value={p.presetName}
                maxLength={100}
                placeholder="Name this setup"
                onChange={(e) => p.setPresetName(e.target.value)}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setSaveOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={p.busy || !p.presetName.trim()}>
                Save preset
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Step({ n }: { n: number }) {
  return (
    <span
      aria-hidden
      className="inline-grid size-[22px] place-items-center rounded-full border border-input bg-accent text-xs font-bold text-primary"
    >
      {n}
    </span>
  );
}

function Row({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{term}</dt>
      <dd className="m-0 text-right font-medium">{children}</dd>
    </>
  );
}
